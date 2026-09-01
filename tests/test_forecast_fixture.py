from __future__ import annotations

from copy import deepcopy

import pytest

from app.research.contracts import canonical_json_bytes, content_hash, validate_observation_identity
from app.research.dataset_bundle import validate_dataset_bundle
from app.research.forecast_contracts import validate_forecast_artifact_receipt
from app.research.forecast_fixture import (
    EFFECTIVE_USAGE_STATUSES,
    ForecastFixture,
    build_forecast_fixture,
    clone_fixture,
    validate_forecast_fixture_links,
)


def test_forecast_fixture_builds_deterministic_closed_loop(tmp_path) -> None:
    first = build_forecast_fixture(tmp_path / "first")
    second = build_forecast_fixture(tmp_path / "second")

    assert first.dataset_bundle == second.dataset_bundle
    assert first.trial_spec == second.trial_spec
    assert first.artifact_receipt == second.artifact_receipt
    assert first.evaluation_observation == second.evaluation_observation
    assert validate_forecast_fixture_links(tmp_path / "first", first) == []


def test_forecast_fixture_rejects_bundle_spec_identity_mismatch(tmp_path) -> None:
    fixture = clone_fixture(build_forecast_fixture(tmp_path))
    fixture.trial_spec["dataset_bundle_id"] = content_hash({"other": "dataset"})
    fixture.trial_spec["forecast_trial_spec_id"] = content_hash(
        fixture.trial_spec, omit={"forecast_trial_spec_id"}
    )

    errors = validate_forecast_fixture_links(tmp_path, fixture)
    assert "trial_spec.dataset_bundle_id must equal dataset bundle identity" in errors


def test_forecast_fixture_rejects_artifact_byte_tampering(tmp_path) -> None:
    fixture = build_forecast_fixture(tmp_path)
    first_artifact = fixture.artifact_receipt["forecast_artifacts"][0]
    path = tmp_path / first_artifact["corpus_path"]
    path.write_bytes(canonical_json_bytes({"tampered": True}))

    errors = validate_forecast_fixture_links(tmp_path, fixture)
    assert any("artifact bytes do not match receipt digest" in error for error in errors)


def test_forecast_fixture_rejects_receipt_artifact_digest_swap(tmp_path) -> None:
    fixture = clone_fixture(build_forecast_fixture(tmp_path))
    point = fixture.artifact_receipt["forecast_artifacts"][0]
    quantile = fixture.artifact_receipt["forecast_artifacts"][1]
    point["artifact_id"] = quantile["artifact_id"]
    point["corpus_path"] = quantile["corpus_path"]
    fixture.artifact_receipt["receipt_id"] = content_hash(
        fixture.artifact_receipt, omit={"receipt_id"}
    )

    errors = validate_forecast_fixture_links(tmp_path, fixture)
    assert "artifact_receipt.forecast_artifacts.artifact_id must be unique" in errors


def test_forecast_fixture_rejects_production_like_usage_status(tmp_path) -> None:
    fixture = clone_fixture(build_forecast_fixture(tmp_path))
    fixture.artifact_receipt["effective_usage_statuses"] = ["PRODUCTION_SIGNAL_EXPORT"]
    fixture.artifact_receipt["receipt_id"] = content_hash(
        fixture.artifact_receipt, omit={"receipt_id"}
    )

    errors = validate_forecast_fixture_links(tmp_path, fixture)
    assert (
        "artifact_receipt.effective_usage_statuses must exactly match allowed research statuses"
        in errors
    )


def test_forecast_fixture_rejects_available_at_leakage(tmp_path) -> None:
    fixture = build_forecast_fixture(tmp_path)
    leaked = deepcopy(fixture.dataset_bundle)
    leaked["identity_payload"]["components"][0]["channels"][2]["temporal_availability"][
        "available_at"
    ] = "2026-09-02T00:00:00+00:00"

    result = validate_dataset_bundle(leaked)
    assert result.status == "NOT_EXECUTABLE"
    assert any(
        "available_at must be <= forecast_origin for FUTURE_KNOWN_COVARIATE" in error
        for error in result.errors
    )


def test_forecast_fixture_stays_outside_strategy_observation_identity(tmp_path) -> None:
    fixture = build_forecast_fixture(tmp_path)
    errors = validate_observation_identity(fixture.evaluation_observation)

    assert "schema_version is invalid" in errors
    assert "origin_execution_id is required" in errors
    assert "executed_lineage_id is required" in errors
    assert "forecast_artifact_receipt_id is not allowed" in errors
    assert "metrics is not allowed" in errors


def test_forecast_fixture_effective_usage_statuses_are_fixed(tmp_path) -> None:
    fixture = build_forecast_fixture(tmp_path)

    assert fixture.artifact_receipt["effective_usage_statuses"] == EFFECTIVE_USAGE_STATUSES
    assert validate_forecast_artifact_receipt(fixture.artifact_receipt) == []


def test_forecast_fixture_contract_has_no_timesfm_fields(tmp_path) -> None:
    fixture = build_forecast_fixture(tmp_path)
    serialized = canonical_json_bytes(
        {
            "dataset_bundle": fixture.dataset_bundle,
            "trial_spec": fixture.trial_spec,
            "artifact_receipt": fixture.artifact_receipt,
            "evaluation_observation": fixture.evaluation_observation,
        }
    )

    assert b"TimesFM" not in serialized
    assert b"timesfm" not in serialized
