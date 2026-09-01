"""FC2 forecast deterministic fixture 的建立與驗證工具。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from app.research.contracts import CANONICALIZATION_VERSION, canonical_json_bytes, content_hash
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
    artifact_receipt: dict[str, Any]
    evaluation_observation: dict[str, Any]
    content_identity: str
    written_paths: dict[str, str]


@dataclass(frozen=True)
class ForecastFixture:
    dataset_bundle: dict[str, Any]
    trial_spec: dict[str, Any]
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
    receipt: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> str:
    artifact_ids = sorted(str(item["artifact_id"]) for item in receipt["forecast_artifacts"])
    return content_hash(
        {
            "schema_version": "forecast-fixture-content-identity.v1",
            "dataset_bundle_id": dataset_bundle["dataset_bundle_id"],
            "forecast_trial_spec_id": spec["forecast_trial_spec_id"],
            "forecast_artifact_receipt_id": receipt["receipt_id"],
            "forecast_evaluation_observation_id": observation["observation_id"],
            "artifact_ids": artifact_ids,
        }
    )


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

    return ForecastFixtureResult(
        corpus_root=corpus_root,
        dataset_bundle=dataset_bundle,
        forecast_trial_spec=spec,
        artifact_receipt=receipt,
        evaluation_observation=observation,
        content_identity=_content_identity(dataset_bundle, spec, receipt, observation),
        written_paths={
            "channel_frame": str(channel_frame_path.relative_to(corpus_root)),
            "dataset_bundle": str(dataset_write.path.relative_to(corpus_root)),
            "forecast_trial_spec": str(spec_write.path.relative_to(corpus_root)),
            "point_artifact": str(point_path.relative_to(corpus_root)),
            "quantile_artifact": str(quantile_path.relative_to(corpus_root)),
            "artifact_receipt": str(receipt_write.path.relative_to(corpus_root)),
            "evaluation_observation": str(observation_write.path.relative_to(corpus_root)),
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
        artifact_receipt=deepcopy(fixture.artifact_receipt),
        evaluation_observation=deepcopy(fixture.evaluation_observation),
        corpus_root=fixture.corpus_root,
        content_identity=fixture.content_identity,
        written_paths=deepcopy(fixture.written_paths),
    )
