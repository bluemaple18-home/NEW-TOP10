"""Research Spine V1 的 canonical fact 契約與 identity helpers。"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any, Mapping


CANONICALIZATION_VERSION = "research-canonical-json.v1"
HASH_PREFIX = "sha256:"
TERMINAL_CAUSE_POLICY_VERSION = "research-terminal-cause-ordering.v1"

_SAFETY = {
    "does_not_train_model": True,
    "does_not_change_production_ranking": True,
    "production_promotion_allowed": False,
}
_TERMINAL_STATUSES = {
    "SUCCEEDED",
    "FAILED",
    "REJECTED_BEFORE_EXECUTION",
    "CANCELLED",
    "TIMED_OUT",
    "ABORTED",
}
_IDENTITY_STATUSES = {"EXACT", "EXPLAINED_MISMATCH", "UNEXPLAINED_MISMATCH", "NOT_EXECUTED"}
_EXECUTION_OBSERVATION_STATUSES = {"NOT_STARTED", "OBSERVED", "PARTIALLY_OBSERVED", "UNKNOWN"}
_SEALED_STATUSES = {"PROVEN_NON_SEALED", "SEALED", "UNKNOWN"}
_LINEAGE_STATUSES = {"VALID", "INVALID_LINEAGE"}
_ELIGIBILITY_STATUSES = {
    "ADAPTIVE_ELIGIBLE",
    "LEGACY_DIAGNOSTIC_ONLY",
    "SEALED_VALIDATION_ONLY",
    "TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE",
    "UNSUPPORTED_NOT_AN_OBSERVATION",
    "INVALID_LINEAGE",
}
_PARAMETER_KEYS = {
    "horizon",
    "stop_loss_pct",
    "take_profit_pct",
    "max_group_exposure",
    "regime_gate",
    "risk_guard",
    "entry_filter",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON 不允許 NaN 或 Infinity")
        value = Decimal(str(value))
    if isinstance(value, Decimal):
        normalized = format(value.normalize(), "f")
        return "0" if normalized in {"-0", ""} else normalized
    return value


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        _normalize(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def content_hash(payload: Mapping[str, Any], *, omit: set[str] | None = None) -> str:
    body = {key: value for key, value in payload.items() if key not in (omit or set())}
    return HASH_PREFIX + hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _required(payload: Mapping[str, Any], fields: set[str], prefix: str = "") -> list[str]:
    return [f"{prefix}{field} is required" for field in sorted(fields) if field not in payload]


def _exact_fields(
    payload: Mapping[str, Any], fields: set[str], prefix: str = "", *, optional: set[str] | None = None
) -> list[str]:
    errors = _required(payload, fields, prefix)
    extras = sorted(set(payload) - fields - (optional or set()))
    errors.extend(f"{prefix}{field} is not allowed" for field in extras)
    return errors


def _hash(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith(HASH_PREFIX):
        return [f"{field} must be sha256:<64 lowercase hex>"]
    if any(character not in "0123456789abcdef" for character in value[7:]):
        return [f"{field} must be sha256:<64 lowercase hex>"]
    return []


def _nonempty(value: object, field: str) -> list[str]:
    return [] if isinstance(value, str) and value.strip() else [f"{field} must be non-empty"]


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


def _relative_ref(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{field} must be non-empty relative path"]
    if value == "UNKNOWN":
        return [f"{field} must be concrete relative path"]
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return [f"{field} must be non-empty relative path"]
    return []


def _validate_safety(value: object) -> list[str]:
    safety = _mapping(value)
    errors = _exact_fields(safety, set(_SAFETY), "safety.")
    for field, expected in _SAFETY.items():
        if safety.get(field) is not expected:
            errors.append(f"safety.{field} must be {str(expected).lower()}")
    return errors


def validate_parameter_catalog(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "catalog_version",
        "canonicalization_version",
        "authority_mode",
        "dimensions",
        "validation_profiles",
        "entrypoint_defaults",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-parameter-catalog.v1":
        errors.append("schema_version is invalid")
    if payload.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("canonicalization_version is invalid")
    if payload.get("authority_mode") != "SOLE_AUTHORING_AUTHORITY":
        errors.append("authority_mode must be SOLE_AUTHORING_AUTHORITY")
    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return errors + ["dimensions must be a non-empty list"]
    dimension_fields = {
        "id",
        "name",
        "research_level",
        "product_semantics",
        "data_type",
        "coverage_values",
        "executable_values",
        "categorical_baselines",
        "execution_support",
        "runner_mapping",
        "default_value",
        "coverage_default_only",
        "stage_allowlist",
        "regime_allowlist",
        "dynamic_execution_allowed",
    }
    ids: list[str] = []
    for index, raw in enumerate(dimensions):
        row = _mapping(raw)
        errors.extend(_exact_fields(row, dimension_fields, f"dimensions[{index}]."))
        dimension_id = row.get("id")
        errors.extend(_nonempty(dimension_id, f"dimensions[{index}].id"))
        if isinstance(dimension_id, str):
            ids.append(dimension_id)
        if row.get("data_type") not in {"integer", "decimal", "categorical"}:
            errors.append(f"dimensions[{index}].data_type is invalid")
        for field in ("coverage_values", "executable_values", "categorical_baselines"):
            if not isinstance(row.get(field), list):
                errors.append(f"dimensions[{index}].{field} must be a list")
        allowed_values = list(row.get("coverage_values") or []) + list(row.get("executable_values") or [])
        if row.get("default_value") not in allowed_values:
            errors.append(f"dimensions[{index}].default_value must be declared")
        if any(value not in allowed_values for value in (row.get("categorical_baselines") or [])):
            errors.append(f"dimensions[{index}].categorical_baselines must be declared")
        if row.get("execution_support") not in {"SUPPORTED", "CONTRACT_DEPENDENT"}:
            errors.append(f"dimensions[{index}].execution_support is invalid")
        for field in ("stage_allowlist", "regime_allowlist"):
            if not isinstance(row.get(field), list):
                errors.append(f"dimensions[{index}].{field} must be a list")
        if row.get("dynamic_execution_allowed") is not False:
            errors.append(f"dimensions[{index}].dynamic_execution_allowed must be false")
    if len(ids) != len(set(ids)):
        errors.append("dimension ids must be unique")
    if set(ids) != _PARAMETER_KEYS:
        errors.append("dimension ids must equal canonical parameter set")
    profiles = payload.get("validation_profiles")
    if not isinstance(profiles, list) or not profiles:
        errors.append("validation_profiles must be a non-empty list")
    else:
        profile_fields = {
            "id",
            "title_suffix",
            "hypothesis_suffix",
            "horizon",
            "stop_loss_pct",
            "take_profit_pct",
            "max_group_exposure",
            "score_bonus",
        }
        for index, raw in enumerate(profiles):
            profile = _mapping(raw)
            errors.extend(_exact_fields(profile, profile_fields, f"validation_profiles[{index}]."))
            dimension_by_id = {
                str(row.get("id")): _mapping(row) for row in dimensions if isinstance(row, Mapping)
            }
            for parameter in _PARAMETER_KEYS.intersection(profile):
                values = profile.get(parameter)
                allowed = dimension_by_id.get(parameter, {}).get("executable_values")
                if not isinstance(values, list) or not isinstance(allowed, list) or any(
                    value not in allowed for value in values
                ):
                    errors.append(
                        f"validation_profiles[{index}].{parameter} must use executable values"
                    )
        profile_ids = {str(_mapping(profile).get("id")) for profile in profiles}
        if len(profile_ids) != len(profiles):
            errors.append("validation profile ids must be unique")
        if profile_ids != {"standard", "risk_guard", "long_horizon", "tight_exit"}:
            errors.append("validation profile ids must preserve current runner profiles")
    entrypoints = payload.get("entrypoint_defaults")
    if not isinstance(entrypoints, Mapping) or set(entrypoints) != {
        "autonomous_research",
        "strategy_matrix",
        "weekend_research_matrix",
    }:
        errors.append("entrypoint_defaults must preserve current entrypoints")
    else:
        dimensions_by_id = {
            str(row.get("id")): _mapping(row) for row in dimensions if isinstance(row, Mapping)
        }
        for entrypoint, raw_defaults in entrypoints.items():
            defaults = _mapping(raw_defaults)
            if set(defaults) != {"horizon", "stop_loss_pct", "take_profit_pct", "max_group_exposure"}:
                errors.append(f"entrypoint_defaults.{entrypoint} has invalid parameter set")
                continue
            for parameter, values in defaults.items():
                executable = dimensions_by_id.get(parameter, {}).get("executable_values")
                if not isinstance(values, list) or not isinstance(executable, list) or any(
                    value not in executable for value in values
                ):
                    errors.append(
                        f"entrypoint_defaults.{entrypoint}.{parameter} must use executable values"
                    )
    return errors


def validate_trial_spec(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "canonicalization_version",
        "trial_spec_id",
        "topic_id",
        "topic_family_id",
        "parameter_catalog_version",
        "parameter_catalog_hash",
        "parameters",
        "research_stage",
        "regime_scope",
        "dataset_authority",
        "ranking_source_authority",
        "execution_profile",
        "safety",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-trial-spec.v1":
        errors.append("schema_version is invalid")
    if payload.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("canonicalization_version is invalid")
    for field in ("topic_id", "topic_family_id", "parameter_catalog_version", "research_stage"):
        errors.extend(_nonempty(payload.get(field), field))
    for field in ("trial_spec_id", "parameter_catalog_hash"):
        errors.extend(_hash(payload.get(field), field))
    parameters = _mapping(payload.get("parameters"))
    if set(parameters) != _PARAMETER_KEYS:
        errors.append("parameters must equal canonical parameter set")
    elif any(parameters.get(field) is not None for field in ("regime_gate", "risk_guard", "entry_filter")):
        errors.append("coverage-only parameters must be null NOT_EXECUTED sentinels")
    for name in ("regime_scope", "dataset_authority", "ranking_source_authority", "execution_profile"):
        if not _mapping(payload.get(name)):
            errors.append(f"{name} must be a non-empty object")
    errors.extend(_hash(_mapping(payload.get("dataset_authority")).get("dataset_hash"), "dataset_authority.dataset_hash"))
    errors.extend(_hash(_mapping(payload.get("ranking_source_authority")).get("ranking_source_hash"), "ranking_source_authority.ranking_source_hash"))
    errors.extend(_validate_safety(payload.get("safety")))

    if not errors and payload.get("trial_spec_id") != content_hash(payload, omit={"trial_spec_id"}):
        errors.append("trial_spec_id does not match canonical content")
    return errors


def validate_research_intent(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "intent_id",
        "requested_trial_spec_ids",
        "requested_dataset_bundle_id",
        "requested_dataset_bundle_manifest_ref",
        "requested_at",
        "request_source",
        "selection_reason",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-intent.v1":
        errors.append("schema_version is invalid")
    errors.extend(_nonempty(payload.get("intent_id"), "intent_id"))
    ids = payload.get("requested_trial_spec_ids")
    if not isinstance(ids, list) or not ids:
        errors.append("requested_trial_spec_ids must be non-empty")
    else:
        for index, value in enumerate(ids):
            errors.extend(_hash(value, f"requested_trial_spec_ids[{index}]"))
    errors.extend(_hash(payload.get("requested_dataset_bundle_id"), "requested_dataset_bundle_id"))
    errors.extend(_relative_ref(payload.get("requested_dataset_bundle_manifest_ref"), "requested_dataset_bundle_manifest_ref"))
    errors.extend(_utc_timestamp(payload.get("requested_at"), "requested_at"))
    return errors


def validate_attempt_started(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "attempt_event_id",
        "run_id",
        "intent_id",
        "requested_trial_spec_ids",
        "requested_dataset_bundle_id",
        "requested_dataset_bundle_manifest_ref",
        "started_at",
        "executor",
        "invocation_hash",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-run-attempt-started.v1":
        errors.append("schema_version is invalid")
    errors.extend(_hash(payload.get("attempt_event_id"), "attempt_event_id"))
    errors.extend(_hash(payload.get("invocation_hash"), "invocation_hash"))
    errors.extend(_hash(payload.get("requested_dataset_bundle_id"), "requested_dataset_bundle_id"))
    errors.extend(_relative_ref(payload.get("requested_dataset_bundle_manifest_ref"), "requested_dataset_bundle_manifest_ref"))
    errors.extend(_utc_timestamp(payload.get("started_at"), "started_at"))
    if not errors and payload.get("attempt_event_id") != content_hash(payload, omit={"attempt_event_id"}):
        errors.append("attempt_event_id does not match canonical content")
    return errors


def validate_orphan_reconciliation(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "run_id",
        "intent_id",
        "attempt_event_id",
        "observed_at",
        "reconciliation_policy_version",
        "status",
        "sealed_usage_status",
        "facts_unknown",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-orphan-reconciliation.v1":
        errors.append("schema_version is invalid")
    if payload.get("status") != "ORPHANED_ATTEMPT":
        errors.append("status must be ORPHANED_ATTEMPT")
    if payload.get("sealed_usage_status") != "UNKNOWN":
        errors.append("orphan sealed_usage_status must be UNKNOWN")
    required_unknown = {"executed_parameters", "executed_lineage", "executed_dataset_bundle", "result"}
    if set(payload.get("facts_unknown") or []) != required_unknown:
        errors.append("facts_unknown must enumerate all unknowable execution facts")
    errors.extend(_hash(payload.get("attempt_event_id"), "attempt_event_id"))
    errors.extend(_utc_timestamp(payload.get("observed_at"), "observed_at"))
    return errors


def requested_executed_differences(payload: Mapping[str, Any]) -> set[str]:
    requested = _mapping(payload.get("requested"))
    requested_by_trial = _mapping(requested.get("parameters_by_trial"))
    units = [_mapping(unit) for unit in payload.get("executed_units", [])]
    differences: set[str] = set()
    if payload.get("artifact_errors"):
        differences.add("artifact_set")
    binding = _mapping(payload.get("bundle_binding"))
    if (
        binding.get("executed_dataset_bundle_id") not in {None, "UNKNOWN"}
        and binding.get("requested_dataset_bundle_id") != binding.get("executed_dataset_bundle_id")
    ):
        differences.add("dataset_bundle")
    unit_by_trial = {unit.get("requested_trial_spec_id"): unit for unit in units}
    requested_ids = set(requested.get("trial_spec_ids") or [])
    if requested_ids != set(unit_by_trial):
        differences.add("trial_spec_ids")
    for trial_id in requested_ids.intersection(unit_by_trial):
        unit = unit_by_trial[trial_id]
        if unit.get("executed_trial_spec_id") != trial_id:
            differences.add(f"executed_trial_spec_id.{trial_id}")
        if dict(_mapping(requested_by_trial.get(trial_id))) != dict(_mapping(unit.get("executed_parameters"))):
            differences.add(f"parameters_by_trial.{trial_id}")
        comparisons = (
            ("research_stage", "executed_research_stage"),
            ("regime_scope", "executed_regime_scope"),
        )
        for requested_field, executed_field in comparisons:
            if requested.get(requested_field) != unit.get(executed_field):
                differences.add(requested_field)
        if _mapping(requested.get("dataset_authority")).get("dataset_hash") != unit.get("executed_dataset_hash"):
            differences.add("dataset_authority")
        ranking = _mapping(_mapping(requested.get("ranking_source_authority_by_trial")).get(trial_id))
        if ranking.get("ranking_source_hash") != unit.get("executed_ranking_source_hash"):
            differences.add(f"ranking_source_authority_by_trial.{trial_id}")
        expected_profile = _mapping(_mapping(requested.get("execution_profile_by_trial")).get(trial_id))
        if dict(expected_profile) != dict(_mapping(unit.get("executed_execution_profile"))):
            differences.add(f"execution_profile_by_trial.{trial_id}")
    return differences


def select_terminal_cause(candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    """選出 receipt ownership 的 first-party terminal cause。"""
    tie_break = {
        "CANCELLED": 0,
        "TIMED_OUT": 1,
        "ABORTED": 2,
        "FAILED": 3,
        "SUCCEEDED": 4,
        "REJECTED_BEFORE_EXECUTION": 5,
    }

    def key(candidate: Mapping[str, Any]) -> tuple[datetime, int]:
        observed = _parse_utc(candidate.get("observed_at")) or datetime.max
        return observed, tie_break.get(str(candidate.get("status")), 99)

    if not candidates:
        raise ValueError("terminal cause candidates must be non-empty")
    return dict(sorted(candidates, key=key)[0])


def _validate_terminal_cause(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    terminal = payload.get("terminal_status")
    completed = _parse_utc(payload.get("completed_at"))
    cause = _mapping(payload.get("terminal_cause"))
    fields = {
        "policy_version",
        "status",
        "reason_code",
        "observed_at",
        "observer",
        "runner_started",
        "evidence_refs",
    }
    if terminal in {"CANCELLED", "TIMED_OUT", "ABORTED"} or "status_evidence" in cause:
        fields.add("status_evidence")
    errors.extend(_exact_fields(cause, fields, "terminal_cause."))
    if cause.get("policy_version") != TERMINAL_CAUSE_POLICY_VERSION:
        errors.append("terminal_cause.policy_version is invalid")
    if cause.get("status") != terminal:
        errors.append("terminal_cause.status must equal terminal_status")
    errors.extend(_nonempty(cause.get("reason_code"), "terminal_cause.reason_code"))
    errors.extend(_nonempty(cause.get("observer"), "terminal_cause.observer"))
    errors.extend(_utc_timestamp(cause.get("observed_at"), "terminal_cause.observed_at"))
    observed = _parse_utc(cause.get("observed_at"))
    if completed is not None and observed is not None and observed > completed:
        errors.append("terminal_cause.observed_at must be <= completed_at")
    evidence_refs = cause.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("terminal_cause.evidence_refs must be a non-empty list")
    else:
        for index, value in enumerate(evidence_refs):
            errors.extend(_hash(value, f"terminal_cause.evidence_refs[{index}]"))
        if len(evidence_refs) != len(set(evidence_refs)):
            errors.append("terminal_cause.evidence_refs must be unique")
    if cause.get("runner_started") is not (terminal != "REJECTED_BEFORE_EXECUTION"):
        errors.append("terminal_cause.runner_started does not match terminal semantics")
    status_evidence = _mapping(cause.get("status_evidence"))
    if terminal == "CANCELLED":
        evidence_fields = {"cancellation_request_id", "accepted_at", "typed_reason"}
        errors.extend(_exact_fields(status_evidence, evidence_fields, "terminal_cause.status_evidence."))
        errors.extend(_nonempty(status_evidence.get("cancellation_request_id"), "terminal_cause.status_evidence.cancellation_request_id"))
        errors.extend(_utc_timestamp(status_evidence.get("accepted_at"), "terminal_cause.status_evidence.accepted_at"))
        if status_evidence.get("typed_reason") != cause.get("reason_code"):
            errors.append("terminal_cause.status_evidence.typed_reason must match reason_code")
    elif terminal == "TIMED_OUT":
        evidence_fields = {"deadline_at", "timeout_policy_version", "observer_id"}
        errors.extend(_exact_fields(status_evidence, evidence_fields, "terminal_cause.status_evidence."))
        errors.extend(_utc_timestamp(status_evidence.get("deadline_at"), "terminal_cause.status_evidence.deadline_at"))
        errors.extend(_nonempty(status_evidence.get("timeout_policy_version"), "terminal_cause.status_evidence.timeout_policy_version"))
        errors.extend(_nonempty(status_evidence.get("observer_id"), "terminal_cause.status_evidence.observer_id"))
        deadline = _parse_utc(status_evidence.get("deadline_at"))
        if deadline is not None and observed is not None and deadline > observed:
            errors.append("terminal_cause.status_evidence.deadline_at must be <= observed_at")
    elif terminal == "ABORTED":
        evidence_fields = {"abort_initiator", "invariant", "supervisor_id"}
        errors.extend(_exact_fields(status_evidence, evidence_fields, "terminal_cause.status_evidence."))
        errors.extend(_nonempty(status_evidence.get("abort_initiator"), "terminal_cause.status_evidence.abort_initiator"))
        errors.extend(_nonempty(status_evidence.get("supervisor_id"), "terminal_cause.status_evidence.supervisor_id"))
        if status_evidence.get("invariant") != cause.get("reason_code"):
            errors.append("terminal_cause.status_evidence.invariant must match reason_code")
    elif "status_evidence" in cause:
        errors.append("terminal_cause.status_evidence is only allowed for CANCELLED/TIMED_OUT/ABORTED")
    return errors


def _validate_bundle_binding(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    binding = _mapping(payload.get("bundle_binding"))
    fields = {
        "requested_dataset_bundle_id",
        "requested_dataset_bundle_manifest_ref",
        "executed_dataset_bundle_id",
        "executed_dataset_bundle_manifest_ref",
        "validation_status",
    }
    if "resolution_delta" in binding:
        fields.add("resolution_delta")
    errors.extend(_exact_fields(binding, fields, "bundle_binding."))
    errors.extend(_hash(binding.get("requested_dataset_bundle_id"), "bundle_binding.requested_dataset_bundle_id"))
    errors.extend(_relative_ref(binding.get("requested_dataset_bundle_manifest_ref"), "bundle_binding.requested_dataset_bundle_manifest_ref"))
    if binding.get("executed_dataset_bundle_id") == "UNKNOWN":
        if binding.get("validation_status") != "NOT_EXECUTED":
            errors.append("bundle_binding.validation_status must be NOT_EXECUTED for UNKNOWN executed bundle")
        if binding.get("executed_dataset_bundle_manifest_ref") != "UNKNOWN":
            errors.append("bundle_binding.executed_dataset_bundle_manifest_ref must be UNKNOWN")
    else:
        errors.extend(_hash(binding.get("executed_dataset_bundle_id"), "bundle_binding.executed_dataset_bundle_id"))
        errors.extend(_relative_ref(binding.get("executed_dataset_bundle_manifest_ref"), "bundle_binding.executed_dataset_bundle_manifest_ref"))
        if binding.get("validation_status") != "VALID":
            errors.append("bundle_binding.validation_status must be VALID")
    delta = _mapping(binding.get("resolution_delta"))
    if delta:
        fields = {
            "reason_code",
            "changed_identity_paths",
            "changed_roles",
            "resolution_authority",
            "requested_manifest_id",
            "executed_manifest_id",
            "evidence_refs",
        }
        if delta.get("reason_code") == "SOURCE_FALLBACK":
            fields.add("transition_profile_version")
        errors.extend(_exact_fields(delta, fields, "bundle_binding.resolution_delta."))
        for field in ("requested_manifest_id", "executed_manifest_id"):
            errors.extend(_hash(delta.get(field), f"bundle_binding.resolution_delta.{field}"))
        for field in ("changed_identity_paths", "changed_roles", "evidence_refs"):
            values = delta.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"bundle_binding.resolution_delta.{field} must be a non-empty list")
            elif not all(isinstance(value, str) for value in values):
                errors.append(f"bundle_binding.resolution_delta.{field} entries must be strings")
        for index, value in enumerate(delta.get("evidence_refs") or []):
            errors.extend(_hash(value, f"bundle_binding.resolution_delta.evidence_refs[{index}]"))
    return errors


def validate_run_receipt(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "run_id",
        "intent_id",
        "receipt_id",
        "attempt_event_id",
        "writer_version",
        "terminal_status",
        "started_at",
        "completed_at",
        "terminal_cause",
        "bundle_binding",
        "requested",
        "executed_units",
        "resolution_events",
        "identity_match_status",
        "execution_observation_status",
        "artifacts",
        "safety",
    }
    errors = _exact_fields(payload, fields, optional={"failure", "artifact_errors"})
    if payload.get("schema_version") != "research-run-receipt.v1":
        errors.append("schema_version is invalid")
    if payload.get("terminal_status") not in _TERMINAL_STATUSES:
        errors.append("terminal_status is invalid")
    if payload.get("identity_match_status") not in _IDENTITY_STATUSES:
        errors.append("identity_match_status is invalid")
    if payload.get("execution_observation_status") not in _EXECUTION_OBSERVATION_STATUSES:
        errors.append("execution_observation_status is invalid")
    errors.extend(_hash(payload.get("receipt_id"), "receipt_id"))
    errors.extend(_hash(payload.get("attempt_event_id"), "attempt_event_id"))
    errors.extend(_utc_timestamp(payload.get("started_at"), "started_at"))
    errors.extend(_utc_timestamp(payload.get("completed_at"), "completed_at"))
    errors.extend(_validate_safety(payload.get("safety")))
    started = _parse_utc(payload.get("started_at"))
    completed = _parse_utc(payload.get("completed_at"))
    if started is not None and completed is not None and completed < started:
        errors.append("completed_at must be >= started_at")
    errors.extend(_validate_terminal_cause(payload))
    errors.extend(_validate_bundle_binding(payload))

    artifacts = payload.get("artifacts")
    artifact_ids: set[str] = set()
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
        artifacts = []
    artifact_fields = {"artifact_id", "corpus_path", "provenance_path", "validation_status"}
    for index, raw in enumerate(artifacts):
        artifact = _mapping(raw)
        errors.extend(_exact_fields(artifact, artifact_fields, f"artifacts[{index}]."))
        errors.extend(_hash(artifact.get("artifact_id"), f"artifacts[{index}].artifact_id"))
        artifact_id = str(artifact.get("artifact_id") or "")
        digest = artifact_id.removeprefix(HASH_PREFIX)
        corpus_value = str(artifact.get("corpus_path") or "")
        corpus = PurePosixPath(corpus_value)
        if (
            corpus.is_absolute()
            or ".." in corpus.parts
            or corpus.parts != ("source_corpus", "sha256", digest)
        ):
            errors.append(f"artifacts[{index}].corpus_path must match artifact digest")
        if artifact.get("validation_status") not in {"VALID", "INVALID"}:
            errors.append(f"artifacts[{index}].validation_status is invalid")
        artifact_ids.add(artifact_id)
    if len(artifact_ids) != len(artifacts):
        errors.append("artifact_id must be unique")
    artifact_errors = payload.get("artifact_errors") or []
    if not isinstance(artifact_errors, list):
        errors.append("artifact_errors must be a list")
        artifact_errors = []
    error_fields = {
        "artifact_id", "corpus_path", "provenance_path", "validation_status", "reason_code"
    }
    for index, raw in enumerate(artifact_errors):
        artifact = _mapping(raw)
        errors.extend(_exact_fields(artifact, error_fields, f"artifact_errors[{index}]."))
        if artifact.get("validation_status") != "INVALID":
            errors.append(f"artifact_errors[{index}].validation_status must be INVALID")
        errors.extend(_hash(artifact.get("artifact_id"), f"artifact_errors[{index}].artifact_id"))
        digest = str(artifact.get("artifact_id") or "").removeprefix(HASH_PREFIX)
        corpus_value = str(artifact.get("corpus_path") or "")
        corpus = PurePosixPath(corpus_value)
        if (
            corpus.is_absolute()
            or ".." in corpus.parts
            or corpus.parts != ("source_corpus", "sha256", digest)
        ):
            errors.append(f"artifact_errors[{index}].corpus_path must match artifact digest")
        if artifact.get("artifact_id") not in artifact_ids:
            errors.append(f"artifact_errors[{index}].artifact_id must reference artifacts")

    requested = _mapping(payload.get("requested"))
    requested_fields = {
        "trial_spec_ids",
        "dataset_bundle_id",
        "dataset_bundle_manifest_ref",
        "parameters_by_trial",
        "research_stage",
        "regime_scope",
        "dataset_authority",
        "ranking_source_authority_by_trial",
        "execution_profile_by_trial",
    }
    errors.extend(_exact_fields(requested, requested_fields, "requested."))
    requested_ids_list = requested.get("trial_spec_ids")
    if not isinstance(requested_ids_list, list) or not requested_ids_list:
        errors.append("requested.trial_spec_ids must be non-empty")
        requested_ids_list = []
    for index, value in enumerate(requested_ids_list):
        errors.extend(_hash(value, f"requested.trial_spec_ids[{index}]"))
    if len(requested_ids_list) != len(set(requested_ids_list)):
        errors.append("requested.trial_spec_ids must be unique")
    binding = _mapping(payload.get("bundle_binding"))
    errors.extend(_hash(requested.get("dataset_bundle_id"), "requested.dataset_bundle_id"))
    errors.extend(_relative_ref(requested.get("dataset_bundle_manifest_ref"), "requested.dataset_bundle_manifest_ref"))
    if requested.get("dataset_bundle_id") != binding.get("requested_dataset_bundle_id"):
        errors.append("requested.dataset_bundle_id must match bundle_binding")
    if requested.get("dataset_bundle_manifest_ref") != binding.get("requested_dataset_bundle_manifest_ref"):
        errors.append("requested.dataset_bundle_manifest_ref must match bundle_binding")
    requested_parameters = _mapping(requested.get("parameters_by_trial"))
    if set(requested_parameters) != set(requested_ids_list):
        errors.append("requested.parameters_by_trial keys must equal trial_spec_ids")
    for trial_id, parameters in requested_parameters.items():
        if set(_mapping(parameters)) != _PARAMETER_KEYS:
            errors.append(f"requested.parameters_by_trial.{trial_id} must equal canonical parameter set")
        elif any(_mapping(parameters).get(field) is not None for field in ("regime_gate", "risk_guard", "entry_filter")):
            errors.append(f"requested.parameters_by_trial.{trial_id} coverage-only parameters must be null")
    if set(_mapping(requested.get("ranking_source_authority_by_trial"))) != set(requested_ids_list):
        errors.append("requested.ranking_source_authority_by_trial keys must equal trial_spec_ids")
    if set(_mapping(requested.get("execution_profile_by_trial"))) != set(requested_ids_list):
        errors.append("requested.execution_profile_by_trial keys must equal trial_spec_ids")
    units = payload.get("executed_units")
    if not isinstance(units, list):
        errors.append("executed_units must be a list")
        units = []
    unit_fields = {
        "execution_unit_id",
        "requested_trial_spec_id",
        "executed_trial_spec_id",
        "executed_parameters",
        "executed_research_stage",
        "executed_regime_scope",
        "executed_dataset_hash",
        "executed_dataset_bundle_id",
        "executed_dataset_bundle_manifest_ref",
        "executed_ranking_source_hash",
        "executed_execution_profile",
        "lineage",
        "lineage_assertions",
        "lineage_resolution_status",
        "artifact_refs",
    }
    lineage_fields = {"lineage_id", "sealed_usage_status", "episode_ids", "episode_authority_hash"}
    valid_artifact_ids = {
        str(_mapping(item).get("artifact_id"))
        for item in artifacts
        if _mapping(item).get("validation_status") == "VALID"
    }
    for index, raw in enumerate(units):
        unit = _mapping(raw)
        errors.extend(_exact_fields(unit, unit_fields, f"executed_units[{index}]."))
        errors.extend(_hash(unit.get("execution_unit_id"), f"executed_units[{index}].execution_unit_id"))
        errors.extend(_hash(unit.get("requested_trial_spec_id"), f"executed_units[{index}].requested_trial_spec_id"))
        errors.extend(_hash(unit.get("executed_trial_spec_id"), f"executed_units[{index}].executed_trial_spec_id"))
        if set(_mapping(unit.get("executed_parameters"))) != _PARAMETER_KEYS:
            errors.append(f"executed_units[{index}].executed_parameters must equal canonical parameter set")
        elif any(_mapping(unit.get("executed_parameters")).get(field) is not None for field in ("regime_gate", "risk_guard", "entry_filter")):
            errors.append(f"executed_units[{index}].executed_parameters coverage-only parameters must be null")
        refs = unit.get("artifact_refs")
        errors.extend(_hash(unit.get("executed_dataset_bundle_id"), f"executed_units[{index}].executed_dataset_bundle_id"))
        errors.extend(_relative_ref(unit.get("executed_dataset_bundle_manifest_ref"), f"executed_units[{index}].executed_dataset_bundle_manifest_ref"))
        if binding.get("executed_dataset_bundle_id") != unit.get("executed_dataset_bundle_id"):
            errors.append(f"executed_units[{index}].executed_dataset_bundle_id must match bundle_binding")
        if binding.get("executed_dataset_bundle_manifest_ref") != unit.get("executed_dataset_bundle_manifest_ref"):
            errors.append(f"executed_units[{index}].executed_dataset_bundle_manifest_ref must match bundle_binding")
        if not isinstance(refs, list) or not refs or any(ref not in valid_artifact_ids for ref in refs):
            errors.append(f"executed_units[{index}].artifact_refs must reference valid artifacts")
        lineage = _mapping(unit.get("lineage"))
        errors.extend(_exact_fields(lineage, lineage_fields, f"executed_units[{index}].lineage."))
        errors.extend(_hash(lineage.get("lineage_id"), f"executed_units[{index}].lineage.lineage_id"))
        errors.extend(_hash(lineage.get("episode_authority_hash"), f"executed_units[{index}].lineage.episode_authority_hash"))
        sealed = lineage.get("sealed_usage_status")
        resolution = unit.get("lineage_resolution_status")
        if sealed not in _SEALED_STATUSES:
            errors.append(f"executed_units[{index}].lineage.sealed_usage_status is invalid")
        if resolution not in _LINEAGE_STATUSES:
            errors.append(f"executed_units[{index}].lineage_resolution_status is invalid")
        assertions = unit.get("lineage_assertions")
        if not isinstance(assertions, list) or not assertions:
            errors.append(f"executed_units[{index}].lineage_assertions must be non-empty")
        elif any(
            _exact_fields(_mapping(item), {"authority", "authority_hash", "facts"})
            for item in assertions
        ):
            errors.append(f"executed_units[{index}].lineage_assertions are invalid")
        else:
            asserted: dict[str, bytes] = {}
            conflict = False
            for assertion in assertions:
                assertion = _mapping(assertion)
                errors.extend(_nonempty(assertion.get("authority"), f"executed_units[{index}].lineage_assertions.authority"))
                errors.extend(_hash(assertion.get("authority_hash"), f"executed_units[{index}].lineage_assertions.authority_hash"))
                if assertion.get("authority_hash") not in refs:
                    errors.append(
                        f"executed_units[{index}].lineage_assertions.authority_hash must reference unit artifact_refs"
                    )
                facts = _mapping(assertion.get("facts"))
                protected = {
                    "sealed_usage_status", "research_stage", "dataset_hash", "ranking_source_hash",
                    "regime_scope", "episode_ids",
                }
                extras = sorted(set(facts) - protected)
                if extras:
                    errors.append(f"executed_units[{index}].lineage_assertions facts contain unsupported fields")
                for field, value in facts.items():
                    encoded = canonical_json_bytes({"value": value})
                    if field in asserted and asserted[field] != encoded:
                        conflict = True
                    asserted[field] = encoded
            if conflict and (resolution != "INVALID_LINEAGE" or sealed != "UNKNOWN"):
                errors.append(f"executed_units[{index}] authority conflict must fail closed")
            required_claims = {
                "sealed_usage_status": sealed,
                "research_stage": unit.get("executed_research_stage"),
                "dataset_hash": unit.get("executed_dataset_hash"),
                "ranking_source_hash": unit.get("executed_ranking_source_hash"),
                "regime_scope": unit.get("executed_regime_scope"),
                "episode_ids": lineage.get("episode_ids"),
            }
            unsupported_claims = [
                field
                for field, value in required_claims.items()
                if asserted.get(field) != canonical_json_bytes({"value": value})
            ]
            if unsupported_claims and (resolution != "INVALID_LINEAGE" or sealed != "UNKNOWN"):
                errors.append(f"executed_units[{index}] resolved lineage claims lack authority support")
    if payload.get("terminal_status") == "SUCCEEDED" and not units:
        errors.append("successful receipt requires executed_units")
    if payload.get("terminal_status") == "SUCCEEDED" and payload.get("execution_observation_status") != "OBSERVED":
        errors.append("successful receipt requires OBSERVED execution facts")
    if not units and payload.get("execution_observation_status") == "OBSERVED":
        errors.append("OBSERVED execution facts require executed_units")
    terminal = payload.get("terminal_status")
    observation = payload.get("execution_observation_status")
    if terminal == "REJECTED_BEFORE_EXECUTION" and (units or observation != "NOT_STARTED"):
        errors.append("REJECTED_BEFORE_EXECUTION requires NOT_STARTED and no units")
    if terminal in {"CANCELLED", "TIMED_OUT", "ABORTED"} and observation not in {"UNKNOWN", "PARTIALLY_OBSERVED", "OBSERVED"}:
        errors.append(f"{terminal} requires controlled terminal observation status")
    if terminal == "FAILED" and units and observation not in {"PARTIALLY_OBSERVED", "OBSERVED"}:
        errors.append("FAILED with units requires observed or partially observed facts")
    if terminal == "FAILED" and not units and observation not in {"UNKNOWN", "NOT_STARTED"}:
        errors.append("FAILED without units requires UNKNOWN or NOT_STARTED facts")
    if payload.get("terminal_status") != "SUCCEEDED" and not _mapping(payload.get("failure")):
        errors.append("non-success receipt requires failure")
    elif payload.get("terminal_status") != "SUCCEEDED":
        failure = _mapping(payload.get("failure"))
        errors.extend(_exact_fields(failure, {"reason_code"}, "failure."))
        errors.extend(_nonempty(failure.get("reason_code"), "failure.reason_code"))
    if payload.get("terminal_status") == "SUCCEEDED" and "failure" in payload:
        errors.append("successful receipt must not contain failure")
    unit_trial_ids = [unit.get("requested_trial_spec_id") for unit in map(_mapping, units)]
    if len(unit_trial_ids) != len(set(unit_trial_ids)):
        errors.append("requested_trial_spec_id must map to exactly one executed unit")
    unit_ids = [unit.get("execution_unit_id") for unit in map(_mapping, units)]
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("execution_unit_id must be unique")
    if not units and binding.get("executed_dataset_bundle_id") != "UNKNOWN":
        errors.append("non-executed receipt must keep executed dataset bundle UNKNOWN")
    if units and binding.get("executed_dataset_bundle_id") == "UNKNOWN":
        errors.append("executed receipt requires executed dataset bundle")

    differences = requested_executed_differences(payload) if units else set()
    events = payload.get("resolution_events") if isinstance(payload.get("resolution_events"), list) else []
    event_fields = {str(_mapping(event).get("field")) for event in events}
    for index, event in enumerate(events):
        errors.extend(
            _exact_fields(
                _mapping(event),
                {"reason_code", "field", "requested", "executed"},
                f"resolution_events[{index}].",
            )
        )
    if len(event_fields) != len(events):
        errors.append("resolution_events must not duplicate fields")
    if differences != event_fields:
        errors.append("resolution_events must exactly disclose requested/executed differences")
    expected_status = "EXACT" if not differences and units else "EXPLAINED_MISMATCH" if differences else "NOT_EXECUTED"
    if payload.get("identity_match_status") != expected_status:
        errors.append(f"identity_match_status must be {expected_status}")
    if not errors and payload.get("receipt_id") != content_hash(payload, omit={"receipt_id"}):
        errors.append("receipt_id does not match canonical content")
    return errors


def validate_migration_manifest(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "migration_id",
        "parser_version",
        "semantic_identity_policy_version",
        "duplicate_policy",
        "conflict_policy",
        "generated_at",
        "sources",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-ledger-migration-manifest.v1":
        errors.append("schema_version is invalid")
    errors.extend(_utc_timestamp(payload.get("generated_at"), "generated_at"))
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return errors + ["sources must be a list"]
    source_fields = {
        "source_artifact_hash",
        "source_artifact_path",
        "corpus_artifact_path",
        "corpus_artifact_hash",
        "record_mapping_hash",
        "classification",
        "reason_codes",
    }
    for index, raw in enumerate(sources):
        source = _mapping(raw)
        errors.extend(_exact_fields(source, source_fields, f"sources[{index}]."))
        for field in ("source_artifact_hash", "corpus_artifact_hash", "record_mapping_hash"):
            errors.extend(_hash(source.get(field), f"sources[{index}].{field}"))
        if source.get("classification") not in _ELIGIBILITY_STATUSES:
            errors.append(f"sources[{index}].classification is invalid")
        corpus_path = source.get("corpus_artifact_path")
        digest = str(source.get("corpus_artifact_hash") or "").removeprefix(HASH_PREFIX)
        if not isinstance(corpus_path, str):
            errors.append(f"sources[{index}].corpus_artifact_path must reference immutable CAS")
        else:
            path = PurePosixPath(corpus_path)
            if path.is_absolute() or ".." in path.parts or path.parts[-3:-1] != ("source_corpus", "sha256") or path.name != digest:
                errors.append(f"sources[{index}].corpus_artifact_path must reference immutable CAS")
    return errors


def validate_migration_manifest_v2(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version", "migration_id", "parser_version",
        "semantic_identity_policy_version", "eligibility_preclassification_policy_version",
        "source_authority_order_version", "duplicate_policy", "conflict_policy", "sources",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-ledger-migration-manifest.v2":
        errors.append("schema_version is invalid")
    for field in (
        "migration_id", "parser_version", "semantic_identity_policy_version",
        "eligibility_preclassification_policy_version", "source_authority_order_version",
    ):
        if field == "migration_id":
            errors.extend(_hash(payload.get(field), field))
        else:
            errors.extend(_nonempty(payload.get(field), field))
    if payload.get("duplicate_policy") != "SEMANTIC_EVIDENCE_DEWEIGHT":
        errors.append("duplicate_policy is invalid")
    if payload.get("conflict_policy") != "FAIL_CLOSED_NO_WINNER":
        errors.append("conflict_policy is invalid")
    source_fields = {
        "source_artifact_hash", "corpus_artifact_path", "source_type", "parser_version",
        "record_mapping_path", "record_mapping_hash", "record_counts",
        "classification_counts", "reason_code_counts",
    }
    sources = payload.get("sources")
    if not isinstance(sources, list):
        errors.append("sources must be a list")
        sources = []
    for index, raw in enumerate(sources):
        source = _mapping(raw)
        errors.extend(_exact_fields(source, source_fields, f"sources[{index}]."))
        for field in ("source_artifact_hash", "record_mapping_hash"):
            errors.extend(_hash(source.get(field), f"sources[{index}].{field}"))
        if source.get("source_type") not in {
            "RUN_HISTORY_JSONL", "RUN_HISTORY_JSON", "STRATEGY_MATRIX",
            "AUTONOMOUS_RUN", "REGIME_AUTHORITY", "DEVELOPMENT_AUTHORITY",
        }:
            errors.append(f"sources[{index}].source_type is invalid")
        if source.get("parser_version") != payload.get("parser_version"):
            errors.append(f"sources[{index}].parser_version mismatch")
        for field in ("corpus_artifact_path", "record_mapping_path"):
            value = source.get(field)
            if not isinstance(value, str):
                errors.append(f"sources[{index}].{field} is invalid")
                continue
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"sources[{index}].{field} is invalid")
        expected_mapping_name = str(source.get("record_mapping_hash") or "").removeprefix(HASH_PREFIX)
        if isinstance(source.get("record_mapping_path"), str):
            mapping_path = PurePosixPath(source["record_mapping_path"])
            if mapping_path.parts[-2:-1] != ("records",) or mapping_path.name != f"{expected_mapping_name}.jsonl":
                errors.append(f"sources[{index}].record_mapping_path is not canonical")
        counts = _mapping(source.get("record_counts"))
        errors.extend(_exact_fields(counts, {"seen", "mapped", "excluded"}, f"sources[{index}].record_counts."))
        if any(not isinstance(counts.get(field), int) or counts.get(field, -1) < 0 for field in ("seen", "mapped", "excluded")):
            errors.append(f"sources[{index}].record_counts must be non-negative integers")
        elif counts.get("seen") != counts.get("mapped") + counts.get("excluded"):
            errors.append(f"sources[{index}].record_counts do not reconcile")
        classifications = _mapping(source.get("classification_counts"))
        if any(key not in _ELIGIBILITY_STATUSES or not isinstance(value, int) or value < 0 for key, value in classifications.items()):
            errors.append(f"sources[{index}].classification_counts is invalid")
        elif sum(classifications.values()) != (counts.get("mapped") or 0):
            errors.append(f"sources[{index}].classification_counts do not reconcile")
        reasons = _mapping(source.get("reason_code_counts"))
        if any(not isinstance(key, str) or not key or not isinstance(value, int) or value < 0 for key, value in reasons.items()):
            errors.append(f"sources[{index}].reason_code_counts is invalid")
    if not errors and payload.get("migration_id") != content_hash(payload, omit={"migration_id"}):
        errors.append("migration_id does not match canonical content")
    return errors


def validate_migrated_record(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version", "migration_record_id", "parser_version", "source", "record_kind",
        "legacy_identity", "parameters", "metrics", "preliminary_classification",
        "reason_codes", "semantic_evidence_id",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-migrated-record.v1":
        errors.append("schema_version is invalid")
    errors.extend(_hash(payload.get("migration_record_id"), "migration_record_id"))
    if payload.get("preliminary_classification") not in {
        "LEGACY_DIAGNOSTIC_ONLY", "SEALED_VALIDATION_ONLY",
        "TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE", "UNSUPPORTED_NOT_AN_OBSERVATION",
        "INVALID_LINEAGE",
    }:
        errors.append("preliminary_classification is invalid")
    if payload.get("record_kind") not in {
        "PARAMETER_RESULT", "TOPIC_SUMMARY", "UNSUPPORTED_COORDINATE",
        "EXECUTION_SUMMARY", "UNRESOLVED_RECORD",
    }:
        errors.append("record_kind is invalid")
    source = _mapping(payload.get("source"))
    errors.extend(_exact_fields(source, {"artifact_id", "source_type", "record_locator"}, "source."))
    errors.extend(_hash(source.get("artifact_id"), "source.artifact_id"))
    if source.get("source_type") not in {
        "RUN_HISTORY_JSONL", "RUN_HISTORY_JSON", "STRATEGY_MATRIX",
        "AUTONOMOUS_RUN", "REGIME_AUTHORITY", "DEVELOPMENT_AUTHORITY",
    }:
        errors.append("source.source_type is invalid")
    errors.extend(_nonempty(source.get("record_locator"), "source.record_locator"))
    errors.extend(_nonempty(payload.get("parser_version"), "parser_version"))
    semantic = payload.get("semantic_evidence_id")
    if semantic is not None:
        errors.extend(_hash(semantic, "semantic_evidence_id"))
    if (
        not isinstance(payload.get("reason_codes"), list)
        or not payload.get("reason_codes")
        or any(not isinstance(value, str) or not value for value in payload.get("reason_codes") or [])
    ):
        errors.append("reason_codes must be non-empty")
    parameters = payload.get("parameters")
    if parameters is not None:
        expected_parameters = {
            "horizon", "stop_loss_pct", "take_profit_pct", "max_group_exposure",
            "regime_gate", "risk_guard", "entry_filter",
        }
        errors.extend(_exact_fields(_mapping(parameters), expected_parameters, "parameters."))
    metrics = payload.get("metrics")
    if metrics is not None:
        expected_metrics = {
            "total_return", "max_drawdown", "win_rate", "avg_trade_return",
            "trade_count", "score", "p_value", "robust_neighbor_pass_count",
        }
        errors.extend(_exact_fields(_mapping(metrics), expected_metrics, "metrics."))
    if payload.get("record_kind") == "PARAMETER_RESULT" and (parameters is None or metrics is None or semantic is None):
        errors.append("PARAMETER_RESULT requires parameters, metrics, and semantic_evidence_id")
    return errors


def validate_observation_identity(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "observation_id",
        "identity_policy_version",
        "origin_execution_id",
        "executed_trial_identity",
        "executed_lineage_id",
        "evidence_unit_id",
        "result_unit_id",
        "metric_policy_version",
        "attempt_inclusion_policy_version",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-observation-identity.v1":
        errors.append("schema_version is invalid")
    for field in (
        "observation_id",
        "origin_execution_id",
        "executed_trial_identity",
        "executed_lineage_id",
        "evidence_unit_id",
    ):
        errors.extend(_hash(payload.get(field), field))
    for field in (
        "identity_policy_version",
        "result_unit_id",
        "metric_policy_version",
        "attempt_inclusion_policy_version",
    ):
        errors.extend(_nonempty(payload.get(field), field))
    if not errors and payload.get("observation_id") != content_hash(payload, omit={"observation_id"}):
        errors.append("observation_id does not match canonical content")
    return errors


def projection_identity(payload: Mapping[str, Any]) -> str:
    identity = {
        key: payload.get(key)
        for key in (
            "projection_type",
            "projection_schema_version",
            "input_corpus_hash",
            "parameter_catalog_version",
            "parameter_catalog_hash",
            "canonicalization_version",
            "eligibility_policy_version",
            "failure_classifier_version",
            "learning_policy_version",
            "metric_policy_version",
            "attempt_inclusion_policy_version",
            "migration_semantic_policy_version",
        )
    }
    return content_hash(identity)


def validate_projection_provenance(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "projection_id",
        "projection_type",
        "projection_schema_version",
        "input_corpus_hash",
        "parameter_catalog_version",
        "parameter_catalog_hash",
        "canonicalization_version",
        "eligibility_policy_version",
        "failure_classifier_version",
        "learning_policy_version",
        "metric_policy_version",
        "attempt_inclusion_policy_version",
        "migration_semantic_policy_version",
        "generated_at",
        "output_artifact_path",
        "output_artifact_hash",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != "research-projection-provenance.v1":
        errors.append("schema_version is invalid")
    if payload.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("canonicalization_version is invalid")
    for field in ("projection_id", "input_corpus_hash", "parameter_catalog_hash", "output_artifact_hash"):
        errors.extend(_hash(payload.get(field), field))
    errors.extend(_utc_timestamp(payload.get("generated_at"), "generated_at"))
    expected_id = projection_identity(payload)
    if payload.get("projection_id") != expected_id:
        errors.append("projection_id does not match corpus and policy identity")
    projection_type = str(payload.get("projection_type") or "").lower()
    expected_path = f"artifacts/autonomous_research/projections/{projection_type}/{expected_id[7:]}.json"
    if payload.get("output_artifact_path") != expected_path:
        errors.append("output_artifact_path must be content-addressed by projection_id")
    return errors
