"""FC2 forecast deterministic fixture 的建立與驗證工具。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from app.research.contracts import (
    CANONICALIZATION_VERSION,
    TERMINAL_CAUSE_POLICY_VERSION,
    canonical_json_bytes,
    content_hash,
    validate_attempt_started,
    validate_research_intent,
    validate_run_receipt,
    validate_trial_spec,
)
from app.research.dataset_bundle import build_dataset_bundle, publish_dataset_bundle_manifest, validate_dataset_bundle
from app.research.forecast_contracts import (
    validate_forecast_artifact_receipt,
    validate_forecast_evaluation_observation,
    validate_forecast_trial_spec,
)
from app.research.receipt_store import publish_bytes_to_cas, write_immutable_json


FORECAST_ORIGIN = "2026-08-31T00:00:00+00:00"
OBSERVED_AT = "2026-09-06T00:00:00+00:00"
GENERATED_AT = "2026-08-31T00:01:00+00:00"
COMPLETED_AT = "2026-08-31T00:02:00+00:00"
EFFECTIVE_USAGE_STATUSES = [
    "NO_B_DECISION_CONSUMPTION",
    "NO_M4_M5_M6_M7_MUTATION",
    "NO_PRODUCTION_SIGNAL_EXPORT",
    "RESEARCH_ONLY",
    "SHADOW_BENCHMARK_ONLY",
]


@dataclass(frozen=True)
class ForecastFixtureResult:
    """固定輸入 forecast fixture 的所有可驗證 identity。"""

    corpus_root: Path
    dataset_bundle: dict[str, Any]
    forecast_trial_spec: dict[str, Any]
    lifecycle_trial_spec: dict[str, Any]
    lifecycle_intent: dict[str, Any]
    lifecycle_attempt: dict[str, Any]
    lifecycle_run_receipt: dict[str, Any]
    artifact_receipt: dict[str, Any]
    evaluation_observation: dict[str, Any]
    content_identity: str
    written_paths: dict[str, str]


@dataclass(frozen=True)
class ForecastFixture:
    dataset_bundle: dict[str, Any]
    trial_spec: dict[str, Any]
    lifecycle_trial_spec: dict[str, Any]
    lifecycle_intent: dict[str, Any]
    lifecycle_attempt: dict[str, Any]
    lifecycle_run_receipt: dict[str, Any]
    artifact_receipt: dict[str, Any]
    evaluation_observation: dict[str, Any]
    corpus_root: Path
    content_identity: str
    written_paths: dict[str, str]


def _canonical_line(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _publish_payload_to_cas(corpus_root: Path, payload: Mapping[str, Any]) -> tuple[str, Path]:
    return publish_bytes_to_cas(corpus_root, _canonical_line(payload))


def _fixture_license_ref() -> str:
    return content_hash(
        {
            "schema_version": "forecast-fixture-license-ref.v1",
            "license_policy_version": "forecast-artifact-license-binding.v1",
            "source": "deterministic-local-fixture",
        }
    )


def _fixture_usage_policy_ref() -> str:
    return content_hash(
        {
            "schema_version": "forecast-fixture-usage-policy-ref.v1",
            "statuses": EFFECTIVE_USAGE_STATUSES,
        }
    )


def _channel_frame_payload() -> dict[str, Any]:
    return {
        "schema_version": "forecast-fixture-channel-frame.v1",
        "forecast_origin": FORECAST_ORIGIN,
        "rows": [
            {"date": "2026-08-27", "close": "101.00", "next_close": None, "known_holiday": "0"},
            {"date": "2026-08-28", "close": "102.00", "next_close": None, "known_holiday": "0"},
            {"date": "2026-08-29", "close": "103.00", "next_close": None, "known_holiday": "0"},
        ],
    }


def _coverage() -> dict[str, Any]:
    return {
        "schema_version": "dataset-component-coverage.v1",
        "status": "COMPLETE",
        "expected_member_count": 3,
        "observed_member_count": 3,
        "date_start": "2026-08-27",
        "date_end": "2026-09-05",
    }


def _channel(
    channel_id: str,
    *,
    index: int,
    channel_role: str,
    event_at: str,
    available_at: str,
) -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "channel_index": index,
        "channel_role": channel_role,
        "value_contract": "numeric-series.v1",
        "missingness_policy": "EXPLICIT_NULLS",
        "temporal_availability": {
            "event_at": event_at,
            "forecast_origin": FORECAST_ORIGIN,
            "available_at": available_at,
            "horizon_start": "2026-09-01",
            "horizon_end": "2026-09-05",
        },
    }


def _build_dataset_bundle(channel_frame_id: str) -> dict[str, Any]:
    return build_dataset_bundle(
        consumer_id="FORECAST_TRIAL_V1",
        contract_version="forecast-trial-dataset.v1",
        components=[
            {
                "role": "FORECAST_CHANNEL_SET",
                "member_key": "primary",
                "identity_kind": "FORECAST_CHANNEL_SET_V1",
                "content_id": channel_frame_id,
                "resolution_status": "RESOLVED",
                "format_contract": "forecast-channel-frame.v1",
                "coverage": _coverage(),
                "channels": [
                    _channel(
                        "close",
                        index=0,
                        channel_role="TARGET",
                        event_at="2026-08-29T00:00:00+00:00",
                        available_at="2026-08-29T00:00:00+00:00",
                    ),
                    _channel(
                        "next_close",
                        index=1,
                        channel_role="TARGET",
                        event_at="2026-09-05T00:00:00+00:00",
                        available_at=OBSERVED_AT,
                    ),
                    _channel(
                        "known_holiday",
                        index=2,
                        channel_role="FUTURE_KNOWN_COVARIATE",
                        event_at="2026-09-01T00:00:00+00:00",
                        available_at="2026-08-30T00:00:00+00:00",
                    ),
                ],
            }
        ],
        transformation_identity={
            "contract_version": "forecast-fixture-transform.v1",
            "git_blob_ids": ["git-sha1:" + "1" * 40],
        },
        resolution_semantics={
            "fallback_policy_version": "forecast-fixture-resolution.v1",
            "identity_bearing_absence_is_explicit": True,
        },
    )


def _trial_spec(dataset_bundle: Mapping[str, Any], dataset_ref: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "forecast-trial-spec.v1",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "forecast_trial_spec_id": "",
        "dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
        "dataset_bundle_manifest_ref": dataset_ref,
        "forecast_origin": FORECAST_ORIGIN,
        "horizon": {"unit": "trading_day", "steps": 5},
        "target_channel_ids": ["close", "next_close"],
        "covariate_channel_ids": ["known_holiday"],
        "prediction_contract": {
            "point": {"artifact_contract": "forecast-point-frame.v1"},
            "quantiles": {
                "levels": ["0.1", "0.5", "0.9"],
                "artifact_contract": "forecast-quantile-frame.v1",
            },
        },
        "evaluation_contract": {"metric_policy_version": "forecast-evaluation-metrics.v1"},
        "artifact_contract": {"license_policy_version": "forecast-artifact-license-binding.v1"},
        "execution_profile": {"runner": "deterministic-naive-fixture", "adapter": "NONE"},
        "safety": {
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
    }
    payload["forecast_trial_spec_id"] = content_hash(payload, omit={"forecast_trial_spec_id"})
    return payload


def _point_artifact(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "forecast-point-frame.v1",
        "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
        "forecast_origin": FORECAST_ORIGIN,
        "rows": [
            {"target_channel_id": "close", "step": 1, "date": "2026-09-01", "point": "103.25"},
            {"target_channel_id": "close", "step": 5, "date": "2026-09-05", "point": "104.25"},
            {"target_channel_id": "next_close", "step": 5, "date": "2026-09-05", "point": "104.25"},
        ],
    }


def _quantile_artifact(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "forecast-quantile-frame.v1",
        "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
        "forecast_origin": FORECAST_ORIGIN,
        "quantile_levels": ["0.1", "0.5", "0.9"],
        "rows": [
            {"target_channel_id": "close", "step": 5, "date": "2026-09-05", "q0.1": "103.50", "q0.5": "104.25", "q0.9": "105.00"},
            {"target_channel_id": "next_close", "step": 5, "date": "2026-09-05", "q0.1": "103.50", "q0.5": "104.25", "q0.9": "105.00"},
        ],
    }


def _artifact_ref(artifact_type: str, artifact_id: str, format_contract: str, license_refs: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "corpus_path": f"source_corpus/sha256/{artifact_id.removeprefix('sha256:')}",
        "format_contract": format_contract,
        "license_refs": license_refs,
    }
    if artifact_type == "QUANTILE_FORECAST":
        payload["quantile_levels"] = ["0.1", "0.5", "0.9"]
    return payload


def _artifact_receipt(
    spec: Mapping[str, Any],
    point_id: str,
    quantile_id: str,
) -> dict[str, Any]:
    license_refs = [_fixture_license_ref()]
    payload: dict[str, Any] = {
        "schema_version": "forecast-artifact-receipt.v1",
        "receipt_id": "",
        "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
        "dataset_bundle_id": spec["dataset_bundle_id"],
        "forecast_origin": FORECAST_ORIGIN,
        "writer_version": "forecast-fixture-writer.v1",
        "generated_at": GENERATED_AT,
        "forecast_artifacts": [
            _artifact_ref("POINT_FORECAST", point_id, "forecast-point-frame.v1", license_refs),
            _artifact_ref("QUANTILE_FORECAST", quantile_id, "forecast-quantile-frame.v1", license_refs),
        ],
        "license_refs": license_refs,
        "usage_policy_ref": _fixture_usage_policy_ref(),
        "effective_usage_statuses": EFFECTIVE_USAGE_STATUSES,
    }
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    return payload


def _coverage_parameters() -> dict[str, Any]:
    return {
        "horizon": 5,
        "stop_loss_pct": None,
        "take_profit_pct": None,
        "max_group_exposure": None,
        "regime_gate": None,
        "risk_guard": None,
        "entry_filter": None,
    }


def _forecast_regime_scope() -> dict[str, Any]:
    return {"regime_id": "FORECAST_FIXTURE|FC2"}


def _forecast_episode_ids() -> list[str]:
    return ["forecast-fixture-fc2-deterministic-naive"]


def _no_ranking_source_hash(
    forecast_spec: Mapping[str, Any],
    artifact_receipt: Mapping[str, Any],
) -> str:
    return content_hash(
        {
            "schema_version": "forecast-fixture-no-ranking-source.v1",
            "reason_code": "FORECAST_FIXTURE_HAS_NO_RANKING_SOURCE",
            "forecast_trial_spec_id": forecast_spec["forecast_trial_spec_id"],
            "forecast_artifact_receipt_id": artifact_receipt["receipt_id"],
        }
    )


def _lifecycle_execution_profile(
    *,
    forecast_spec: Mapping[str, Any],
    forecast_spec_ref: str,
    forecast_spec_cas_id: str,
    artifact_receipt: Mapping[str, Any],
    artifact_receipt_ref: str,
    artifact_receipt_cas_id: str,
    evaluation_observation: Mapping[str, Any],
    evaluation_observation_ref: str,
    evaluation_observation_cas_id: str,
) -> dict[str, Any]:
    return {
        "runner": "deterministic-naive-forecast-fixture",
        "profile": "forecast_e2e_fixture",
        "adapter": "NONE",
        "forecast_trial_spec_id": forecast_spec["forecast_trial_spec_id"],
        "forecast_trial_spec_ref": forecast_spec_ref,
        "forecast_trial_spec_cas_id": forecast_spec_cas_id,
        "forecast_artifact_receipt_id": artifact_receipt["receipt_id"],
        "forecast_artifact_receipt_ref": artifact_receipt_ref,
        "forecast_artifact_receipt_cas_id": artifact_receipt_cas_id,
        "forecast_evaluation_observation_id": evaluation_observation["observation_id"],
        "forecast_evaluation_observation_ref": evaluation_observation_ref,
        "forecast_evaluation_observation_cas_id": evaluation_observation_cas_id,
    }


def _lifecycle_trial_spec(
    *,
    dataset_bundle: Mapping[str, Any],
    dataset_ref: str,
    forecast_spec: Mapping[str, Any],
    forecast_spec_ref: str,
    forecast_spec_cas_id: str,
    artifact_receipt: Mapping[str, Any],
    artifact_receipt_ref: str,
    artifact_receipt_cas_id: str,
    evaluation_observation: Mapping[str, Any],
    evaluation_observation_ref: str,
    evaluation_observation_cas_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "research-trial-spec.v1",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "trial_spec_id": "sha256:" + "0" * 64,
        "topic_id": "forecast-fixture:fc2",
        "topic_family_id": "forecast-fixture",
        "parameter_catalog_version": "research-parameter-catalog.v1",
        "parameter_catalog_hash": content_hash({"schema_version": "forecast-fixture-parameter-catalog.v1"}),
        "parameters": _coverage_parameters(),
        "research_stage": "DEVELOPMENT_SCREEN",
        "regime_scope": _forecast_regime_scope(),
        "dataset_authority": {"dataset_hash": dataset_bundle["dataset_bundle_id"]},
        "ranking_source_authority": {
            "ranking_source_hash": _no_ranking_source_hash(forecast_spec, artifact_receipt)
        },
        "execution_profile": _lifecycle_execution_profile(
            forecast_spec=forecast_spec,
            forecast_spec_ref=forecast_spec_ref,
            forecast_spec_cas_id=forecast_spec_cas_id,
            artifact_receipt=artifact_receipt,
            artifact_receipt_ref=artifact_receipt_ref,
            artifact_receipt_cas_id=artifact_receipt_cas_id,
            evaluation_observation=evaluation_observation,
            evaluation_observation_ref=evaluation_observation_ref,
            evaluation_observation_cas_id=evaluation_observation_cas_id,
        ),
        "safety": {
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
    }
    payload["trial_spec_id"] = content_hash(payload, omit={"trial_spec_id"})
    return payload


def _lifecycle_intent(
    *,
    trial_spec: Mapping[str, Any],
    dataset_bundle: Mapping[str, Any],
    dataset_ref: str,
) -> dict[str, Any]:
    identity = content_hash(
        {
            "schema_version": "forecast-fixture-lifecycle-intent-id.v1",
            "trial_spec_id": trial_spec["trial_spec_id"],
            "dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
            "dataset_bundle_manifest_ref": dataset_ref,
        }
    ).removeprefix("sha256:")[:32]
    return {
        "schema_version": "research-intent.v1",
        "intent_id": f"intent-{identity}",
        "requested_trial_spec_ids": [trial_spec["trial_spec_id"]],
        "requested_dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
        "requested_dataset_bundle_manifest_ref": dataset_ref,
        "requested_at": GENERATED_AT,
        "request_source": "forecast_e2e_fixture",
        "selection_reason": {
            "reason_codes": ["FC2_VENDOR_NEUTRAL_FORECAST_FIXTURE"],
            "forecast_trial_spec_id": trial_spec["execution_profile"]["forecast_trial_spec_id"],
        },
    }


def _lifecycle_attempt(intent: Mapping[str, Any]) -> dict[str, Any]:
    run_identity = content_hash(
        {
            "schema_version": "forecast-fixture-lifecycle-run-id.v1",
            "intent_id": intent["intent_id"],
            "requested_trial_spec_ids": intent["requested_trial_spec_ids"],
            "requested_dataset_bundle_id": intent["requested_dataset_bundle_id"],
        }
    ).removeprefix("sha256:")[:32]
    payload: dict[str, Any] = {
        "schema_version": "research-run-attempt-started.v1",
        "attempt_event_id": "sha256:" + "0" * 64,
        "run_id": f"run-{run_identity}",
        "intent_id": intent["intent_id"],
        "requested_trial_spec_ids": intent["requested_trial_spec_ids"],
        "requested_dataset_bundle_id": intent["requested_dataset_bundle_id"],
        "requested_dataset_bundle_manifest_ref": intent["requested_dataset_bundle_manifest_ref"],
        "started_at": GENERATED_AT,
        "executor": {
            "runner_id": "forecast-e2e-fixture",
            "runner_version": "v1",
            "adapter": "NONE",
        },
        "invocation_hash": content_hash(
            {
                "intent_id": intent["intent_id"],
                "requested_trial_spec_ids": intent["requested_trial_spec_ids"],
            }
        ),
    }
    payload["attempt_event_id"] = content_hash(payload, omit={"attempt_event_id"})
    return payload


def _run_artifact(artifact_id: str, provenance_path: str) -> dict[str, str]:
    return {
        "artifact_id": artifact_id,
        "corpus_path": f"source_corpus/sha256/{artifact_id.removeprefix('sha256:')}",
        "provenance_path": provenance_path,
        "validation_status": "VALID",
    }


def _lifecycle_authority_hash(
    *,
    forecast_spec: Mapping[str, Any],
    artifact_receipt: Mapping[str, Any],
    evaluation_observation: Mapping[str, Any],
    artifact_ids: list[str],
) -> str:
    return content_hash(
        {
            "schema_version": "forecast-fixture-lifecycle-authority.v1",
            "forecast_trial_spec_id": forecast_spec["forecast_trial_spec_id"],
            "forecast_artifact_receipt_id": artifact_receipt["receipt_id"],
            "forecast_evaluation_observation_id": evaluation_observation["observation_id"],
            "artifact_ids": sorted(artifact_ids),
            "episode_ids": _forecast_episode_ids(),
        }
    )


def _lifecycle_run_receipt(
    *,
    lifecycle_trial_spec: Mapping[str, Any],
    intent: Mapping[str, Any],
    attempt: Mapping[str, Any],
    dataset_bundle: Mapping[str, Any],
    dataset_ref: str,
    forecast_spec: Mapping[str, Any],
    forecast_spec_cas_id: str,
    artifact_receipt: Mapping[str, Any],
    artifact_receipt_cas_id: str,
    evaluation_observation: Mapping[str, Any],
    evaluation_observation_cas_id: str,
    point_id: str,
    quantile_id: str,
) -> dict[str, Any]:
    lifecycle_trial_id = str(lifecycle_trial_spec["trial_spec_id"])
    parameters = _coverage_parameters()
    artifact_ids = [
        forecast_spec_cas_id,
        point_id,
        quantile_id,
        artifact_receipt_cas_id,
        evaluation_observation_cas_id,
    ]
    ranking_hash = str(lifecycle_trial_spec["ranking_source_authority"]["ranking_source_hash"])
    facts = {
        "sealed_usage_status": "PROVEN_NON_SEALED",
        "research_stage": lifecycle_trial_spec["research_stage"],
        "dataset_hash": dataset_bundle["dataset_bundle_id"],
        "ranking_source_hash": ranking_hash,
        "regime_scope": lifecycle_trial_spec["regime_scope"],
        "episode_ids": _forecast_episode_ids(),
    }
    execution_unit = {
        "execution_unit_id": content_hash({"run_id": attempt["run_id"], "trial_id": lifecycle_trial_id}),
        "requested_trial_spec_id": lifecycle_trial_id,
        "executed_trial_spec_id": lifecycle_trial_id,
        "executed_parameters": parameters,
        "executed_research_stage": lifecycle_trial_spec["research_stage"],
        "executed_regime_scope": lifecycle_trial_spec["regime_scope"],
        "executed_dataset_hash": dataset_bundle["dataset_bundle_id"],
        "executed_dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
        "executed_dataset_bundle_manifest_ref": dataset_ref,
        "executed_ranking_source_hash": ranking_hash,
        "executed_execution_profile": lifecycle_trial_spec["execution_profile"],
        "lineage": {
            "lineage_id": content_hash(facts),
            "sealed_usage_status": "PROVEN_NON_SEALED",
            "episode_ids": _forecast_episode_ids(),
            "episode_authority_hash": _lifecycle_authority_hash(
                forecast_spec=forecast_spec,
                artifact_receipt=artifact_receipt,
                evaluation_observation=evaluation_observation,
                artifact_ids=artifact_ids,
            ),
        },
        "lineage_assertions": [
            {
                "authority": "forecast-fixture-lifecycle-linkage",
                "authority_hash": artifact_receipt_cas_id,
                "facts": facts,
            }
        ],
        "lineage_resolution_status": "VALID",
        "artifact_refs": artifact_ids,
    }
    payload: dict[str, Any] = {
        "schema_version": "research-run-receipt.v1",
        "run_id": attempt["run_id"],
        "intent_id": intent["intent_id"],
        "receipt_id": "sha256:" + "0" * 64,
        "attempt_event_id": attempt["attempt_event_id"],
        "writer_version": "forecast-fixture-research-receipt-writer.v1",
        "terminal_status": "SUCCEEDED",
        "started_at": attempt["started_at"],
        "completed_at": COMPLETED_AT,
        "terminal_cause": {
            "policy_version": TERMINAL_CAUSE_POLICY_VERSION,
            "status": "SUCCEEDED",
            "reason_code": "FORECAST_FIXTURE_EXECUTED",
            "observed_at": COMPLETED_AT,
            "observer": "forecast-e2e-fixture",
            "runner_started": True,
            "evidence_refs": sorted(set(artifact_ids)),
        },
        "bundle_binding": {
            "requested_dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
            "requested_dataset_bundle_manifest_ref": dataset_ref,
            "executed_dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
            "executed_dataset_bundle_manifest_ref": dataset_ref,
            "validation_status": "VALID",
        },
        "requested": {
            "trial_spec_ids": [lifecycle_trial_id],
            "dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
            "dataset_bundle_manifest_ref": dataset_ref,
            "parameters_by_trial": {lifecycle_trial_id: parameters},
            "research_stage": lifecycle_trial_spec["research_stage"],
            "regime_scope": lifecycle_trial_spec["regime_scope"],
            "dataset_authority": lifecycle_trial_spec["dataset_authority"],
            "ranking_source_authority_by_trial": {
                lifecycle_trial_id: lifecycle_trial_spec["ranking_source_authority"]
            },
            "execution_profile_by_trial": {
                lifecycle_trial_id: lifecycle_trial_spec["execution_profile"]
            },
        },
        "executed_units": [execution_unit],
        "resolution_events": [],
        "identity_match_status": "EXACT",
        "execution_observation_status": "OBSERVED",
        "artifacts": [
            _run_artifact(forecast_spec_cas_id, lifecycle_trial_spec["execution_profile"]["forecast_trial_spec_ref"]),
            _run_artifact(point_id, f"source_corpus/sha256/{point_id.removeprefix('sha256:')}"),
            _run_artifact(quantile_id, f"source_corpus/sha256/{quantile_id.removeprefix('sha256:')}"),
            _run_artifact(artifact_receipt_cas_id, lifecycle_trial_spec["execution_profile"]["forecast_artifact_receipt_ref"]),
            _run_artifact(
                evaluation_observation_cas_id,
                lifecycle_trial_spec["execution_profile"]["forecast_evaluation_observation_ref"],
            ),
        ],
        "safety": {
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
    }
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    return payload


def _evaluation_observation(
    spec: Mapping[str, Any],
    receipt: Mapping[str, Any],
    artifact_ids: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "forecast-evaluation-observation.v1",
        "observation_id": "",
        "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
        "forecast_artifact_receipt_id": receipt["receipt_id"],
        "forecast_origin": FORECAST_ORIGIN,
        "target_channel_id": "close",
        "horizon": {"unit": "trading_day", "steps": 5},
        "metric_policy_version": "forecast-evaluation-metrics.v1",
        "result_unit_id": "close:2026-09-05",
        "evidence_unit_id": content_hash(
            {
                "forecast_artifact_receipt_id": receipt["receipt_id"],
                "target_channel_id": "close",
                "result_unit_id": "close:2026-09-05",
            }
        ),
        "metrics": {"mae": "0.75", "rmse": "0.75", "coverage_0_8": "1"},
        "artifact_refs": sorted(artifact_ids),
        "license_refs": receipt["license_refs"],
        "observed_at": OBSERVED_AT,
    }
    payload["observation_id"] = content_hash(payload, omit={"observation_id"})
    return payload


def _content_identity(
    dataset_bundle: Mapping[str, Any],
    spec: Mapping[str, Any],
    lifecycle_trial_spec: Mapping[str, Any],
    lifecycle_intent: Mapping[str, Any],
    lifecycle_attempt: Mapping[str, Any],
    lifecycle_run_receipt: Mapping[str, Any],
    receipt: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> str:
    artifact_ids = sorted(str(item["artifact_id"]) for item in receipt["forecast_artifacts"])
    return content_hash(
        {
            "schema_version": "forecast-fixture-content-identity.v1",
            "dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
            "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
            "lifecycle_trial_spec_id": lifecycle_trial_spec["trial_spec_id"],
            "lifecycle_intent_id": lifecycle_intent["intent_id"],
            "lifecycle_attempt_event_id": lifecycle_attempt["attempt_event_id"],
            "lifecycle_run_receipt_id": lifecycle_run_receipt["receipt_id"],
            "forecast_artifact_receipt_id": receipt["receipt_id"],
            "forecast_evaluation_observation_id": observation["observation_id"],
            "artifact_ids": artifact_ids,
        }
    )


def _relative_to_corpus(path: Path, corpus_root: Path) -> str:
    return path.relative_to(corpus_root).as_posix()


def build_forecast_e2e_fixture(corpus_root: Path) -> ForecastFixtureResult:
    """建立固定小型 forecast fixture；所有輸出都寫入呼叫端指定 corpus。"""

    corpus_root.mkdir(parents=True, exist_ok=True)
    channel_frame_id, channel_frame_path = _publish_payload_to_cas(corpus_root, _channel_frame_payload())
    dataset_bundle = _build_dataset_bundle(channel_frame_id)
    dataset_write = publish_dataset_bundle_manifest(corpus_root, dataset_bundle)
    dataset_ref = f"dataset_bundles/{dataset_bundle['dataset_bundle_id'].removeprefix('sha256:')}.json"

    spec = _trial_spec(dataset_bundle, dataset_ref)
    spec_path = corpus_root / "forecast_trial_specs" / f"{spec['forecast_trial_spec_id'].removeprefix('sha256:')}.json"
    spec_write = write_immutable_json(
        spec_path,
        spec,
        validator=validate_forecast_trial_spec,
        identity_field="forecast_trial_spec_id",
    )
    forecast_spec_cas_id, forecast_spec_cas_path = _publish_payload_to_cas(corpus_root, spec)

    point_id, point_path = _publish_payload_to_cas(corpus_root, _point_artifact(spec))
    quantile_id, quantile_path = _publish_payload_to_cas(corpus_root, _quantile_artifact(spec))
    receipt = _artifact_receipt(spec, point_id, quantile_id)
    receipt_path = corpus_root / "forecast_artifact_receipts" / f"{receipt['receipt_id'].removeprefix('sha256:')}.json"
    receipt_write = write_immutable_json(
        receipt_path,
        receipt,
        validator=validate_forecast_artifact_receipt,
        identity_field="receipt_id",
    )
    artifact_receipt_cas_id, artifact_receipt_cas_path = _publish_payload_to_cas(corpus_root, receipt)

    observation = _evaluation_observation(spec, receipt, [point_id, quantile_id])
    observation_path = (
        corpus_root
        / "forecast_evaluation_observations"
        / f"{observation['observation_id'].removeprefix('sha256:')}.json"
    )
    observation_write = write_immutable_json(
        observation_path,
        observation,
        validator=validate_forecast_evaluation_observation,
        identity_field="observation_id",
    )
    evaluation_observation_cas_id, evaluation_observation_cas_path = _publish_payload_to_cas(corpus_root, observation)

    lifecycle_trial_spec = _lifecycle_trial_spec(
        dataset_bundle=dataset_bundle,
        dataset_ref=dataset_ref,
        forecast_spec=spec,
        forecast_spec_ref=_relative_to_corpus(spec_write.path, corpus_root),
        forecast_spec_cas_id=forecast_spec_cas_id,
        artifact_receipt=receipt,
        artifact_receipt_ref=_relative_to_corpus(receipt_write.path, corpus_root),
        artifact_receipt_cas_id=artifact_receipt_cas_id,
        evaluation_observation=observation,
        evaluation_observation_ref=_relative_to_corpus(observation_write.path, corpus_root),
        evaluation_observation_cas_id=evaluation_observation_cas_id,
    )
    lifecycle_trial_write = write_immutable_json(
        corpus_root / "trial_specs" / f"{lifecycle_trial_spec['trial_spec_id'].removeprefix('sha256:')}.json",
        lifecycle_trial_spec,
        validator=validate_trial_spec,
        identity_field="trial_spec_id",
    )
    lifecycle_intent = _lifecycle_intent(
        trial_spec=lifecycle_trial_spec,
        dataset_bundle=dataset_bundle,
        dataset_ref=dataset_ref,
    )
    lifecycle_intent_write = write_immutable_json(
        corpus_root / "intents" / f"{lifecycle_intent['intent_id']}.json",
        lifecycle_intent,
        validator=validate_research_intent,
        identity_field="intent_id",
    )
    lifecycle_attempt = _lifecycle_attempt(lifecycle_intent)
    lifecycle_attempt_write = write_immutable_json(
        corpus_root / "attempts" / f"{lifecycle_attempt['run_id']}.started.json",
        lifecycle_attempt,
        validator=validate_attempt_started,
        identity_field="run_id",
    )
    lifecycle_run_receipt = _lifecycle_run_receipt(
        lifecycle_trial_spec=lifecycle_trial_spec,
        intent=lifecycle_intent,
        attempt=lifecycle_attempt,
        dataset_bundle=dataset_bundle,
        dataset_ref=dataset_ref,
        forecast_spec=spec,
        forecast_spec_cas_id=forecast_spec_cas_id,
        artifact_receipt=receipt,
        artifact_receipt_cas_id=artifact_receipt_cas_id,
        evaluation_observation=observation,
        evaluation_observation_cas_id=evaluation_observation_cas_id,
        point_id=point_id,
        quantile_id=quantile_id,
    )
    lifecycle_receipt_write = write_immutable_json(
        corpus_root / "receipts" / f"{lifecycle_run_receipt['run_id']}.json",
        lifecycle_run_receipt,
        validator=validate_run_receipt,
        identity_field="run_id",
    )

    return ForecastFixtureResult(
        corpus_root=corpus_root,
        dataset_bundle=dataset_bundle,
        forecast_trial_spec=spec,
        lifecycle_trial_spec=lifecycle_trial_spec,
        lifecycle_intent=lifecycle_intent,
        lifecycle_attempt=lifecycle_attempt,
        lifecycle_run_receipt=lifecycle_run_receipt,
        artifact_receipt=receipt,
        evaluation_observation=observation,
        content_identity=_content_identity(
            dataset_bundle,
            spec,
            lifecycle_trial_spec,
            lifecycle_intent,
            lifecycle_attempt,
            lifecycle_run_receipt,
            receipt,
            observation,
        ),
        written_paths={
            "channel_frame": str(channel_frame_path.relative_to(corpus_root)),
            "dataset_bundle": str(dataset_write.path.relative_to(corpus_root)),
            "forecast_trial_spec": str(spec_write.path.relative_to(corpus_root)),
            "forecast_trial_spec_cas": str(forecast_spec_cas_path.relative_to(corpus_root)),
            "point_artifact": str(point_path.relative_to(corpus_root)),
            "quantile_artifact": str(quantile_path.relative_to(corpus_root)),
            "artifact_receipt": str(receipt_write.path.relative_to(corpus_root)),
            "artifact_receipt_cas": str(artifact_receipt_cas_path.relative_to(corpus_root)),
            "evaluation_observation": str(observation_write.path.relative_to(corpus_root)),
            "evaluation_observation_cas": str(evaluation_observation_cas_path.relative_to(corpus_root)),
            "lifecycle_trial_spec": str(lifecycle_trial_write.path.relative_to(corpus_root)),
            "lifecycle_intent": str(lifecycle_intent_write.path.relative_to(corpus_root)),
            "lifecycle_attempt": str(lifecycle_attempt_write.path.relative_to(corpus_root)),
            "lifecycle_run_receipt": str(lifecycle_receipt_write.path.relative_to(corpus_root)),
        },
    )


def _contains_key(payload: Any, key: str) -> bool:
    if isinstance(payload, Mapping):
        return key in payload or any(_contains_key(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_key(value, key) for value in payload)
    return False


def _artifact_bytes_errors(corpus_root: Path, artifact: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    artifact_id = str(artifact.get("artifact_id") or "")
    digest = artifact_id.removeprefix("sha256:")
    corpus_path = str(artifact.get("corpus_path") or "")
    path = PurePosixPath(corpus_path)
    if path.parts != ("source_corpus", "sha256", digest):
        return [f"{artifact.get('artifact_type')} corpus_path does not match artifact_id"]
    target = corpus_root / corpus_path
    if not target.is_file():
        return [f"{artifact.get('artifact_type')} artifact bytes are missing"]
    encoded = target.read_bytes()
    actual = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if actual != artifact_id:
        errors.append(f"{artifact.get('artifact_type')} artifact bytes do not match artifact_id")
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError:
        errors.append(f"{artifact.get('artifact_type')} artifact bytes must be canonical JSON")
        return errors
    if _contains_key(payload, "available_at"):
        errors.append(f"{artifact.get('artifact_type')} artifact must not contain available_at")
    if payload.get("schema_version") != artifact.get("format_contract"):
        errors.append(f"{artifact.get('artifact_type')} artifact schema_version must match format_contract")
    return errors


def _path_errors(corpus_root: Path, path_value: str, label: str) -> list[str]:
    path = PurePosixPath(path_value)
    if path.is_absolute() or ".." in path.parts:
        return [f"{label} path must be corpus-relative"]
    if not (corpus_root / path_value).is_file():
        return [f"{label} file is missing"]
    return []


def _cas_payload(corpus_root: Path, artifact_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    digest = artifact_id.removeprefix("sha256:")
    path = corpus_root / "source_corpus" / "sha256" / digest
    if not path.is_file():
        return None, [f"CAS artifact is missing: {artifact_id}"]
    encoded = path.read_bytes()
    actual = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if actual != artifact_id:
        return None, [f"CAS artifact digest mismatch: {artifact_id}"]
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError:
        return None, [f"CAS artifact is not JSON: {artifact_id}"]
    return payload, []


def _validate_lifecycle_links(result: ForecastFixtureResult) -> list[str]:
    errors: list[str] = []
    errors.extend(f"lifecycle_trial_spec.{error}" for error in validate_trial_spec(result.lifecycle_trial_spec))
    errors.extend(f"lifecycle_intent.{error}" for error in validate_research_intent(result.lifecycle_intent))
    errors.extend(f"lifecycle_attempt.{error}" for error in validate_attempt_started(result.lifecycle_attempt))
    errors.extend(f"lifecycle_run_receipt.{error}" for error in validate_run_receipt(result.lifecycle_run_receipt))

    for key in (
        "lifecycle_trial_spec",
        "lifecycle_intent",
        "lifecycle_attempt",
        "lifecycle_run_receipt",
        "forecast_trial_spec_cas",
        "artifact_receipt_cas",
        "evaluation_observation_cas",
    ):
        value = result.written_paths.get(key)
        if not isinstance(value, str):
            errors.append(f"written_paths.{key} is required")
        else:
            errors.extend(_path_errors(result.corpus_root, value, f"written_paths.{key}"))

    dataset_id = result.dataset_bundle.get("dataset_bundle_id")
    dataset_ref = result.forecast_trial_spec.get("dataset_bundle_manifest_ref")
    lifecycle_trial_id = result.lifecycle_trial_spec.get("trial_spec_id")
    forecast_spec_id = result.forecast_trial_spec.get("forecast_trial_spec_id")
    forecast_receipt_id = result.artifact_receipt.get("receipt_id")
    forecast_observation_id = result.evaluation_observation.get("observation_id")
    profile = result.lifecycle_trial_spec.get("execution_profile") if isinstance(result.lifecycle_trial_spec, Mapping) else {}
    profile = profile if isinstance(profile, Mapping) else {}

    if result.lifecycle_intent.get("requested_trial_spec_ids") != [lifecycle_trial_id]:
        errors.append("lifecycle_intent must request lifecycle trial spec")
    if result.lifecycle_intent.get("requested_dataset_bundle_id") != dataset_id:
        errors.append("lifecycle_intent dataset bundle must match forecast dataset bundle")
    if result.lifecycle_intent.get("requested_dataset_bundle_manifest_ref") != dataset_ref:
        errors.append("lifecycle_intent dataset manifest ref must match forecast trial spec")
    if result.lifecycle_attempt.get("intent_id") != result.lifecycle_intent.get("intent_id"):
        errors.append("lifecycle_attempt intent_id must match lifecycle_intent")
    if result.lifecycle_attempt.get("requested_trial_spec_ids") != result.lifecycle_intent.get("requested_trial_spec_ids"):
        errors.append("lifecycle_attempt requested trials must match lifecycle_intent")
    if result.lifecycle_run_receipt.get("intent_id") != result.lifecycle_intent.get("intent_id"):
        errors.append("lifecycle_run_receipt intent_id must match lifecycle_intent")
    if result.lifecycle_run_receipt.get("attempt_event_id") != result.lifecycle_attempt.get("attempt_event_id"):
        errors.append("lifecycle_run_receipt attempt_event_id must match lifecycle_attempt")
    if result.lifecycle_run_receipt.get("requested", {}).get("trial_spec_ids") != [lifecycle_trial_id]:
        errors.append("lifecycle_run_receipt must request lifecycle trial spec")
    if result.lifecycle_run_receipt.get("bundle_binding", {}).get("executed_dataset_bundle_id") != dataset_id:
        errors.append("lifecycle_run_receipt executed dataset bundle must match forecast dataset bundle")

    expected_profile = {
        "forecast_trial_spec_id": forecast_spec_id,
        "forecast_artifact_receipt_id": forecast_receipt_id,
        "forecast_evaluation_observation_id": forecast_observation_id,
    }
    for field, expected in expected_profile.items():
        if profile.get(field) != expected:
            errors.append(f"lifecycle_trial_spec.execution_profile.{field} must match forecast fixture")

    forecast_spec_cas_id = str(profile.get("forecast_trial_spec_cas_id") or "")
    forecast_receipt_cas_id = str(profile.get("forecast_artifact_receipt_cas_id") or "")
    forecast_observation_cas_id = str(profile.get("forecast_evaluation_observation_cas_id") or "")
    for artifact_id, field, expected_schema, expected_identity_field, expected_identity in (
        (forecast_spec_cas_id, "forecast_trial_spec_cas_id", "forecast-trial-spec.v1", "forecast_trial_spec_id", forecast_spec_id),
        (
            forecast_receipt_cas_id,
            "forecast_artifact_receipt_cas_id",
            "forecast-artifact-receipt.v1",
            "receipt_id",
            forecast_receipt_id,
        ),
        (
            forecast_observation_cas_id,
            "forecast_evaluation_observation_cas_id",
            "forecast-evaluation-observation.v1",
            "observation_id",
            forecast_observation_id,
        ),
    ):
        payload, cas_errors = _cas_payload(result.corpus_root, artifact_id)
        errors.extend(f"lifecycle_trial_spec.execution_profile.{field}.{error}" for error in cas_errors)
        if payload is None:
            continue
        if payload.get("schema_version") != expected_schema:
            errors.append(f"lifecycle_trial_spec.execution_profile.{field} schema_version mismatch")
        if payload.get(expected_identity_field) != expected_identity:
            errors.append(f"lifecycle_trial_spec.execution_profile.{field} identity mismatch")

    run_artifacts = {
        str(item.get("artifact_id"))
        for item in result.lifecycle_run_receipt.get("artifacts", [])
        if isinstance(item, Mapping)
    }
    forecast_artifact_ids = {
        str(item.get("artifact_id"))
        for item in result.artifact_receipt.get("forecast_artifacts", [])
        if isinstance(item, Mapping)
    }
    expected_run_artifacts = {
        forecast_spec_cas_id,
        forecast_receipt_cas_id,
        forecast_observation_cas_id,
        *forecast_artifact_ids,
    }
    if not expected_run_artifacts.issubset(run_artifacts):
        errors.append("lifecycle_run_receipt artifacts must include forecast spec, artifacts, receipt, and evaluation CAS")
    units = result.lifecycle_run_receipt.get("executed_units")
    unit = units[0] if isinstance(units, list) and len(units) == 1 and isinstance(units[0], Mapping) else {}
    if not unit:
        errors.append("lifecycle_run_receipt must contain one forecast execution unit")
    else:
        if unit.get("requested_trial_spec_id") != lifecycle_trial_id or unit.get("executed_trial_spec_id") != lifecycle_trial_id:
            errors.append("lifecycle_run_receipt execution unit must bind lifecycle trial spec")
        if unit.get("executed_dataset_bundle_id") != dataset_id:
            errors.append("lifecycle_run_receipt execution unit dataset bundle must match forecast dataset bundle")
        if set(unit.get("artifact_refs") or []) != expected_run_artifacts:
            errors.append("lifecycle_run_receipt execution unit artifact_refs must equal forecast lifecycle artifacts")
        assertions = unit.get("lineage_assertions")
        authority_hashes = {
            assertion.get("authority_hash")
            for assertion in assertions
            if isinstance(assertions, list) and isinstance(assertion, Mapping)
        }
        if forecast_receipt_cas_id not in authority_hashes:
            errors.append("lifecycle_run_receipt lineage must be authorized by forecast artifact receipt CAS")

    if result.lifecycle_run_receipt.get("terminal_cause", {}).get("evidence_refs") != sorted(expected_run_artifacts):
        errors.append("lifecycle_run_receipt terminal cause evidence must equal forecast lifecycle artifacts")
    return errors


def validate_forecast_e2e_fixture(result: ForecastFixtureResult) -> list[str]:
    """驗證 fixture 的 contract、artifact bytes、identity linkage 與 strategy 隔離。"""

    errors: list[str] = []
    dataset_validation = validate_dataset_bundle(result.dataset_bundle)
    if dataset_validation.status != "EXECUTABLE":
        errors.extend(f"dataset_bundle.{error}" for error in dataset_validation.errors)
    errors.extend(f"forecast_trial_spec.{error}" for error in validate_forecast_trial_spec(result.forecast_trial_spec))
    errors.extend(f"artifact_receipt.{error}" for error in validate_forecast_artifact_receipt(result.artifact_receipt))
    errors.extend(
        f"evaluation_observation.{error}"
        for error in validate_forecast_evaluation_observation(result.evaluation_observation)
    )
    errors.extend(_validate_lifecycle_links(result))

    if result.forecast_trial_spec.get("dataset_bundle_id") != result.dataset_bundle.get("dataset_bundle_id"):
        errors.append("forecast_trial_spec.dataset_bundle_id must match dataset_bundle")
    if result.artifact_receipt.get("dataset_bundle_id") != result.dataset_bundle.get("dataset_bundle_id"):
        errors.append("artifact_receipt.dataset_bundle_id must match dataset_bundle")
    if result.artifact_receipt.get("forecast_trial_spec_id") != result.forecast_trial_spec.get("forecast_trial_spec_id"):
        errors.append("artifact_receipt.forecast_trial_spec_id must match forecast_trial_spec")
    if result.evaluation_observation.get("forecast_trial_spec_id") != result.forecast_trial_spec.get("forecast_trial_spec_id"):
        errors.append("evaluation_observation.forecast_trial_spec_id must match forecast_trial_spec")
    if result.evaluation_observation.get("forecast_artifact_receipt_id") != result.artifact_receipt.get("receipt_id"):
        errors.append("evaluation_observation.forecast_artifact_receipt_id must match artifact_receipt")

    artifact_ids = sorted(str(item.get("artifact_id")) for item in result.artifact_receipt.get("forecast_artifacts", []))
    if result.evaluation_observation.get("artifact_refs") != artifact_ids:
        errors.append("evaluation_observation.artifact_refs must match receipt artifact ids")
    if result.evaluation_observation.get("license_refs") != result.artifact_receipt.get("license_refs"):
        errors.append("evaluation_observation.license_refs must match artifact_receipt")
    for artifact in result.artifact_receipt.get("forecast_artifacts", []):
        if isinstance(artifact, Mapping):
            errors.extend(_artifact_bytes_errors(result.corpus_root, artifact))

    from app.research.contracts import validate_observation_identity

    if "schema_version is invalid" not in validate_observation_identity(result.evaluation_observation):
        errors.append("forecast evaluation observation must stay outside strategy observation identity")
    expected_identity = _content_identity(
        result.dataset_bundle,
        result.forecast_trial_spec,
        result.lifecycle_trial_spec,
        result.lifecycle_intent,
        result.lifecycle_attempt,
        result.lifecycle_run_receipt,
        result.artifact_receipt,
        result.evaluation_observation,
    )
    if result.content_identity != expected_identity:
        errors.append("content_identity does not match fixture content")
    return errors


def build_forecast_fixture(corpus_root: Path) -> ForecastFixture:
    result = build_forecast_e2e_fixture(corpus_root)
    return ForecastFixture(
        dataset_bundle=result.dataset_bundle,
        trial_spec=result.forecast_trial_spec,
        lifecycle_trial_spec=result.lifecycle_trial_spec,
        lifecycle_intent=result.lifecycle_intent,
        lifecycle_attempt=result.lifecycle_attempt,
        lifecycle_run_receipt=result.lifecycle_run_receipt,
        artifact_receipt=result.artifact_receipt,
        evaluation_observation=result.evaluation_observation,
        corpus_root=result.corpus_root,
        content_identity=result.content_identity,
        written_paths=result.written_paths,
    )


def validate_forecast_fixture_links(
    corpus_root: Path,
    fixture: ForecastFixture,
) -> list[str]:
    result = ForecastFixtureResult(
        corpus_root=corpus_root,
        dataset_bundle=fixture.dataset_bundle,
        forecast_trial_spec=fixture.trial_spec,
        lifecycle_trial_spec=fixture.lifecycle_trial_spec,
        lifecycle_intent=fixture.lifecycle_intent,
        lifecycle_attempt=fixture.lifecycle_attempt,
        lifecycle_run_receipt=fixture.lifecycle_run_receipt,
        artifact_receipt=fixture.artifact_receipt,
        evaluation_observation=fixture.evaluation_observation,
        content_identity=fixture.content_identity,
        written_paths=fixture.written_paths,
    )
    translated: list[str] = []
    for error in validate_forecast_e2e_fixture(result):
        if error == "forecast_trial_spec.dataset_bundle_id must match dataset_bundle":
            translated.append("trial_spec.dataset_bundle_id must equal dataset bundle identity")
        elif error == "artifact_receipt.forecast_trial_spec_id must match forecast_trial_spec":
            translated.append("artifact_receipt.forecast_trial_spec_id must equal trial spec identity")
        elif error.endswith(" artifact bytes do not match artifact_id"):
            translated.append(error.replace("artifact_id", "receipt digest"))
        else:
            translated.append(error)
    return translated


def clone_fixture(fixture: ForecastFixture) -> ForecastFixture:
    return ForecastFixture(
        dataset_bundle=deepcopy(fixture.dataset_bundle),
        trial_spec=deepcopy(fixture.trial_spec),
        lifecycle_trial_spec=deepcopy(fixture.lifecycle_trial_spec),
        lifecycle_intent=deepcopy(fixture.lifecycle_intent),
        lifecycle_attempt=deepcopy(fixture.lifecycle_attempt),
        lifecycle_run_receipt=deepcopy(fixture.lifecycle_run_receipt),
        artifact_receipt=deepcopy(fixture.artifact_receipt),
        evaluation_observation=deepcopy(fixture.evaluation_observation),
        corpus_root=fixture.corpus_root,
        content_identity=fixture.content_identity,
        written_paths=deepcopy(fixture.written_paths),
    )
