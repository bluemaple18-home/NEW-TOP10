"""Vendor-neutral forecast contract validators."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any, Mapping

from app.research.contracts import CANONICALIZATION_VERSION, content_hash


HASH_PREFIX = "sha256:"
FORECAST_TRIAL_SPEC_VERSION = "forecast-trial-spec.v1"
FORECAST_ARTIFACT_RECEIPT_VERSION = "forecast-artifact-receipt.v1"
FORECAST_EVALUATION_OBSERVATION_VERSION = "forecast-evaluation-observation.v1"

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STRATEGY_PARAMETER_KEYS = {
    "parameters",
    "ranking_source_authority",
    "stop_loss_pct",
    "take_profit_pct",
    "max_group_exposure",
    "regime_gate",
    "risk_guard",
    "entry_filter",
}
_SAFETY = {
    "does_not_train_model": True,
    "does_not_change_production_ranking": True,
    "production_promotion_allowed": False,
}
_EFFECTIVE_USAGE_STATUSES = {
    "RESEARCH_ONLY",
    "SHADOW_BENCHMARK_ONLY",
    "NO_PRODUCTION_SIGNAL_EXPORT",
    "NO_B_DECISION_CONSUMPTION",
    "NO_M4_M5_M6_M7_MUTATION",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _exact_fields(
    payload: Mapping[str, Any],
    fields: set[str],
    prefix: str = "",
    *,
    optional: set[str] | None = None,
) -> list[str]:
    errors = [f"{prefix}{field} is required" for field in sorted(fields) if field not in payload]
    errors.extend(f"{prefix}{field} is not allowed" for field in sorted(set(payload) - fields - (optional or set())))
    return errors


def _hash(value: object, field: str) -> list[str]:
    return [] if isinstance(value, str) and _HASH_RE.match(value) else [f"{field} must be sha256:<64 lowercase hex>"]


def _nonempty(value: object, field: str) -> list[str]:
    return [] if isinstance(value, str) and value.strip() else [f"{field} must be non-empty"]


def _sorted_unique(values: object, field: str) -> list[str]:
    if not isinstance(values, list):
        return [f"{field} must be a list"]
    if not all(isinstance(value, str) for value in values):
        return [f"{field} entries must be strings"]
    if values != sorted(values) or len(values) != len(set(values)):
        return [f"{field} must be sorted and unique"]
    return []


def _nonempty_unique_strings(values: object, field: str) -> list[str]:
    if not isinstance(values, list):
        return [f"{field} must be a list"]
    if not all(isinstance(value, str) for value in values):
        return [f"{field} entries must be strings"]
    if not values:
        return [f"{field} must be non-empty"]
    if any(not value.strip() for value in values):
        return [f"{field} entries must be non-empty"]
    if len(values) != len(set(values)):
        return [f"{field} entries must be unique"]
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


def _relative_ref(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{field} must be non-empty relative path"]
    if value == "UNKNOWN":
        return [f"{field} must be concrete relative path"]
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return [f"{field} must be non-empty relative path"]
    return []


def _positive_int(value: object, field: str) -> list[str]:
    return [] if isinstance(value, int) and value > 0 and not isinstance(value, bool) else [f"{field} must be positive integer"]


def _decimal_string(value: object, field: str) -> list[str]:
    if not isinstance(value, str):
        return [f"{field} must be decimal string"]
    try:
        number = Decimal(value)
    except InvalidOperation:
        return [f"{field} must be decimal string"]
    if not number.is_finite():
        return [f"{field} must be finite decimal string"]
    return []


def _validate_quantile_levels(values: object, field: str) -> list[str]:
    if not isinstance(values, list):
        return [f"{field} must be a list"]
    if not values:
        return [f"{field} must be non-empty"]
    if not all(isinstance(value, str) for value in values):
        return [f"{field} entries must be strings"]
    errors: list[str] = []
    decimals: list[Decimal] = []
    for index, value in enumerate(values):
        item_field = f"{field}[{index}]"
        try:
            number = Decimal(value)
        except InvalidOperation:
            errors.append(f"{item_field} must be decimal string")
            continue
        if not number.is_finite():
            errors.append(f"{item_field} must be finite decimal string")
            continue
        if number <= 0 or number >= 1:
            errors.append(f"{item_field} must be between 0 and 1")
        decimals.append(number)
    if decimals and (decimals != sorted(decimals) or len(decimals) != len(set(decimals))):
        errors.append(f"{field} must be numerically sorted and unique")
    return errors


def _validate_effective_usage_statuses(values: object, field: str) -> list[str]:
    errors = _sorted_unique(values, field)
    if isinstance(values, list) and all(isinstance(value, str) for value in values):
        if set(values) != _EFFECTIVE_USAGE_STATUSES:
            errors.append(f"{field} must exactly match allowed research statuses")
    return errors


def _validate_safety(value: object) -> list[str]:
    safety = _mapping(value)
    errors = _exact_fields(safety, set(_SAFETY), "safety.")
    for field, expected in _SAFETY.items():
        if safety.get(field) is not expected:
            errors.append(f"safety.{field} must be {str(expected).lower()}")
    return errors


def _strategy_pollution_errors(payload: Mapping[str, Any]) -> list[str]:
    polluted = sorted(set(payload).intersection(_STRATEGY_PARAMETER_KEYS))
    if polluted:
        return ["strategy parameters are not allowed in forecast trial spec"]
    return []


def validate_forecast_trial_spec(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "canonicalization_version",
        "forecast_trial_spec_id",
        "dataset_bundle_id",
        "dataset_bundle_manifest_ref",
        "forecast_origin",
        "horizon",
        "target_channel_ids",
        "covariate_channel_ids",
        "prediction_contract",
        "evaluation_contract",
        "artifact_contract",
        "execution_profile",
        "safety",
    }
    errors = _exact_fields(payload, fields)
    errors.extend(_strategy_pollution_errors(payload))
    if payload.get("schema_version") != FORECAST_TRIAL_SPEC_VERSION:
        errors.append("schema_version is invalid")
    if payload.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("canonicalization_version is invalid")
    errors.extend(_hash(payload.get("forecast_trial_spec_id"), "forecast_trial_spec_id"))
    errors.extend(_hash(payload.get("dataset_bundle_id"), "dataset_bundle_id"))
    errors.extend(_relative_ref(payload.get("dataset_bundle_manifest_ref"), "dataset_bundle_manifest_ref"))
    errors.extend(_utc_timestamp(payload.get("forecast_origin"), "forecast_origin"))
    horizon = _mapping(payload.get("horizon"))
    errors.extend(_exact_fields(horizon, {"unit", "steps"}, "horizon."))
    if horizon.get("unit") not in {"calendar_day", "trading_day"}:
        errors.append("horizon.unit is invalid")
    errors.extend(_positive_int(horizon.get("steps"), "horizon.steps"))
    errors.extend(_nonempty_unique_strings(payload.get("target_channel_ids"), "target_channel_ids"))
    errors.extend(_sorted_unique(payload.get("covariate_channel_ids"), "covariate_channel_ids"))
    prediction = _mapping(payload.get("prediction_contract"))
    errors.extend(_exact_fields(prediction, {"point", "quantiles"}, "prediction_contract."))
    point = _mapping(prediction.get("point"))
    quantiles = _mapping(prediction.get("quantiles"))
    errors.extend(_exact_fields(point, {"artifact_contract"}, "prediction_contract.point."))
    errors.extend(_nonempty(point.get("artifact_contract"), "prediction_contract.point.artifact_contract"))
    errors.extend(_exact_fields(quantiles, {"levels", "artifact_contract"}, "prediction_contract.quantiles."))
    errors.extend(_validate_quantile_levels(quantiles.get("levels"), "prediction_contract.quantiles.levels"))
    errors.extend(_nonempty(quantiles.get("artifact_contract"), "prediction_contract.quantiles.artifact_contract"))
    evaluation = _mapping(payload.get("evaluation_contract"))
    errors.extend(_exact_fields(evaluation, {"metric_policy_version"}, "evaluation_contract."))
    errors.extend(_nonempty(evaluation.get("metric_policy_version"), "evaluation_contract.metric_policy_version"))
    artifact = _mapping(payload.get("artifact_contract"))
    errors.extend(_exact_fields(artifact, {"license_policy_version"}, "artifact_contract."))
    errors.extend(_nonempty(artifact.get("license_policy_version"), "artifact_contract.license_policy_version"))
    execution = _mapping(payload.get("execution_profile"))
    errors.extend(_exact_fields(execution, {"runner", "adapter"}, "execution_profile."))
    errors.extend(_nonempty(execution.get("runner"), "execution_profile.runner"))
    if execution.get("adapter") != "NONE":
        errors.append("execution_profile.adapter must be NONE")
    errors.extend(_validate_safety(payload.get("safety")))
    if not errors and payload.get("forecast_trial_spec_id") != content_hash(payload, omit={"forecast_trial_spec_id"}):
        errors.append("forecast_trial_spec_id does not match canonical content")
    return errors


def validate_forecast_artifact_receipt(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "receipt_id",
        "forecast_trial_spec_id",
        "dataset_bundle_id",
        "forecast_origin",
        "writer_version",
        "generated_at",
        "forecast_artifacts",
        "license_refs",
        "usage_policy_ref",
        "effective_usage_statuses",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != FORECAST_ARTIFACT_RECEIPT_VERSION:
        errors.append("schema_version is invalid")
    for field in ("receipt_id", "forecast_trial_spec_id", "dataset_bundle_id"):
        errors.extend(_hash(payload.get(field), field))
    errors.extend(_utc_timestamp(payload.get("forecast_origin"), "forecast_origin"))
    errors.extend(_utc_timestamp(payload.get("generated_at"), "generated_at"))
    errors.extend(_nonempty(payload.get("writer_version"), "writer_version"))
    license_refs = payload.get("license_refs")
    errors.extend(_sorted_unique(license_refs, "license_refs"))
    if isinstance(license_refs, list) and not license_refs:
        errors.append("license_refs must be non-empty")
    if isinstance(license_refs, list):
        for index, value in enumerate(license_refs):
            errors.extend(_hash(value, f"license_refs[{index}]"))
    errors.extend(_hash(payload.get("usage_policy_ref"), "usage_policy_ref"))
    errors.extend(_validate_effective_usage_statuses(payload.get("effective_usage_statuses"), "effective_usage_statuses"))
    artifacts = payload.get("forecast_artifacts")
    if not isinstance(artifacts, list):
        return errors + ["forecast_artifacts must be a list"]
    artifact_types: list[str] = []
    artifact_ids: list[str] = []
    for index, raw_artifact in enumerate(artifacts):
        artifact = _mapping(raw_artifact)
        prefix = f"forecast_artifacts[{index}]."
        allowed = {"artifact_type", "artifact_id", "corpus_path", "format_contract", "license_refs"}
        if artifact.get("artifact_type") == "QUANTILE_FORECAST":
            allowed.add("quantile_levels")
        errors.extend(_exact_fields(artifact, allowed, prefix))
        artifact_type = artifact.get("artifact_type")
        if artifact_type not in {"POINT_FORECAST", "QUANTILE_FORECAST"}:
            errors.append(f"{prefix}artifact_type is invalid")
        else:
            artifact_types.append(str(artifact_type))
        errors.extend(_hash(artifact.get("artifact_id"), f"{prefix}artifact_id"))
        artifact_id = str(artifact.get("artifact_id") or "")
        artifact_ids.append(artifact_id)
        digest = artifact_id.removeprefix(HASH_PREFIX)
        corpus = PurePosixPath(str(artifact.get("corpus_path") or ""))
        if corpus.is_absolute() or ".." in corpus.parts or corpus.parts != ("source_corpus", "sha256", digest):
            errors.append(f"{prefix}corpus_path must match artifact digest")
        errors.extend(_nonempty(artifact.get("format_contract"), f"{prefix}format_contract"))
        if artifact.get("license_refs") != license_refs:
            errors.append(f"{prefix}license_refs must equal receipt license_refs")
        if artifact_type == "QUANTILE_FORECAST":
            errors.extend(_validate_quantile_levels(artifact.get("quantile_levels"), f"{prefix}quantile_levels"))
    if sorted(artifact_types) != ["POINT_FORECAST", "QUANTILE_FORECAST"]:
        errors.append("forecast_artifacts must contain exactly POINT_FORECAST and QUANTILE_FORECAST")
    if len(artifact_ids) != len(set(artifact_ids)):
        errors.append("forecast_artifacts.artifact_id must be unique")
    if not errors and payload.get("receipt_id") != content_hash(payload, omit={"receipt_id"}):
        errors.append("receipt_id does not match canonical content")
    return errors


def validate_forecast_evaluation_observation(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "observation_id",
        "forecast_trial_spec_id",
        "forecast_artifact_receipt_id",
        "forecast_origin",
        "target_channel_id",
        "horizon",
        "metric_policy_version",
        "result_unit_id",
        "evidence_unit_id",
        "metrics",
        "artifact_refs",
        "license_refs",
        "observed_at",
    }
    errors = _exact_fields(payload, fields)
    if payload.get("schema_version") != FORECAST_EVALUATION_OBSERVATION_VERSION:
        errors.append("schema_version is invalid")
    for field in ("observation_id", "forecast_trial_spec_id", "forecast_artifact_receipt_id", "evidence_unit_id"):
        errors.extend(_hash(payload.get(field), field))
    errors.extend(_utc_timestamp(payload.get("forecast_origin"), "forecast_origin"))
    errors.extend(_utc_timestamp(payload.get("observed_at"), "observed_at"))
    errors.extend(_nonempty(payload.get("target_channel_id"), "target_channel_id"))
    errors.extend(_nonempty(payload.get("metric_policy_version"), "metric_policy_version"))
    errors.extend(_nonempty(payload.get("result_unit_id"), "result_unit_id"))
    horizon = _mapping(payload.get("horizon"))
    errors.extend(_exact_fields(horizon, {"unit", "steps"}, "horizon."))
    if horizon.get("unit") not in {"calendar_day", "trading_day"}:
        errors.append("horizon.unit is invalid")
    errors.extend(_positive_int(horizon.get("steps"), "horizon.steps"))
    metrics = _mapping(payload.get("metrics"))
    metric_fields = {"mae", "rmse", "coverage_0_8"}
    errors.extend(_exact_fields(metrics, metric_fields, "metrics."))
    for metric in sorted(metric_fields):
        errors.extend(_decimal_string(metrics.get(metric), f"metrics.{metric}"))
    artifact_refs = payload.get("artifact_refs")
    errors.extend(_sorted_unique(artifact_refs, "artifact_refs"))
    if isinstance(artifact_refs, list) and not artifact_refs:
        errors.append("artifact_refs must be non-empty")
    if isinstance(artifact_refs, list):
        for index, value in enumerate(artifact_refs):
            errors.extend(_hash(value, f"artifact_refs[{index}]"))
    license_refs = payload.get("license_refs")
    errors.extend(_sorted_unique(license_refs, "license_refs"))
    if isinstance(license_refs, list) and not license_refs:
        errors.append("license_refs must be non-empty")
    if isinstance(license_refs, list):
        for index, value in enumerate(license_refs):
            errors.extend(_hash(value, f"license_refs[{index}]"))
    if not errors and payload.get("observation_id") != content_hash(payload, omit={"observation_id"}):
        errors.append("observation_id does not match canonical content")
    return errors
