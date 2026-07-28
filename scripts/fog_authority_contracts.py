#!/usr/bin/env python3
"""Fog runtime 的 repo role/path/hash 與 exact schema 共用契約。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCHEMA_PATH = Path("docs/architecture/fog_runtime_receipt_v3.schema.json")
DATA_AUTHORITY_PATH = Path("config/fog_runtime_data_authority_v1.json")
PROTECTED_PRODUCTION_ROLES = {
    "model": "models/latest_lgbm.pkl",
    "baseline": "models/baseline_stats.json",
    "ranking": "app/agent_b_ranking.py",
    "weights": "config/signals.yaml",
    "promotion": "app/modeling/model_runtime_promotion.py",
}
EXPECTED_DATA_AUTHORITY: dict[str, Any] = {
    "schema_version": "fog-runtime-data-authority.v1",
    "processed_id_authority": {
        "research_map": {
            "artifact_path": "artifacts/research_map/research_fog_map_latest.json",
            "source_roles": {
                "research_run_history": (
                    "artifacts/autonomous_research/run_history.jsonl"
                ),
            },
        },
        "inventory": {
            "artifact_path": (
                "artifacts/weekend_training/"
                "weekend_universe_inventory_latest.json"
            ),
            "source_roles": {
                "weekend_inventory_snapshot": (
                    "artifacts/weekend_training/"
                    "weekend_universe_inventory_source.json"
                ),
            },
        },
    },
    "trusted_baseline": {
        "path": "authority/trusted-protected-baseline.json",
        "source_identity": "trusted-mainline",
        "protected_roles": PROTECTED_PRODUCTION_ROLES,
    },
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class AuthorityContractError(ValueError):
    """Repo authority fail-closed 錯誤。"""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


def canonical_json_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(root: str | Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise AuthorityContractError("INVALID_REPO_PATH", str(relative_path))
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise AuthorityContractError("INVALID_REPO_PATH", relative_path)
    resolved_root = Path(root).resolve()
    resolved = (resolved_root / path).resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise AuthorityContractError("PATH_ESCAPE", relative_path) from error
    return resolved


def read_json_authority(root: str | Path, relative_path: str) -> dict[str, Any]:
    path = resolve_repo_path(root, relative_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuthorityContractError("AUTHORITY_LOAD_FAILED", relative_path) from error
    if not isinstance(payload, dict):
        raise AuthorityContractError("AUTHORITY_SCHEMA_REJECT", relative_path)
    return payload


def load_data_authority() -> dict[str, Any]:
    """只從本 checkout 的 versioned config載入 data authority。"""
    payload = read_json_authority(PROJECT_ROOT, DATA_AUTHORITY_PATH.as_posix())
    if payload != EXPECTED_DATA_AUTHORITY:
        raise AuthorityContractError(
            "DATA_AUTHORITY_CONTRACT_DRIFT",
            DATA_AUTHORITY_PATH.as_posix(),
        )
    return payload


def verify_declared_source_roles(
    *,
    root: str | Path,
    declared: object,
    expected_roles: dict[str, str],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    if not isinstance(declared, dict) or set(declared) != set(expected_roles):
        return {
            "ok": False,
            "reason_codes": ["SOURCE_ROLE_SET_DRIFT"],
            "resolved_paths": [],
        }
    resolved_paths: list[str] = []
    for role, expected_path in sorted(expected_roles.items()):
        item = declared.get(role)
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            reason_codes.append("SOURCE_LINEAGE_SCHEMA_REJECT")
            continue
        if item.get("path") != expected_path:
            reason_codes.append("SOURCE_PATH_DRIFT")
            continue
        digest = item.get("sha256")
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            reason_codes.append("SOURCE_HASH_INVALID")
            continue
        try:
            path = resolve_repo_path(root, expected_path)
            if not path.is_file():
                reason_codes.append("SOURCE_MISSING")
                continue
            if sha256_file(path) != digest:
                reason_codes.append("SOURCE_HASH_DRIFT")
                continue
            resolved_paths.append(expected_path)
        except AuthorityContractError as error:
            reason_codes.append(error.reason_code)
    return {
        "ok": not reason_codes,
        "reason_codes": sorted(set(reason_codes)),
        "resolved_paths": sorted(resolved_paths),
    }


def verify_trusted_baseline(
    *,
    root: str | Path,
    baseline_path: str,
    protected_roles: dict[str, str] = PROTECTED_PRODUCTION_ROLES,
    expected_source_identity: str,
) -> dict[str, Any]:
    reason_codes: list[str] = []
    try:
        data_authority = load_data_authority()
    except AuthorityContractError as error:
        return {"ok": False, "reason_codes": [error.reason_code]}
    baseline_authority = data_authority["trusted_baseline"]
    if (
        baseline_path != baseline_authority["path"]
        or expected_source_identity != baseline_authority["source_identity"]
        or protected_roles != baseline_authority["protected_roles"]
    ):
        return {"ok": False, "reason_codes": ["DATA_AUTHORITY_ARGUMENT_DRIFT"]}
    canonical_baseline_path = baseline_authority["path"]
    canonical_source_identity = baseline_authority["source_identity"]
    canonical_protected_roles = baseline_authority["protected_roles"]
    try:
        baseline = read_json_authority(root, canonical_baseline_path)
    except AuthorityContractError as error:
        return {"ok": False, "reason_codes": [error.reason_code]}
    if set(baseline) != {
        "schema_version",
        "created_at_utc",
        "source_identity",
        "artifacts",
    }:
        reason_codes.append("BASELINE_SCHEMA_REJECT")
    if baseline.get("schema_version") != "fog-protected-baseline.v1":
        reason_codes.append("BASELINE_SCHEMA_REJECT")
    created_at = baseline.get("created_at_utc")
    if (
        not isinstance(created_at, str)
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z",
            created_at,
        )
        is None
    ):
        reason_codes.append("BASELINE_SCHEMA_REJECT")
    else:
        try:
            datetime.fromisoformat(created_at[:-1] + "+00:00")
        except ValueError:
            reason_codes.append("BASELINE_SCHEMA_REJECT")
    if baseline.get("source_identity") != canonical_source_identity:
        reason_codes.append("SOURCE_IDENTITY_DRIFT")
    artifacts = baseline.get("artifacts")
    observed: dict[str, dict[str, Any]] = {}
    if not isinstance(artifacts, list):
        reason_codes.append("BASELINE_SCHEMA_REJECT")
    else:
        for item in artifacts:
            if (
                not isinstance(item, dict)
                or set(item) != {"role", "path", "sha256"}
                or not isinstance(item.get("role"), str)
            ):
                reason_codes.append("BASELINE_SCHEMA_REJECT")
                continue
            role = item["role"]
            if role in observed:
                reason_codes.append("PROTECTED_ROLE_DUPLICATE")
            observed[role] = item
    if set(observed) != set(canonical_protected_roles):
        reason_codes.append("PROTECTED_ROLE_SET_DRIFT")
    for role, expected_path in sorted(canonical_protected_roles.items()):
        item = observed.get(role)
        if item is None:
            continue
        if item.get("path") != expected_path:
            reason_codes.append("PROTECTED_PATH_SET_DRIFT")
            continue
        digest = item.get("sha256")
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            reason_codes.append("PROTECTED_HASH_INVALID")
            continue
        try:
            current = resolve_repo_path(root, expected_path)
            if not current.is_file():
                reason_codes.append("PROTECTED_ARTIFACT_MISSING")
            elif sha256_file(current) != digest:
                reason_codes.append("PROTECTED_HASH_DRIFT")
        except AuthorityContractError as error:
            reason_codes.append(error.reason_code)
    return {
        "ok": not reason_codes,
        "reason_codes": sorted(set(reason_codes)),
        "protected_roles": dict(sorted(canonical_protected_roles.items())),
    }


def load_receipt_schema(
    *,
    root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    return read_json_authority(root, RECEIPT_SCHEMA_PATH.as_posix())


def _resolve_local_ref(
    root_schema: dict[str, Any],
    reference: str,
) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise AuthorityContractError("RECEIPT_SCHEMA_AUTHORITY_INVALID", reference)
    node: Any = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise AuthorityContractError("RECEIPT_SCHEMA_AUTHORITY_INVALID", reference)
        node = node[part]
    if not isinstance(node, dict):
        raise AuthorityContractError("RECEIPT_SCHEMA_AUTHORITY_INVALID", reference)
    return node


def _type_matches(expected: object, value: object) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    for expected_type in expected_types:
        if expected_type == "object" and isinstance(value, dict):
            return True
        if expected_type == "array" and isinstance(value, list):
            return True
        if expected_type == "string" and isinstance(value, str):
            return True
        if expected_type == "null" and value is None:
            return True
    return expected is None


def _validate_schema_node(
    root_schema: dict[str, Any],
    schema: dict[str, Any],
    value: object,
    location: str,
) -> list[str]:
    if "$ref" in schema:
        schema = _resolve_local_ref(root_schema, str(schema["$ref"]))
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: const")
    if not _type_matches(schema.get("type"), value):
        return errors + [f"{location}: type"]
    if isinstance(value, dict) and schema.get("type") == "object":
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, dict) or not isinstance(required, list):
            return errors + [f"{location}: invalid schema authority"]
        missing = sorted(set(required) - set(value))
        unknown = sorted(set(value) - set(properties))
        if missing:
            errors.append(f"{location}: missing {missing}")
        if schema.get("additionalProperties") is False and unknown:
            errors.append(f"{location}: unknown {unknown}")
        for key in sorted(set(value) & set(properties)):
            child_schema = properties[key]
            if not isinstance(child_schema, dict):
                errors.append(f"{location}.{key}: invalid schema authority")
                continue
            errors.extend(
                _validate_schema_node(
                    root_schema,
                    child_schema,
                    value[key],
                    f"{location}.{key}",
                )
            )
    if isinstance(value, list) and schema.get("type") == "array":
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate_schema_node(
                        root_schema,
                        item_schema,
                        item,
                        f"{location}[{index}]",
                    )
                )
        if schema.get("uniqueItems"):
            encoded = [
                json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False)
                for item in value
            ]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{location}: duplicate items")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            errors.append(f"{location}: minLength")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            errors.append(f"{location}: pattern")
        if schema.get("format") == "date":
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                errors.append(f"{location}: date")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{location}: date-time")
    return errors


def validate_receipt_schema(
    receipt: object,
    *,
    root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    try:
        schema = load_receipt_schema(root=root)
        errors = _validate_schema_node(schema, schema, receipt, "$")
    except AuthorityContractError as error:
        return {
            "ok": False,
            "reason_codes": [error.reason_code],
            "errors": [str(error)],
        }
    return {
        "ok": not errors,
        "reason_codes": [] if not errors else ["RECEIPT_SCHEMA_REJECT"],
        "errors": errors,
    }
