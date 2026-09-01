from __future__ import annotations

from copy import deepcopy

import pytest

from app.research.contracts import CANONICALIZATION_VERSION, content_hash, validate_observation_identity
from app.research.dataset_bundle import build_dataset_bundle, validate_dataset_bundle
from app.research.forecast_contracts import (
    validate_forecast_artifact_receipt,
    validate_forecast_evaluation_observation,
    validate_forecast_trial_spec,
)


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64
GIT_A = "git-sha1:" + "a" * 40


def coverage() -> dict[str, object]:
    return {
        "schema_version": "dataset-component-coverage.v1",
        "status": "COMPLETE",
        "expected_member_count": 2,
        "observed_member_count": 2,
        "date_start": "2026-08-01",
        "date_end": "2026-08-30",
    }


def channel(
    channel_id: str,
    *,
    index: int,
    channel_role: str = "PAST_COVARIATE",
    available_at: str = "2026-08-30T00:00:00+00:00",
) -> dict[str, object]:
    return {
        "channel_id": channel_id,
        "channel_index": index,
        "channel_role": channel_role,
        "value_contract": "numeric-series.v1",
        "missingness_policy": "EXPLICIT_NULLS",
        "temporal_availability": {
            "forecast_origin": "2026-08-31T00:00:00+00:00",
            "available_at": available_at,
            "horizon_start": "2026-09-01",
            "horizon_end": "2026-09-05",
        },
    }


def forecast_bundle() -> dict[str, object]:
    return build_dataset_bundle(
        consumer_id="FORECAST_TRIAL_V1",
        contract_version="forecast-trial-dataset.v1",
        components=[
            {
                "role": "FORECAST_CHANNEL_SET",
                "member_key": "primary",
                "identity_kind": "FORECAST_CHANNEL_SET_V1",
                "content_id": SHA_A,
                "resolution_status": "RESOLVED",
                "format_contract": "forecast-channel-frame.v1",
                "coverage": coverage(),
                "channels": [
                    channel("close", index=0, channel_role="TARGET"),
                    channel("known_holiday", index=1, channel_role="FUTURE_KNOWN_COVARIATE"),
                ],
            }
        ],
        transformation_identity={
            "contract_version": "forecast-dataset-transform.v1",
            "git_blob_ids": [GIT_A],
        },
        resolution_semantics={
            "fallback_policy_version": "forecast-dataset-resolution.v1",
            "identity_bearing_absence_is_explicit": True,
        },
    )


def forecast_trial_spec() -> dict[str, object]:
    payload = {
        "schema_version": "forecast-trial-spec.v1",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "forecast_trial_spec_id": SHA_A,
        "dataset_bundle_id": SHA_B,
        "dataset_bundle_manifest_ref": "dataset_bundles/" + SHA_B[7:] + ".json",
        "forecast_origin": "2026-08-31T00:00:00+00:00",
        "horizon": {"unit": "trading_day", "steps": 5},
        "target_channel_id": "close",
        "covariate_channel_ids": ["known_holiday"],
        "prediction_contract": {
            "point": {"artifact_contract": "forecast-point-frame.v1"},
            "quantiles": {"levels": ["0.1", "0.5", "0.9"], "artifact_contract": "forecast-quantile-frame.v1"},
        },
        "evaluation_contract": {"metric_policy_version": "forecast-evaluation-metrics.v1"},
        "artifact_contract": {"license_policy_version": "forecast-artifact-license-binding.v1"},
        "execution_profile": {"runner": "forecast-contract-only", "adapter": "NONE"},
        "safety": {
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
    }
    payload["forecast_trial_spec_id"] = content_hash(payload, omit={"forecast_trial_spec_id"})
    return payload


def forecast_receipt() -> dict[str, object]:
    spec = forecast_trial_spec()
    payload = {
        "schema_version": "forecast-artifact-receipt.v1",
        "receipt_id": SHA_A,
        "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
        "dataset_bundle_id": spec["dataset_bundle_id"],
        "forecast_origin": spec["forecast_origin"],
        "writer_version": "forecast-artifact-receipt-writer.v1",
        "generated_at": "2026-08-31T00:01:00+00:00",
        "forecast_artifacts": [
            {
                "artifact_type": "POINT_FORECAST",
                "artifact_id": SHA_C,
                "corpus_path": f"source_corpus/sha256/{SHA_C[7:]}",
                "format_contract": "forecast-point-frame.v1",
                "license_refs": [SHA_E],
            },
            {
                "artifact_type": "QUANTILE_FORECAST",
                "artifact_id": SHA_D,
                "corpus_path": f"source_corpus/sha256/{SHA_D[7:]}",
                "format_contract": "forecast-quantile-frame.v1",
                "quantile_levels": ["0.1", "0.5", "0.9"],
                "license_refs": [SHA_E],
            },
        ],
        "license_refs": [SHA_E],
    }
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    return payload


def forecast_observation() -> dict[str, object]:
    receipt = forecast_receipt()
    spec = forecast_trial_spec()
    payload = {
        "schema_version": "forecast-evaluation-observation.v1",
        "observation_id": SHA_A,
        "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
        "forecast_artifact_receipt_id": receipt["receipt_id"],
        "forecast_origin": spec["forecast_origin"],
        "target_channel_id": "close",
        "horizon": {"unit": "trading_day", "steps": 5},
        "metric_policy_version": "forecast-evaluation-metrics.v1",
        "result_unit_id": "close:2026-09-05",
        "evidence_unit_id": content_hash({"forecast": receipt["receipt_id"], "target": "close:2026-09-05"}),
        "metrics": {"mae": "1.25", "rmse": "1.5", "coverage_0_8": "0.8"},
        "artifact_refs": [SHA_C, SHA_D],
        "license_refs": [SHA_E],
        "observed_at": "2026-09-06T00:00:00+00:00",
    }
    payload["observation_id"] = content_hash(payload, omit={"observation_id"})
    return payload


def test_forecast_dataset_bundle_accepts_ordered_future_known_covariate() -> None:
    manifest = forecast_bundle()
    assert validate_dataset_bundle(manifest).status == "EXECUTABLE"


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (
            lambda m: m["identity_payload"]["components"][0]["channels"].append(channel("close", index=2)),
            "channels.channel_id must be unique",
        ),
        (
            lambda m: m["identity_payload"]["components"][0]["channels"][1].update({"channel_index": 3}),
            "channels.channel_index must be contiguous from zero",
        ),
        (
            lambda m: m["identity_payload"]["components"][0]["channels"][1].update({"missingness_policy": "AMBIGUOUS"}),
            "missingness_policy must be explicit",
        ),
        (
            lambda m: m["identity_payload"]["components"][0]["channels"][1]["temporal_availability"].update(
                {"available_at": "2026-09-01T00:00:00+00:00"}
            ),
            "available_at must be <= forecast_origin",
        ),
    ],
)
def test_forecast_dataset_bundle_fails_closed_on_ambiguous_channels(mutate, expected: str) -> None:
    manifest = forecast_bundle()
    mutate(manifest)
    result = validate_dataset_bundle(manifest)
    assert result.status == "NOT_EXECUTABLE"
    assert any(expected in error for error in result.errors)


def test_forecast_trial_spec_is_independent_and_rejects_strategy_pollution() -> None:
    payload = forecast_trial_spec()
    assert validate_forecast_trial_spec(payload) == []

    polluted = deepcopy(payload)
    polluted["parameters"] = {"horizon": 5, "stop_loss_pct": 0.08}
    polluted["ranking_source_authority"] = {"ranking_source_hash": SHA_A}
    errors = validate_forecast_trial_spec(polluted)
    assert "strategy parameters are not allowed in forecast trial spec" in errors
    assert "ranking_source_authority is not allowed" in errors


def test_forecast_artifact_receipt_binds_point_quantile_and_license_refs() -> None:
    payload = forecast_receipt()
    assert validate_forecast_artifact_receipt(payload) == []

    missing_quantile = deepcopy(payload)
    missing_quantile["forecast_artifacts"] = [missing_quantile["forecast_artifacts"][0]]
    errors = validate_forecast_artifact_receipt(missing_quantile)
    assert "forecast_artifacts must contain exactly POINT_FORECAST and QUANTILE_FORECAST" in errors

    missing_license = deepcopy(payload)
    missing_license["forecast_artifacts"][0]["license_refs"] = []
    errors = validate_forecast_artifact_receipt(missing_license)
    assert "forecast_artifacts[0].license_refs must equal receipt license_refs" in errors


def test_forecast_contracts_reject_non_finite_decimals() -> None:
    spec = forecast_trial_spec()
    spec["prediction_contract"]["quantiles"]["levels"] = ["0.1", "NaN"]
    assert "prediction_contract.quantiles.levels[1] must be finite decimal string" in validate_forecast_trial_spec(spec)

    observation = forecast_observation()
    observation["metrics"]["mae"] = "Infinity"
    assert "metrics.mae must be finite decimal string" in validate_forecast_evaluation_observation(observation)


def test_forecast_evaluation_observation_stays_outside_research_observation_identity() -> None:
    payload = forecast_observation()
    assert validate_forecast_evaluation_observation(payload) == []
    assert "schema_version is invalid" in validate_observation_identity(payload)
