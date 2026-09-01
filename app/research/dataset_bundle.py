"""Research dataset bundle V1 的純資料契約、identity 與驗證工具。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

from app.research.contracts import (
    CANONICALIZATION_VERSION,
    HASH_PREFIX,
    content_hash,
)
from app.research.receipt_store import write_immutable_json


SCHEMA_VERSION = "research-dataset-bundle.v1"
IDENTITY_KIND = "DATASET_BUNDLE_V1"
FUNDAMENTALS_SCHEMA_VERSION = "research-fundamentals-snapshot.v1"
RESOLVED = "RESOLVED"
ABSENT_BY_CONTRACT = "ABSENT_BY_CONTRACT"
ABSENT_USE_ALL_FEATURE_STOCKS = "ABSENT_USE_ALL_FEATURE_STOCKS"
EMPTY_USE_ALL_FEATURE_STOCKS = "EMPTY_USE_ALL_FEATURE_STOCKS"
FEATURES_ARTIFACT_V1 = "FEATURES_ARTIFACT_V1"
LEGACY_DIAGNOSTIC_ONLY = "LEGACY_DIAGNOSTIC_ONLY"
FORECAST_TRIAL_CONSUMER_V1 = "FORECAST_TRIAL_V1"
FORECAST_TRIAL_DATASET_CONTRACT_V1 = "forecast-trial-dataset.v1"
FORECAST_CHANNEL_SET_V1 = "FORECAST_CHANNEL_SET_V1"

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_BLOB_RE = re.compile(r"^git-sha1:[0-9a-f]{40}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_ROLE_IDENTITY = {
    "FEATURES_ARTIFACT": FEATURES_ARTIFACT_V1,
    "EVENTS_ARTIFACT": "EVENTS_ARTIFACT_V1",
    "SIGNALS_CONFIG": "SIGNALS_CONFIG_V1",
    "FUNDAMENTALS_SNAPSHOT": "FUNDAMENTALS_SNAPSHOT_V1",
    "UNIVERSE_ARTIFACT": "UNIVERSE_ARTIFACT_V1",
    "FORECAST_CHANNEL_SET": FORECAST_CHANNEL_SET_V1,
}

_CONSUMER_MATRIX = {
    ("M4_TRAINING_V1", "m4-training-dataset.v1"): {
        "FEATURES_ARTIFACT": {RESOLVED},
        "EVENTS_ARTIFACT": {RESOLVED, ABSENT_BY_CONTRACT},
        "SIGNALS_CONFIG": {RESOLVED},
        "FUNDAMENTALS_SNAPSHOT": {RESOLVED},
    },
    ("M4_RANKING_V1", "m4-ranking-dataset.v1"): {
        "FEATURES_ARTIFACT": {RESOLVED},
        "EVENTS_ARTIFACT": {RESOLVED, ABSENT_BY_CONTRACT},
        "SIGNALS_CONFIG": {RESOLVED},
        "FUNDAMENTALS_SNAPSHOT": {RESOLVED},
        "UNIVERSE_ARTIFACT": {RESOLVED, ABSENT_USE_ALL_FEATURE_STOCKS, EMPTY_USE_ALL_FEATURE_STOCKS},
    },
    ("STRATEGY_MATRIX_FEATURES_V1", "strategy-matrix-features.v1"): {
        "FEATURES_ARTIFACT": {RESOLVED},
    },
    (FORECAST_TRIAL_CONSUMER_V1, FORECAST_TRIAL_DATASET_CONTRACT_V1): {
        "FORECAST_CHANNEL_SET": {RESOLVED},
    },
}

_IDENTITY_FIELDS = {
    "schema_version",
    "canonicalization_version",
    "identity_kind",
    "consumer_contract",
    "components",
    "transformation_identity",
    "resolution_semantics",
}
_ENVELOPE_FIELDS = {"dataset_bundle_id", "identity_payload"}
_CONSUMER_FIELDS = {"consumer_id", "contract_version"}
_TRANSFORMATION_FIELDS = {"contract_version", "git_blob_ids"}
_RESOLUTION_FIELDS = {"fallback_policy_version", "identity_bearing_absence_is_explicit"}
_RESOLVED_FIELDS = {
    "role",
    "member_key",
    "identity_kind",
    "content_id",
    "resolution_status",
    "format_contract",
    "coverage",
}
_ABSENT_FIELDS = {
    "role",
    "member_key",
    "identity_kind",
    "resolution_status",
    "semantic_absence_code",
    "coverage",
}
_EMPTY_FIELDS = _RESOLVED_FIELDS | {"member_count"}
_FORECAST_CHANNEL_SET_FIELDS = _RESOLVED_FIELDS | {"channels"}
_FORECAST_CHANNEL_FIELDS = {
    "channel_id",
    "channel_index",
    "channel_role",
    "value_contract",
    "missingness_policy",
    "temporal_availability",
}
_FORECAST_TEMPORAL_FIELDS = {"forecast_origin", "available_at", "horizon_start", "horizon_end"}
_FORECAST_CHANNEL_ROLES = {"TARGET", "PAST_COVARIATE", "FUTURE_KNOWN_COVARIATE"}
_FORECAST_MISSINGNESS_POLICIES = {
    "EXPLICIT_NULLS",
    "FORWARD_FILLED_WITH_LIMIT",
    "NOT_APPLICABLE_NO_MISSING",
}
_COMPONENT_COVERAGE_FIELDS = {
    "schema_version",
    "status",
    "expected_member_count",
    "observed_member_count",
    "date_start",
    "date_end",
}
_FUNDAMENTALS_FIELDS = {
    "snapshot_content_id",
    "schema_version",
    "canonicalization_version",
    "identity_kind",
    "as_of",
    "coverage",
    "missing_value_semantics",
    "records_contract",
    "records_content_id",
}
_FUNDAMENTALS_COVERAGE_FIELDS = {
    "universe_content_id",
    "expected_member_count",
    "observed_member_count",
    "date_start",
    "date_end",
    "status",
}
_REQUEST_EXEC_FIELDS = {
    "requested_dataset_bundle_id",
    "executed_dataset_bundle_id",
    "resolution_delta",
}
_DELTA_BASE_FIELDS = {
    "reason_code",
    "changed_identity_paths",
    "changed_roles",
    "resolution_authority",
    "requested_manifest_id",
    "executed_manifest_id",
    "evidence_refs",
}
_REASON_ALLOWED_PREFIX = {
    "SOURCE_FALLBACK": ("/components/",),
    "SOURCE_UNAVAILABLE": ("/components/",),
    "COVERAGE_RECONCILIATION": ("/components/",),
    "TRANSFORMATION_CHANGE": ("/transformation_identity/",),
    "RESOLUTION_POLICY_CHANGE": ("/resolution_semantics/",),
}
_COMPONENT_LEAFS = {
    "identity_kind",
    "content_id",
    "resolution_status",
    "format_contract",
    "semantic_absence_code",
    "member_count",
}
_COVERAGE_LEAFS = {
    "schema_version",
    "universe_content_id",
    "expected_member_count",
    "observed_member_count",
    "date_start",
    "date_end",
    "status",
}

_COMPONENT_COVERAGE_STATUSES_BY_RESOLUTION = {
    RESOLVED: frozenset({"COMPLETE", "PARTIAL", "EMPTY"}),
    ABSENT_BY_CONTRACT: frozenset({"NOT_APPLICABLE"}),
    ABSENT_USE_ALL_FEATURE_STOCKS: frozenset({"NOT_APPLICABLE"}),
    EMPTY_USE_ALL_FEATURE_STOCKS: frozenset({"EMPTY"}),
}


@dataclass(frozen=True)
class ValidationResult:
    status: str
    errors: list[str]


@dataclass(frozen=True)
class SnapshotValidationResult:
    status: str
    content_id: str
    errors: list[str]


@dataclass(frozen=True)
class WriteResult:
    status: str
    path: Path


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _exact_fields(payload: Mapping[str, Any], fields: set[str], prefix: str = "") -> list[str]:
    errors = [f"{prefix}{field} is required" for field in sorted(fields) if field not in payload]
    errors.extend(f"{prefix}{field} is not allowed" for field in sorted(set(payload) - fields))
    return errors


def _hash(value: object, field: str) -> list[str]:
    return [] if isinstance(value, str) and _HASH_RE.match(value) else [f"{field} must be sha256:<64 lowercase hex>"]


def _git_blob(value: object, field: str) -> list[str]:
    return [] if isinstance(value, str) and _GIT_BLOB_RE.match(value) else [f"{field} must be git-sha1:<40 lowercase hex>"]


def _nonempty(value: object, field: str) -> list[str]:
    return [] if isinstance(value, str) and value.strip() else [f"{field} must be non-empty"]


def _date_or_none(value: object, field: str, *, allow_none: bool = True) -> list[str]:
    if value is None and allow_none:
        return []
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return [f"{field} must be YYYY-MM-DD"]
    try:
        date.fromisoformat(value)
    except ValueError:
        return [f"{field} must be a valid calendar date"]
    return []


def _utc_timestamp(value: object, field: str) -> list[str]:
    if not isinstance(value, str):
        return [f"{field} must be an RFC3339 UTC timestamp"]
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return [f"{field} must be an RFC3339 UTC timestamp"]
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        return [f"{field} must be UTC"]
    return []


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        return None
    return parsed


def _non_negative_int(value: object, field: str) -> list[str]:
    return [] if isinstance(value, int) and value >= 0 and not isinstance(value, bool) else [f"{field} must be non-negative integer"]


def _is_scalar_string_list(values: object) -> bool:
    return isinstance(values, list) and all(isinstance(value, str) for value in values)


def _sorted_unique(values: object, field: str) -> list[str]:
    if not isinstance(values, list):
        return [f"{field} must be a list"]
    if not _is_scalar_string_list(values):
        return [f"{field} entries must be strings"]
    if values != sorted(values) or len(values) != len(set(values)):
        return [f"{field} must be sorted and unique"]
    return []


def _canonical_components(components: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = [dict(component) for component in components]
    return sorted(
        normalized,
        key=lambda component: (
            str(component.get("role", "")),
            str(component.get("member_key", "")),
            str(component.get("identity_kind", "")),
            str(component.get("content_id", "")),
            str(component.get("resolution_status", "")),
            str(component.get("semantic_absence_code", "")),
        ),
    )


def _canonical_identity_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(payload)
    components = identity.get("components")
    if isinstance(components, list):
        identity["components"] = _canonical_components([_mapping(component) for component in components])
    transformation = dict(_mapping(identity.get("transformation_identity")))
    blob_ids = transformation.get("git_blob_ids")
    if isinstance(blob_ids, list) and all(isinstance(blob_id, str) for blob_id in blob_ids):
        transformation["git_blob_ids"] = sorted(blob_ids)
    identity["transformation_identity"] = transformation
    return identity


def recompute_dataset_bundle_id(manifest: Mapping[str, Any]) -> str:
    return content_hash(_canonical_identity_payload(_mapping(manifest).get("identity_payload", {})))


def _validate_component_coverage(
    coverage: Mapping[str, Any],
    prefix: str = "coverage.",
    *,
    resolution_status: str,
) -> list[str]:
    errors = _exact_fields(coverage, _COMPONENT_COVERAGE_FIELDS, prefix)
    if coverage.get("schema_version") != "dataset-component-coverage.v1":
        errors.append(f"{prefix}schema_version is invalid")
    status = coverage.get("status")
    if status not in {"COMPLETE", "PARTIAL", "EMPTY", "NOT_APPLICABLE"}:
        errors.append(f"{prefix}status is invalid")
        return errors
    expected_statuses = _COMPONENT_COVERAGE_STATUSES_BY_RESOLUTION.get(resolution_status, frozenset())
    if status not in expected_statuses:
        errors.append(f"{prefix}status is not allowed for resolution variant")
    expected = coverage.get("expected_member_count")
    observed = coverage.get("observed_member_count")
    if status == "NOT_APPLICABLE":
        if expected is not None or observed != 0 or coverage.get("date_start") is not None or coverage.get("date_end") is not None:
            errors.append(f"{prefix}NOT_APPLICABLE coverage must be semantic absence")
        return errors
    errors.extend(_non_negative_int(expected, f"{prefix}expected_member_count"))
    errors.extend(_non_negative_int(observed, f"{prefix}observed_member_count"))
    if isinstance(expected, int) and isinstance(observed, int) and observed > expected:
        errors.append(f"{prefix}observed_member_count must be <= expected_member_count")
    if status == "COMPLETE" and expected != observed:
        errors.append(f"{prefix}COMPLETE coverage must observe all expected members")
    if status == "PARTIAL" and not (isinstance(expected, int) and isinstance(observed, int) and 0 < observed < expected):
        errors.append(f"{prefix}PARTIAL coverage must be between empty and complete")
    if status == "EMPTY" and (expected != 0 or observed != 0):
        errors.append(f"{prefix}EMPTY coverage counts must be zero")
    start = coverage.get("date_start")
    end = coverage.get("date_end")
    errors.extend(_date_or_none(start, f"{prefix}date_start"))
    errors.extend(_date_or_none(end, f"{prefix}date_end"))
    if status == "EMPTY":
        if start is not None or end is not None:
            errors.append(f"{prefix}EMPTY coverage dates must be null")
    else:
        if start is None or end is None:
            errors.append(f"{prefix}{status} coverage dates must be present")
        elif isinstance(start, str) and isinstance(end, str) and start > end:
            errors.append(f"{prefix}date_start must be <= date_end")
    return errors


def _validate_fundamentals_coverage(coverage: Mapping[str, Any], prefix: str = "coverage.") -> list[str]:
    errors = _exact_fields(coverage, _FUNDAMENTALS_COVERAGE_FIELDS, prefix)
    errors.extend(_hash(coverage.get("universe_content_id"), f"{prefix}universe_content_id"))
    expected = coverage.get("expected_member_count")
    observed = coverage.get("observed_member_count")
    errors.extend(_non_negative_int(expected, f"{prefix}expected_member_count"))
    errors.extend(_non_negative_int(observed, f"{prefix}observed_member_count"))
    status = coverage.get("status")
    if status not in {"COMPLETE", "PARTIAL", "EMPTY"}:
        errors.append(f"{prefix}status is invalid")
    if isinstance(expected, int) and isinstance(observed, int) and observed > expected:
        errors.append(f"{prefix}observed_member_count must be <= expected_member_count")
    if status == "COMPLETE" and expected != observed:
        errors.append(f"{prefix}COMPLETE coverage must observe all expected members")
    if status == "PARTIAL" and not (isinstance(expected, int) and isinstance(observed, int) and 0 < observed < expected):
        errors.append(f"{prefix}PARTIAL coverage must be between empty and complete")
    if status == "EMPTY" and observed != 0:
        errors.append(f"{prefix}EMPTY coverage observed_member_count must be zero")
    start = coverage.get("date_start")
    end = coverage.get("date_end")
    errors.extend(_date_or_none(start, f"{prefix}date_start"))
    errors.extend(_date_or_none(end, f"{prefix}date_end"))
    if status == "EMPTY":
        if start is not None or end is not None:
            errors.append(f"{prefix}EMPTY coverage dates must be null")
    elif start is None or end is None:
        errors.append(f"{prefix}{status} coverage dates must be present")
    elif isinstance(start, str) and isinstance(end, str) and start > end:
        errors.append(f"{prefix}date_start must be <= date_end")
    return errors


def validate_fundamentals_snapshot(payload: Mapping[str, Any]) -> SnapshotValidationResult:
    snapshot = _mapping(payload)
    errors = _exact_fields(snapshot, _FUNDAMENTALS_FIELDS)
    if snapshot.get("schema_version") != FUNDAMENTALS_SCHEMA_VERSION:
        errors.append("schema_version is invalid")
    if snapshot.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("canonicalization_version is invalid")
    if snapshot.get("identity_kind") != "FUNDAMENTALS_SNAPSHOT_V1":
        errors.append("identity_kind is invalid")
    errors.extend(_date_or_none(snapshot.get("as_of"), "as_of", allow_none=False))
    errors.extend(_hash(snapshot.get("records_content_id"), "records_content_id"))
    coverage = _mapping(snapshot.get("coverage"))
    errors.extend(_validate_fundamentals_coverage(coverage))
    missing = _mapping(snapshot.get("missing_value_semantics"))
    errors.extend(_exact_fields(missing, {"policy", "version"}, "missing_value_semantics."))
    if missing.get("policy") not in {"PRESERVE_NULL", "EXPLICIT_EMPTY_SNAPSHOT"}:
        errors.append("missing_value_semantics.policy is invalid")
    errors.extend(_nonempty(missing.get("version"), "missing_value_semantics.version"))
    records_contract = _mapping(snapshot.get("records_contract"))
    errors.extend(_exact_fields(records_contract, {"schema_version", "normalization_version"}, "records_contract."))
    errors.extend(_nonempty(records_contract.get("schema_version"), "records_contract.schema_version"))
    errors.extend(_nonempty(records_contract.get("normalization_version"), "records_contract.normalization_version"))
    computed = content_hash(snapshot, omit={"snapshot_content_id"})
    if snapshot.get("snapshot_content_id") != computed:
        errors.append("snapshot_content_id must equal canonical content hash")
    return SnapshotValidationResult("VALID" if not errors else "INVALID", computed, errors)


def _validate_component(component: Mapping[str, Any], allowed: set[str], index: int) -> list[str]:
    prefix = f"components[{index}]."
    errors: list[str] = []
    role = component.get("role")
    status = component.get("resolution_status")
    if not isinstance(role, str) or role not in _ROLE_IDENTITY:
        errors.append(f"{prefix}role is unsupported")
    if isinstance(role, str) and role in _ROLE_IDENTITY and component.get("identity_kind") != _ROLE_IDENTITY[role]:
        errors.append(f"{prefix}identity_kind must be {_ROLE_IDENTITY[role]}")
    if component.get("member_key") != "primary":
        errors.append(f"{prefix}member_key must be primary")
    if status not in allowed:
        errors.append(f"{prefix}resolution_status is not allowed for consumer")
    if role == "FORECAST_CHANNEL_SET":
        return errors + _validate_forecast_channel_set(component, prefix)
    if status == RESOLVED:
        errors.extend(_exact_fields(component, _RESOLVED_FIELDS, prefix))
        errors.extend(_hash(component.get("content_id"), f"{prefix}content_id"))
        errors.extend(_nonempty(component.get("format_contract"), f"{prefix}format_contract"))
        if role == "FUNDAMENTALS_SNAPSHOT":
            errors.extend(_validate_fundamentals_coverage(_mapping(component.get("coverage")), f"{prefix}coverage."))
        else:
            errors.extend(_validate_component_coverage(
                _mapping(component.get("coverage")),
                f"{prefix}coverage.",
                resolution_status=RESOLVED,
            ))
    elif status == ABSENT_BY_CONTRACT:
        errors.extend(_exact_fields(component, _ABSENT_FIELDS, prefix))
        if role != "EVENTS_ARTIFACT":
            errors.append(f"{prefix}ABSENT_BY_CONTRACT only supports EVENTS_ARTIFACT")
        if component.get("semantic_absence_code") != "OPTIONAL_COMPONENT_NOT_PRESENT":
            errors.append(f"{prefix}semantic_absence_code is invalid")
        errors.extend(_validate_component_coverage(
            _mapping(component.get("coverage")),
            f"{prefix}coverage.",
            resolution_status=ABSENT_BY_CONTRACT,
        ))
    elif status == ABSENT_USE_ALL_FEATURE_STOCKS:
        errors.extend(_exact_fields(component, _ABSENT_FIELDS, prefix))
        if role != "UNIVERSE_ARTIFACT":
            errors.append(f"{prefix}ABSENT_USE_ALL_FEATURE_STOCKS only supports UNIVERSE_ARTIFACT")
        if component.get("semantic_absence_code") != "UNIVERSE_NOT_PRESENT_USE_ALL_FEATURE_STOCKS":
            errors.append(f"{prefix}semantic_absence_code is invalid")
        errors.extend(_validate_component_coverage(
            _mapping(component.get("coverage")),
            f"{prefix}coverage.",
            resolution_status=ABSENT_USE_ALL_FEATURE_STOCKS,
        ))
    elif status == EMPTY_USE_ALL_FEATURE_STOCKS:
        errors.extend(_exact_fields(component, _EMPTY_FIELDS, prefix))
        if role != "UNIVERSE_ARTIFACT":
            errors.append(f"{prefix}EMPTY_USE_ALL_FEATURE_STOCKS only supports UNIVERSE_ARTIFACT")
        errors.extend(_hash(component.get("content_id"), f"{prefix}content_id"))
        errors.extend(_nonempty(component.get("format_contract"), f"{prefix}format_contract"))
        if component.get("member_count") != 0:
            errors.append(f"{prefix}member_count must be 0")
        errors.extend(_validate_component_coverage(
            _mapping(component.get("coverage")),
            f"{prefix}coverage.",
            resolution_status=EMPTY_USE_ALL_FEATURE_STOCKS,
        ))
    else:
        errors.append(f"{prefix}resolution_status is invalid")
    return errors


def _validate_forecast_channel_set(component: Mapping[str, Any], prefix: str) -> list[str]:
    errors = _exact_fields(component, _FORECAST_CHANNEL_SET_FIELDS, prefix)
    if component.get("member_key") != "primary":
        errors.append(f"{prefix}member_key must be primary")
    if component.get("identity_kind") != FORECAST_CHANNEL_SET_V1:
        errors.append(f"{prefix}identity_kind must be {FORECAST_CHANNEL_SET_V1}")
    if component.get("resolution_status") != RESOLVED:
        errors.append(f"{prefix}resolution_status must be RESOLVED")
    errors.extend(_hash(component.get("content_id"), f"{prefix}content_id"))
    errors.extend(_nonempty(component.get("format_contract"), f"{prefix}format_contract"))
    errors.extend(_validate_component_coverage(
        _mapping(component.get("coverage")),
        f"{prefix}coverage.",
        resolution_status=RESOLVED,
    ))
    channels = component.get("channels")
    if not isinstance(channels, list) or not channels:
        return errors + [f"{prefix}channels must be a non-empty list"]
    channel_ids: list[str] = []
    channel_indices: list[int] = []
    target_count = 0
    for channel_index, raw_channel in enumerate(channels):
        channel = _mapping(raw_channel)
        channel_prefix = f"{prefix}channels[{channel_index}]."
        errors.extend(_exact_fields(channel, _FORECAST_CHANNEL_FIELDS, channel_prefix))
        errors.extend(_nonempty(channel.get("channel_id"), f"{channel_prefix}channel_id"))
        if isinstance(channel.get("channel_id"), str):
            channel_ids.append(str(channel["channel_id"]))
        errors.extend(_non_negative_int(channel.get("channel_index"), f"{channel_prefix}channel_index"))
        if isinstance(channel.get("channel_index"), int) and not isinstance(channel.get("channel_index"), bool):
            channel_indices.append(int(channel["channel_index"]))
        channel_role = channel.get("channel_role")
        if channel_role not in _FORECAST_CHANNEL_ROLES:
            errors.append(f"{channel_prefix}channel_role is invalid")
        if channel_role == "TARGET":
            target_count += 1
        errors.extend(_nonempty(channel.get("value_contract"), f"{channel_prefix}value_contract"))
        if channel.get("missingness_policy") not in _FORECAST_MISSINGNESS_POLICIES:
            errors.append(f"{channel_prefix}missingness_policy must be explicit")
        errors.extend(_validate_forecast_temporal_availability(
            _mapping(channel.get("temporal_availability")),
            f"{channel_prefix}temporal_availability.",
        ))
    if len(channel_ids) != len(set(channel_ids)):
        errors.append(f"{prefix}channels.channel_id must be unique")
    if channel_indices != list(range(len(channels))):
        errors.append(f"{prefix}channels.channel_index must be contiguous from zero")
    if target_count != 1:
        errors.append(f"{prefix}channels must contain exactly one TARGET")
    return errors


def _validate_forecast_temporal_availability(
    temporal: Mapping[str, Any],
    prefix: str,
) -> list[str]:
    errors = _exact_fields(temporal, _FORECAST_TEMPORAL_FIELDS, prefix)
    errors.extend(_utc_timestamp(temporal.get("forecast_origin"), f"{prefix}forecast_origin"))
    errors.extend(_utc_timestamp(temporal.get("available_at"), f"{prefix}available_at"))
    errors.extend(_date_or_none(temporal.get("horizon_start"), f"{prefix}horizon_start", allow_none=False))
    errors.extend(_date_or_none(temporal.get("horizon_end"), f"{prefix}horizon_end", allow_none=False))
    forecast_origin = _parse_utc(temporal.get("forecast_origin"))
    available_at = _parse_utc(temporal.get("available_at"))
    if forecast_origin is not None and available_at is not None and available_at > forecast_origin:
        errors.append(f"{prefix}available_at must be <= forecast_origin")
    horizon_start = temporal.get("horizon_start")
    horizon_end = temporal.get("horizon_end")
    if isinstance(horizon_start, str) and isinstance(horizon_end, str) and horizon_start > horizon_end:
        errors.append(f"{prefix}horizon_start must be <= horizon_end")
    return errors


def validate_dataset_bundle(
    manifest: Mapping[str, Any],
    *,
    fundamentals_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
) -> ValidationResult:
    envelope = _mapping(manifest)
    errors = _exact_fields(envelope, _ENVELOPE_FIELDS)
    identity = _mapping(envelope.get("identity_payload"))
    errors.extend(_exact_fields(identity, _IDENTITY_FIELDS, "identity_payload."))
    if identity.get("schema_version") != SCHEMA_VERSION:
        errors.append("identity_payload.schema_version is invalid")
    if identity.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("identity_payload.canonicalization_version is invalid")
    if identity.get("identity_kind") != IDENTITY_KIND:
        errors.append("identity_payload.identity_kind is invalid")
    consumer_contract = _mapping(identity.get("consumer_contract"))
    errors.extend(_exact_fields(consumer_contract, _CONSUMER_FIELDS, "consumer_contract."))
    consumer_key = (consumer_contract.get("consumer_id"), consumer_contract.get("contract_version"))
    matrix = _CONSUMER_MATRIX.get(consumer_key)
    if matrix is None:
        errors.append("consumer_contract is unsupported")
        matrix = {}
    transformation = _mapping(identity.get("transformation_identity"))
    errors.extend(_exact_fields(transformation, _TRANSFORMATION_FIELDS, "transformation_identity."))
    errors.extend(_nonempty(transformation.get("contract_version"), "transformation_identity.contract_version"))
    blob_ids = transformation.get("git_blob_ids")
    errors.extend(_sorted_unique(blob_ids, "transformation_identity.git_blob_ids"))
    if _is_scalar_string_list(blob_ids):
        if not blob_ids:
            errors.append("transformation_identity.git_blob_ids must be non-empty")
        for index, blob_id in enumerate(blob_ids):
            errors.extend(_git_blob(blob_id, f"transformation_identity.git_blob_ids[{index}]"))
    resolution = _mapping(identity.get("resolution_semantics"))
    errors.extend(_exact_fields(resolution, _RESOLUTION_FIELDS, "resolution_semantics."))
    errors.extend(_nonempty(resolution.get("fallback_policy_version"), "resolution_semantics.fallback_policy_version"))
    if resolution.get("identity_bearing_absence_is_explicit") is not True:
        errors.append("resolution_semantics.identity_bearing_absence_is_explicit must be true")
    components = identity.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components must be a non-empty list")
        components = []
    seen: set[tuple[object, object]] = set()
    role_counts = {role: 0 for role in matrix}
    for index, raw in enumerate(components):
        component = _mapping(raw)
        role = component.get("role")
        key = (repr(role), repr(component.get("member_key")))
        if key in seen:
            errors.append("component keys must be unique")
        seen.add(key)
        if isinstance(role, str) and role in role_counts:
            role_counts[str(role)] += 1
        errors.extend(_validate_component(component, matrix.get(str(role), set()), index))
        if role == "FUNDAMENTALS_SNAPSHOT" and component.get("resolution_status") == RESOLVED:
            snapshot = _mapping((fundamentals_snapshots or {}).get(str(component.get("member_key"))))
            if not snapshot:
                errors.append("fundamentals snapshot evidence is required")
            else:
                snapshot_result = validate_fundamentals_snapshot(snapshot)
                errors.extend(snapshot_result.errors)
                if component.get("content_id") != snapshot.get("snapshot_content_id"):
                    errors.append("fundamentals content_id must match snapshot_content_id")
                if component.get("coverage") != snapshot.get("coverage"):
                    errors.append("fundamentals coverage must match snapshot coverage")
    for role, count in role_counts.items():
        if count != 1:
            errors.append(f"consumer role {role} must have exactly one record")
    if envelope.get("dataset_bundle_id") != recompute_dataset_bundle_id(envelope):
        errors.append("dataset_bundle_id must equal canonical identity payload hash")
    errors.extend(_hash(envelope.get("dataset_bundle_id"), "dataset_bundle_id"))
    return ValidationResult("EXECUTABLE" if not errors else "NOT_EXECUTABLE", errors)


def build_dataset_bundle(
    *,
    consumer_id: str,
    contract_version: str,
    components: list[Mapping[str, Any]],
    transformation_identity: Mapping[str, Any],
    resolution_semantics: Mapping[str, Any],
    fundamentals_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity_payload = {
        "schema_version": SCHEMA_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "identity_kind": IDENTITY_KIND,
        "consumer_contract": {
            "consumer_id": consumer_id,
            "contract_version": contract_version,
        },
        "components": [dict(component) for component in components],
        "transformation_identity": dict(transformation_identity),
        "resolution_semantics": dict(resolution_semantics),
    }
    manifest = {
        "dataset_bundle_id": "",
        "identity_payload": _canonical_identity_payload(identity_payload),
    }
    manifest["dataset_bundle_id"] = recompute_dataset_bundle_id(manifest)
    result = validate_dataset_bundle(manifest, fundamentals_snapshots=fundamentals_snapshots)
    if result.errors:
        raise ValueError("dataset bundle is not executable: " + "; ".join(result.errors))
    return manifest


def legacy_dataset_hash_identity(dataset_hash: str) -> dict[str, Any]:
    errors = _hash(dataset_hash, "dataset_hash")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "identity_kind": FEATURES_ARTIFACT_V1,
        "content_id": dataset_hash,
        "eligibility": LEGACY_DIAGNOSTIC_ONLY,
        "dataset_bundle_id": None,
    }


def _component_map(manifest: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    components = _mapping(manifest.get("identity_payload")).get("components")
    if not isinstance(components, list):
        return {}
    return {
        (str(component.get("role")), str(component.get("member_key"))): _mapping(component)
        for component in components
        if isinstance(component, Mapping)
    }


def component_diff_paths(requested: Mapping[str, Any], executed: Mapping[str, Any]) -> list[str]:
    req_identity = _mapping(requested.get("identity_payload"))
    exe_identity = _mapping(executed.get("identity_payload"))
    paths: set[str] = set()
    req_components = _component_map(requested)
    exe_components = _component_map(executed)
    for key in sorted(set(req_components) | set(exe_components)):
        role, member_key = key
        req_component = req_components.get(key, {})
        exe_component = exe_components.get(key, {})
        root = f"/components/{role}:{member_key}"
        for field in sorted(_COMPONENT_LEAFS):
            if req_component.get(field) != exe_component.get(field):
                paths.add(f"{root}/{field}")
        req_coverage = _mapping(req_component.get("coverage"))
        exe_coverage = _mapping(exe_component.get("coverage"))
        for field in sorted(_COVERAGE_LEAFS):
            if req_coverage.get(field) != exe_coverage.get(field):
                paths.add(f"{root}/coverage/{field}")
    if req_identity.get("transformation_identity") != exe_identity.get("transformation_identity"):
        req_transform = _mapping(req_identity.get("transformation_identity"))
        exe_transform = _mapping(exe_identity.get("transformation_identity"))
        for field in sorted(_TRANSFORMATION_FIELDS):
            if req_transform.get(field) != exe_transform.get(field):
                paths.add(f"/transformation_identity/{field}")
    if req_identity.get("resolution_semantics") != exe_identity.get("resolution_semantics"):
        req_resolution = _mapping(req_identity.get("resolution_semantics"))
        exe_resolution = _mapping(exe_identity.get("resolution_semantics"))
        for field in sorted(_RESOLUTION_FIELDS):
            if req_resolution.get(field) != exe_resolution.get(field):
                paths.add(f"/resolution_semantics/{field}")
    return sorted(paths)


def _roles_from_paths(paths: list[str]) -> list[str]:
    roles = {
        path.split("/", 3)[2].split(":", 1)[0]
        for path in paths
        if isinstance(path, str) and path.startswith("/components/") and ":" in path.split("/", 3)[2]
    }
    return sorted(roles)


def _path_allowed(reason_code: str, path: str) -> bool:
    prefixes = _REASON_ALLOWED_PREFIX.get(reason_code, ())
    if not path.startswith(prefixes):
        return False
    if reason_code == "COVERAGE_RECONCILIATION":
        return "/coverage/" in path
    return True


def _component(manifest: Mapping[str, Any], role: str) -> Mapping[str, Any]:
    return _component_map(manifest).get((role, "primary"), {})


def _validate_source_fallback(requested: Mapping[str, Any], executed: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    req_identity = _mapping(requested.get("identity_payload"))
    exe_identity = _mapping(executed.get("identity_payload"))
    consumer = _mapping(req_identity.get("consumer_contract"))
    if consumer != {"consumer_id": "M4_TRAINING_V1", "contract_version": "m4-training-dataset.v1"}:
        errors.append("SOURCE_FALLBACK supports only M4_TRAINING_V1@m4-training-dataset.v1")
    if consumer != _mapping(exe_identity.get("consumer_contract")):
        errors.append("consumer_contract must not change for SOURCE_FALLBACK")
    for field in ("transformation_identity", "resolution_semantics"):
        if req_identity.get(field) != exe_identity.get(field):
            errors.append(f"{field} must not change for SOURCE_FALLBACK")
    req_features = _component(requested, "FEATURES_ARTIFACT")
    exe_features = _component(executed, "FEATURES_ARTIFACT")
    if req_features.get("resolution_status") != RESOLVED or exe_features.get("resolution_status") != RESOLVED:
        errors.append("SOURCE_FALLBACK features must be RESOLVED -> RESOLVED")
    if req_features.get("content_id") == exe_features.get("content_id"):
        errors.append("SOURCE_FALLBACK features content_id must change")
    if _component(requested, "SIGNALS_CONFIG") != _component(executed, "SIGNALS_CONFIG"):
        errors.append("SOURCE_FALLBACK signals must not change")
    if _component(requested, "FUNDAMENTALS_SNAPSHOT").get("resolution_status") != RESOLVED:
        errors.append("SOURCE_FALLBACK requested fundamentals must be RESOLVED")
    if _component(executed, "FUNDAMENTALS_SNAPSHOT").get("resolution_status") != RESOLVED:
        errors.append("SOURCE_FALLBACK executed fundamentals must be RESOLVED")
    if "FEATURES_ARTIFACT" not in _roles_from_paths(component_diff_paths(requested, executed)):
        errors.append("SOURCE_FALLBACK changed_roles must include FEATURES_ARTIFACT")
    return errors


def validate_requested_executed_bundle_refs(
    envelope: Mapping[str, Any],
    requested_manifest: Mapping[str, Any] | None,
    executed_manifest: Mapping[str, Any] | None,
    *,
    requested_fundamentals_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    executed_fundamentals_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
) -> ValidationResult:
    errors: list[str] = []
    payload = _mapping(envelope)
    allowed_outer = set(_REQUEST_EXEC_FIELDS)
    if "resolution_delta" not in payload:
        allowed_outer.remove("resolution_delta")
    errors.extend(_exact_fields(payload, allowed_outer))
    errors.extend(_hash(payload.get("requested_dataset_bundle_id"), "requested_dataset_bundle_id"))
    errors.extend(_hash(payload.get("executed_dataset_bundle_id"), "executed_dataset_bundle_id"))
    if requested_manifest is None or executed_manifest is None:
        return ValidationResult("INVALID", errors + ["requested and executed manifests are required"])
    requested_validation = validate_dataset_bundle(
        requested_manifest,
        fundamentals_snapshots=requested_fundamentals_snapshots,
    )
    executed_validation = validate_dataset_bundle(
        executed_manifest,
        fundamentals_snapshots=executed_fundamentals_snapshots,
    )
    errors.extend(f"requested_manifest.{error}" for error in requested_validation.errors)
    errors.extend(f"executed_manifest.{error}" for error in executed_validation.errors)
    requested_id = recompute_dataset_bundle_id(requested_manifest)
    executed_id = recompute_dataset_bundle_id(executed_manifest)
    if requested_id != payload.get("requested_dataset_bundle_id"):
        errors.append("requested manifest ID does not match envelope")
    if executed_id != payload.get("executed_dataset_bundle_id"):
        errors.append("executed manifest ID does not match envelope")
    paths = component_diff_paths(requested_manifest, executed_manifest)
    ids_equal = requested_id == executed_id
    delta = payload.get("resolution_delta")
    if ids_equal and delta is not None:
        errors.append("resolution_delta must be absent when IDs are equal")
    if not ids_equal and delta is None:
        errors.append("resolution_delta is required when IDs differ")
    if delta is None:
        return ValidationResult("VALID" if not errors else "INVALID", errors)
    delta_map = _mapping(delta)
    delta_fields = set(_DELTA_BASE_FIELDS)
    if delta_map.get("reason_code") == "SOURCE_FALLBACK":
        delta_fields.add("transition_profile_version")
    errors.extend(_exact_fields(delta_map, delta_fields, "resolution_delta."))
    reason = str(delta_map.get("reason_code"))
    if reason not in _REASON_ALLOWED_PREFIX:
        errors.append("resolution_delta.reason_code is invalid")
    if reason == "SOURCE_FALLBACK" and delta_map.get("transition_profile_version") != "m4-training-source-fallback.v1":
        errors.append("resolution_delta.transition_profile_version is invalid")
    for field in ("requested_manifest_id", "executed_manifest_id"):
        errors.extend(_hash(delta_map.get(field), f"resolution_delta.{field}"))
    if delta_map.get("requested_manifest_id") != requested_id:
        errors.append("resolution_delta.requested_manifest_id mismatch")
    if delta_map.get("executed_manifest_id") != executed_id:
        errors.append("resolution_delta.executed_manifest_id mismatch")
    changed_paths = delta_map.get("changed_identity_paths")
    errors.extend(_sorted_unique(changed_paths, "resolution_delta.changed_identity_paths"))
    if _is_scalar_string_list(changed_paths):
        if not changed_paths:
            errors.append("resolution_delta.changed_identity_paths must be non-empty")
        if changed_paths != paths:
            errors.append("resolution_delta.changed_identity_paths must equal deterministic diff")
        for path in changed_paths:
            if not isinstance(path, str) or not _path_allowed(reason, path):
                errors.append(f"resolution_delta.changed_identity_paths contains disallowed path {path}")
    changed_roles = delta_map.get("changed_roles")
    errors.extend(_sorted_unique(changed_roles, "resolution_delta.changed_roles"))
    if _is_scalar_string_list(changed_paths) and _is_scalar_string_list(changed_roles) and changed_roles != _roles_from_paths(changed_paths):
        errors.append("resolution_delta.changed_roles must equal derived roles")
    errors.extend(_nonempty(delta_map.get("resolution_authority"), "resolution_delta.resolution_authority"))
    evidence_refs = delta_map.get("evidence_refs")
    errors.extend(_sorted_unique(evidence_refs, "resolution_delta.evidence_refs"))
    if _is_scalar_string_list(evidence_refs):
        if not evidence_refs:
            errors.append("resolution_delta.evidence_refs must be non-empty")
        for index, evidence_ref in enumerate(evidence_refs):
            errors.extend(_hash(evidence_ref, f"resolution_delta.evidence_refs[{index}]"))
    req_consumer = _mapping(_mapping(requested_manifest.get("identity_payload")).get("consumer_contract"))
    exe_consumer = _mapping(_mapping(executed_manifest.get("identity_payload")).get("consumer_contract"))
    if req_consumer.get("consumer_id") != exe_consumer.get("consumer_id"):
        errors.append("requested and executed consumer_id must match")
    if req_consumer.get("contract_version") != exe_consumer.get("contract_version"):
        errors.append("consumer contract_version drift requires a new TrialSpec")
    if reason == "SOURCE_FALLBACK":
        errors.extend(_validate_source_fallback(requested_manifest, executed_manifest))
    if reason == "SOURCE_UNAVAILABLE":
        roles = _roles_from_paths(paths)
        if len(roles) != 1:
            errors.append("SOURCE_UNAVAILABLE must change exactly one role")
        role = roles[0] if roles else ""
        req_component = _component(requested_manifest, role)
        exe_component = _component(executed_manifest, role)
        if req_component.get("resolution_status") != RESOLVED:
            errors.append("SOURCE_UNAVAILABLE must start from RESOLVED")
        if exe_component.get("resolution_status") not in {ABSENT_BY_CONTRACT, ABSENT_USE_ALL_FEATURE_STOCKS}:
            errors.append("SOURCE_UNAVAILABLE target must be an allowed absence variant")
    return ValidationResult("VALID" if not errors else "INVALID", errors)


def publish_dataset_bundle_manifest(
    corpus_root: Path,
    manifest: Mapping[str, Any],
    *,
    fundamentals_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
) -> WriteResult:
    identity = str(manifest["dataset_bundle_id"]).removeprefix(HASH_PREFIX)
    target = corpus_root / "dataset_bundles" / f"{identity}.json"
    result = write_immutable_json(
        target,
        manifest,
        validator=lambda payload: validate_dataset_bundle(
            payload,
            fundamentals_snapshots=fundamentals_snapshots,
        ).errors,
        identity_field="dataset_bundle_id",
    )
    return WriteResult(result.status, result.path)
