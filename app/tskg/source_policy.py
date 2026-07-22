"""TSKG 離線來源政策 registry 與 fail-closed preflight。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from app.tskg.identity import parse_utc_instant


_TOP_LEVEL_FIELDS = {"schema_version", "registry_version", "policies"}
_POLICY_FIELDS = {
    "policy_id",
    "source_id",
    "source_class",
    "publisher",
    "owner",
    "decision_status",
    "terms_decision",
    "legal_basis",
    "robots_decision",
    "allowed_methods",
    "allowed_paths",
    "allowed_media_types",
    "authentication_constraints",
    "rate_limit",
    "concurrency_limit",
    "user_agent",
    "contact",
    "raw_retention",
    "snippet_retention",
    "metadata_retention",
    "redaction_policy",
    "deletion_policy",
    "redistribution_policy",
    "reviewed_at",
    "expires_at",
    "decision_evidence",
}
_STRING_FIELDS = {
    "policy_id",
    "source_id",
    "publisher",
    "owner",
    "authentication_constraints",
    "user_agent",
    "contact",
    "raw_retention",
    "snippet_retention",
    "metadata_retention",
    "redaction_policy",
    "deletion_policy",
    "redistribution_policy",
}
_LIST_FIELDS = {
    "allowed_methods",
    "allowed_paths",
    "allowed_media_types",
    "decision_evidence",
}
_METHOD_PATTERN = re.compile(r"^[A-Z]+$")
_MEDIA_TYPE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)
_GOVERNED_LOAD_TOKEN = object()
_GOVERNED_REGISTRY_CHECKSUM = "c914d8ba5f179819bfd7f8237ae7b9dc2a2221f1746ed3691fabffec2923018f"
_GOVERNED_POLICY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "tskg_source_policy_governed_v1.json"
)


class SourcePolicyContractError(ValueError):
    """來源 registry 違反 closed/versioned policy contract。"""


class SourcePolicyRegistry:
    """驗證並持有 deterministic、完全離線的來源政策 registry。"""

    def __init__(
        self,
        payload: Mapping[str, Any],
        *,
        _governed_load_token: object | None = None,
    ) -> None:
        if not isinstance(payload, Mapping):
            raise SourcePolicyContractError("registry must be an object")
        canonical = self._validate_and_canonicalize(
            deepcopy(dict(payload)),
            allow_approved_public=_governed_load_token is _GOVERNED_LOAD_TOKEN,
        )
        checksum = _checksum(canonical)
        if (
            _governed_load_token is _GOVERNED_LOAD_TOKEN
            and checksum != _GOVERNED_REGISTRY_CHECKSUM
        ):
            raise SourcePolicyContractError(
                "governed registry content does not match reviewed checksum"
            )
        self._payload = canonical
        self._policies_by_source = {
            policy["source_id"]: policy for policy in canonical["policies"]
        }
        self._checksum = checksum

    @classmethod
    def from_file(cls, path: Path) -> "SourcePolicyRegistry":
        with path.open("r", encoding="utf-8") as policy_file:
            return cls(
                json.load(
                    policy_file,
                    object_pairs_hook=_reject_duplicate_json_members,
                )
            )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SourcePolicyRegistry":
        """從既有 mapping 建立 registry；raw JSON duplicates 只能由 from_file 偵測。"""

        return cls(payload)

    @classmethod
    def from_governed_file(cls, path: Path) -> "SourcePolicyRegistry":
        """載入經 code review 版控的正式來源政策；不接受 runtime mapping 提權。"""

        governed_path = Path(path).resolve()
        if governed_path != _GOVERNED_POLICY_PATH.resolve():
            raise SourcePolicyContractError(
                "governed policy must use the pinned repository path"
            )
        with governed_path.open("r", encoding="utf-8") as policy_file:
            payload = json.load(
                policy_file,
                object_pairs_hook=_reject_duplicate_json_members,
            )
        if payload.get("registry_version") != "source-policy-governed-v1":
            raise SourcePolicyContractError(
                "governed registry_version must equal source-policy-governed-v1"
            )
        return cls(payload, _governed_load_token=_GOVERNED_LOAD_TOKEN)

    @property
    def checksum(self) -> str:
        return self._checksum

    def policy_for_source(self, source_id: str) -> dict[str, Any] | None:
        policy = self._policies_by_source.get(source_id)
        return deepcopy(policy) if policy is not None else None

    def summary(self) -> dict[str, Any]:
        policies = self._payload["policies"]
        return {
            "schema_version": self._payload["schema_version"],
            "registry_version": self._payload["registry_version"],
            "policy_count": len(policies),
            "approved_synthetic_count": sum(
                policy["source_class"] == "SYNTHETIC"
                and policy["decision_status"] == "APPROVED"
                for policy in policies
            ),
            "approved_public_count": sum(
                policy["source_class"] == "PUBLIC"
                and policy["decision_status"] == "APPROVED"
                for policy in policies
            ),
        }

    @staticmethod
    def _validate_and_canonicalize(
        payload: dict[str, Any],
        *,
        allow_approved_public: bool,
    ) -> dict[str, Any]:
        _require_closed_shape(payload, _TOP_LEVEL_FIELDS, "registry")
        if payload.get("schema_version") != "tskg-source-policy-v1":
            raise SourcePolicyContractError(
                "schema_version must equal tskg-source-policy-v1"
            )
        if not _is_non_empty_string(payload.get("registry_version")):
            raise SourcePolicyContractError("registry_version must be non-empty")
        policies = payload.get("policies")
        if not isinstance(policies, list) or not policies:
            raise SourcePolicyContractError("policies must be a non-empty list")

        policy_ids: set[str] = set()
        source_ids: set[str] = set()
        canonical_policies: list[dict[str, Any]] = []
        for policy in policies:
            canonical = _validate_policy(
                policy,
                allow_approved_public=allow_approved_public,
            )
            if canonical["policy_id"] in policy_ids:
                raise SourcePolicyContractError("duplicate policy_id")
            if canonical["source_id"] in source_ids:
                raise SourcePolicyContractError("duplicate source_id")
            policy_ids.add(canonical["policy_id"])
            source_ids.add(canonical["source_id"])
            canonical_policies.append(canonical)

        payload["policies"] = sorted(
            canonical_policies,
            key=lambda item: (item["source_id"], item["policy_id"]),
        )
        return payload


def preflight_source(
    registry: SourcePolicyRegistry,
    *,
    source_id: str,
    method: str,
    path: str,
    media_type: str,
    as_of: datetime | str,
    reader: Callable[[str], Any],
    requested_rate: int = 1,
    requested_concurrency: int = 1,
) -> dict[str, Any]:
    """所有政策與 request gate 通過後，才允許 reader 被呼叫一次。"""

    if not isinstance(registry, SourcePolicyRegistry):
        raise TypeError("registry must be a SourcePolicyRegistry")
    if not _is_non_empty_string(source_id):
        return _error(registry, source_id, None, "INVALID_REQUEST", "invalid source_id")
    try:
        instant = parse_utc_instant(as_of)
    except (TypeError, ValueError):
        return _error(registry, source_id, None, "INVALID_REQUEST", "invalid as_of")
    if not callable(reader):
        return _error(registry, source_id, None, "INVALID_REQUEST", "invalid reader")
    if not _is_positive_int(requested_rate) or not _is_positive_int(
        requested_concurrency
    ):
        return _error(
            registry,
            source_id,
            None,
            "INVALID_REQUEST",
            "requested limits must be positive integers",
        )
    if not isinstance(method, str) or not _METHOD_PATTERN.fullmatch(method):
        return _error(registry, source_id, None, "INVALID_REQUEST", "invalid method")
    canonical_path = _canonical_request_path(path)
    if canonical_path is None:
        return _error(registry, source_id, None, "INVALID_REQUEST", "invalid path")
    if not isinstance(media_type, str) or not _MEDIA_TYPE_PATTERN.fullmatch(media_type):
        return _error(
            registry,
            source_id,
            None,
            "INVALID_REQUEST",
            "invalid media_type",
        )

    policy = registry.policy_for_source(source_id)
    if policy is None:
        return _error(
            registry,
            source_id,
            None,
            "SOURCE_UNKNOWN",
            "source has no policy",
        )
    policy_id = policy["policy_id"]
    if policy["decision_status"] == "BLOCKED":
        return _error(
            registry, source_id, policy_id, "SOURCE_BLOCKED", "source is blocked"
        )
    if policy["decision_status"] == "EXPIRED":
        return _error(
            registry, source_id, policy_id, "POLICY_EXPIRED", "policy is expired"
        )
    if not _governance_allows_access(policy):
        return _error(
            registry,
            source_id,
            policy_id,
            "GOVERNANCE_INCOMPLETE",
            "terms, legal basis, and robots must independently allow access",
        )

    reviewed_at = parse_utc_instant(policy["reviewed_at"])
    expires_at = parse_utc_instant(policy["expires_at"])
    if instant < reviewed_at:
        return _error(
            registry,
            source_id,
            policy_id,
            "POLICY_NOT_YET_EFFECTIVE",
            "policy is not yet effective",
        )
    if instant >= expires_at:
        return _error(
            registry, source_id, policy_id, "POLICY_EXPIRED", "policy is expired"
        )
    if method not in policy["allowed_methods"]:
        return _error(
            registry,
            source_id,
            policy_id,
            "METHOD_NOT_ALLOWED",
            "method is outside policy",
        )
    if not any(
        _path_matches(canonical_path, allowed)
        for allowed in policy["allowed_paths"]
    ):
        return _error(
            registry,
            source_id,
            policy_id,
            "PATH_NOT_ALLOWED",
            "path is outside policy",
        )
    if media_type not in policy["allowed_media_types"]:
        return _error(
            registry,
            source_id,
            policy_id,
            "MEDIA_TYPE_NOT_ALLOWED",
            "media type is outside policy",
        )
    if requested_rate > policy["rate_limit"]:
        return _error(
            registry,
            source_id,
            policy_id,
            "RATE_LIMIT_EXCEEDED",
            "requested rate exceeds policy",
        )
    if requested_concurrency > policy["concurrency_limit"]:
        return _error(
            registry,
            source_id,
            policy_id,
            "CONCURRENCY_LIMIT_EXCEEDED",
            "requested concurrency exceeds policy",
        )

    receipt = {
        "policy_id": policy_id,
        "policy_checksum": registry.checksum,
        "source_id": source_id,
        "method": method,
        "path": canonical_path,
        "media_type": media_type,
        "as_of": _canonical_timestamp(instant),
        "requested_rate": requested_rate,
        "requested_concurrency": requested_concurrency,
    }
    receipt["receipt_id"] = _checksum(receipt)
    reader_result = reader(canonical_path)
    return {"ok": True, "receipt": receipt, "reader_result": reader_result}


def _validate_policy(
    value: Any,
    *,
    allow_approved_public: bool,
) -> dict[str, Any]:
    _require_closed_shape(value, _POLICY_FIELDS, "policy")
    policy = deepcopy(value)
    for field in _STRING_FIELDS:
        if not _is_non_empty_string(policy[field]):
            raise SourcePolicyContractError(f"{field} must be a non-empty string")

    enum_contracts = {
        "source_class": {"SYNTHETIC", "PUBLIC"},
        "decision_status": {"APPROVED", "BLOCKED", "EXPIRED"},
        "terms_decision": {"APPROVED", "BLOCKED"},
        "legal_basis": {"APPROVED", "BLOCKED"},
        "robots_decision": {"ALLOW", "DISALLOW"},
    }
    for field, allowed in enum_contracts.items():
        if policy[field] not in allowed:
            raise SourcePolicyContractError(f"unsupported {field}")
    if (
        policy["source_class"] == "PUBLIC"
        and policy["decision_status"] == "APPROVED"
        and not allow_approved_public
    ):
        raise SourcePolicyContractError(
            "PUBLIC approval requires a versioned governed registry"
        )
    for field in _LIST_FIELDS:
        items = policy[field]
        if (
            not isinstance(items, list)
            or not items
            or any(not _is_non_empty_string(item) for item in items)
            or len(set(items)) != len(items)
        ):
            raise SourcePolicyContractError(
                f"{field} must contain unique non-empty strings"
            )
        policy[field] = sorted(items)

    if any(
        not _METHOD_PATTERN.fullmatch(method)
        for method in policy["allowed_methods"]
    ):
        raise SourcePolicyContractError("allowed_methods must use uppercase tokens")
    if any(
        not _is_safe_policy_path(path) for path in policy["allowed_paths"]
    ):
        raise SourcePolicyContractError("allowed_paths contains an unsafe path")
    if any(
        not _MEDIA_TYPE_PATTERN.fullmatch(media_type)
        for media_type in policy["allowed_media_types"]
    ):
        raise SourcePolicyContractError("allowed_media_types contains an invalid value")

    if not _is_bounded_int(policy["rate_limit"], maximum=1000):
        raise SourcePolicyContractError("rate_limit must be between 1 and 1000")
    if not _is_bounded_int(policy["concurrency_limit"], maximum=100):
        raise SourcePolicyContractError(
            "concurrency_limit must be between 1 and 100"
        )
    try:
        reviewed_at = parse_utc_instant(policy["reviewed_at"])
        expires_at = parse_utc_instant(policy["expires_at"])
    except (TypeError, ValueError) as error:
        raise SourcePolicyContractError(
            "reviewed_at and expires_at must be RFC 3339 UTC timestamps"
        ) from error
    if reviewed_at >= expires_at:
        raise SourcePolicyContractError("expires_at must be after reviewed_at")
    return policy


def _require_closed_shape(
    value: Any, expected_fields: set[str], record_name: str
) -> None:
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise SourcePolicyContractError(
            f"{record_name} must contain exactly {sorted(expected_fields)}"
        )


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _is_bounded_int(value: Any, *, maximum: int) -> bool:
    return _is_positive_int(value) and value <= maximum


def _canonical_request_path(path: Any) -> str | None:
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        return None
    if unicodedata.normalize("NFKC", path) != path:
        return None
    if any(unicodedata.category(character).startswith("C") for character in path):
        return None
    if any(token in path for token in ("?", "#", "\\", "%", "//")):
        return None
    if any(segment in {"", ".", ".."} for segment in path.split("/")[1:]):
        return None
    return path


def _is_safe_request_path(path: Any) -> bool:
    return _canonical_request_path(path) is not None


def _is_safe_policy_path(path: Any) -> bool:
    if not isinstance(path, str):
        return False
    concrete = path[:-2] if path.endswith("/*") else path
    if "*" in concrete or not _is_safe_request_path(concrete):
        return False
    return not path.endswith("/") and path != "/*"


def _path_matches(requested: str, allowed: str) -> bool:
    if allowed.endswith("/*"):
        prefix = allowed[:-1]
        return requested.startswith(prefix) and len(requested) > len(prefix)
    return requested == allowed


def _reject_duplicate_json_members(
    members: list[tuple[str, Any]],
) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in members:
        if key in parsed:
            raise SourcePolicyContractError(f"duplicate JSON member: {key}")
        parsed[key] = value
    return parsed


def _governance_allows_access(policy: Mapping[str, Any]) -> bool:
    return (
        policy["terms_decision"] == "APPROVED"
        and policy["legal_basis"] == "APPROVED"
        and policy["robots_decision"] == "ALLOW"
    )


def _canonical_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _checksum(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _error(
    registry: SourcePolicyRegistry,
    source_id: Any,
    policy_id: str | None,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "source_id": source_id if isinstance(source_id, str) else None,
            "policy_id": policy_id,
            "policy_checksum": registry.checksum,
        },
    }
