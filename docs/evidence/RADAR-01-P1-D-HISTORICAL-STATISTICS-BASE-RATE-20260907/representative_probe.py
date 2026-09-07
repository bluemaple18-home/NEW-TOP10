"""P1-D 代表性本機資料 probe；只建立暫存 validation-only snapshot。"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.pipeline.daily_close_snapshot import (
    FINALIZATION_AUTHORITY,
    RECORD_COLUMNS,
    materialize_daily_close_snapshot,
)
from app.research.contracts import content_hash
from app.signals import (
    INITIAL_SIGNAL_SPECS,
    SignalEligibilityStatus,
    build_signal_historical_statistics,
)


FEATURE_PATH = ROOT / "data" / "clean" / "features.parquet"
PATTERN_PATH = ROOT / "app" / "indicators" / "mixins" / "pattern.py"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _git_blob_ref(path: Path) -> str:
    payload = path.read_bytes()
    digest = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload)
    return "git-sha1:" + digest.hexdigest()


def _signal_summary(item) -> dict[str, object]:
    conditional = item.conditional
    baseline = item.baseline
    edge = item.incremental_edge
    recomputed_rate_edge = None
    if (
        conditional.direction_positive_rate is not None
        and baseline.direction_positive_rate is not None
    ):
        recomputed_rate_edge = (
            conditional.direction_positive_rate
            - baseline.direction_positive_rate
        ) * 100.0
    return {
        "signal_id": item.signal_id,
        "direction": item.direction,
        "horizon_sessions": item.forward_horizon_sessions,
        "coverage": {
            "evaluated_rows": item.coverage.evaluated_rows,
            "triggered_rows": item.coverage.triggered_rows,
            "not_triggered_rows": item.coverage.not_triggered_rows,
            "not_observable_rows": item.coverage.not_observable_rows,
            "triggered_complete_outcomes": item.coverage.triggered_complete_outcomes,
            "triggered_outcome_incomplete_rows": item.coverage.triggered_outcome_incomplete_rows,
        },
        "conditional": {
            "raw_sample_size": conditional.raw_sample_size,
            "effective_sample_size": conditional.effective_sample_size,
            "overlap_count": conditional.overlap_count,
            "event_date_count": conditional.event_date_count,
            "direction_positive_rate": conditional.direction_positive_rate,
            "mean_return": conditional.mean_return,
            "median_return": conditional.median_return,
            "mae_mean": conditional.maximum_adverse_excursion_mean,
        },
        "baseline": {
            "raw_sample_size": baseline.raw_sample_size,
            "effective_sample_size": baseline.effective_sample_size,
            "overlap_count": baseline.overlap_count,
            "event_date_count": baseline.event_date_count,
            "direction_positive_rate": baseline.direction_positive_rate,
            "mean_return": baseline.mean_return,
            "median_return": baseline.median_return,
        },
        "incremental_edge": {
            "direction_positive_rate_percentage_points": edge.direction_positive_rate_percentage_points,
            "mean_return_edge": edge.mean_return_edge,
            "median_return_edge": edge.median_return_edge,
            "rate_edge_recomputes": edge.direction_positive_rate_percentage_points
            == recomputed_rate_edge,
        },
        "raw_effective_overlap_closes": (
            conditional.raw_sample_size
            == conditional.effective_sample_size + conditional.overlap_count
            and baseline.raw_sample_size
            == baseline.effective_sample_size + baseline.overlap_count
        ),
        "coverage_closes": item.coverage.evaluated_rows
        == (
            item.coverage.triggered_rows
            + item.coverage.not_triggered_rows
            + item.coverage.not_observable_rows
        ),
    }


def main() -> int:
    features = pd.read_parquet(FEATURE_PATH)
    raw = features.loc[:, list(RECORD_COLUMNS)].copy()
    start = pd.Timestamp(raw["date"].min()).date().isoformat()
    end = pd.Timestamp(raw["date"].max()).date().isoformat()
    feature_content_id = _sha256_file(FEATURE_PATH)
    indicator_ref = _git_blob_ref(PATTERN_PATH)
    specs = tuple(
        replace(
            spec,
            evaluation_horizon_days=5,
            research_evidence_ref="test-only://radar-p1d/representative-replay",
            eligibility_status=SignalEligibilityStatus.RADAR_ELIGIBLE,
        )
        for spec in INITIAL_SIGNAL_SPECS.values()
    )
    with tempfile.TemporaryDirectory(prefix="radar-p1d-representative-") as temp:
        snapshot = materialize_daily_close_snapshot(
            raw,
            root=Path(temp) / "daily-close-snapshots",
            source={
                "provider_identity": f"validation-file@{feature_content_id}",
                "adapter_contract": "radar-p1d-legacy-clean-replay.v1",
                "endpoint_contract": {
                    "transport": "LOCAL_FILE",
                    "format": "parquet",
                    "finalization_authority": FINALIZATION_AUTHORITY,
                },
            },
            fetched_at="2026-09-07T09:30:00Z",
            requested_start=start,
            requested_end=end,
        )
        first = build_signal_historical_statistics(
            snapshot.manifest_path,
            FEATURE_PATH,
            indicator_semantics_ref=indicator_ref,
            specs=specs,
        )
        second = build_signal_historical_statistics(
            snapshot.manifest_path,
            FEATURE_PATH,
            indicator_semantics_ref=indicator_ref,
            specs=specs,
        )
        default = build_signal_historical_statistics(
            snapshot.manifest_path,
            FEATURE_PATH,
            indicator_semantics_ref=indicator_ref,
        )
        summaries = [_signal_summary(item) for item in first.signal_statistics]
        payload = {
            "authority": "VALIDATION_ONLY_NO_ELIGIBILITY_OR_RANKING_AUTHORITY",
            "feature_source": str(FEATURE_PATH.relative_to(ROOT)),
            "input": {
                "rows": len(features),
                "stocks": int(features["stock_id"].nunique()),
                "date_start": start,
                "date_end": end,
                "markets": sorted(features["market"].astype(str).unique()),
                "feature_content_id": feature_content_id,
                "snapshot_id": first.snapshot_id,
                "records_content_id": first.records_content_id,
            },
            "result": {
                "contract_version": first.contract_version,
                "status": first.status.value,
                "result_content_id": first.result_content_id,
                "result_id_recomputes": first.result_content_id
                == content_hash(first.identity_payload()),
                "replay_result_content_id": second.result_content_id,
                "deterministic_replay_equal": first == second,
                "eligible_signal_count": first.eligible_signal_count,
                "price_return_basis": first.price_return_basis,
                "effective_sample_policy": first.effective_sample_policy,
                "research_status": first.research_status,
                "oos_status": first.oos_status,
                "sealed_status": first.sealed_status,
                "authority_scope": first.authority_scope,
                "warning_reason_codes": sorted(
                    {warning.reason_code for warning in first.warnings}
                ),
                "signals": summaries,
                "all_sample_counts_close": all(
                    item["raw_effective_overlap_closes"] for item in summaries
                ),
                "all_coverage_counts_close": all(
                    item["coverage_closes"] for item in summaries
                ),
                "all_rate_edges_recompute": all(
                    item["incremental_edge"]["rate_edge_recomputes"]
                    for item in summaries
                ),
            },
            "default_catalog": {
                "status": default.status.value,
                "eligible_signal_count": default.eligible_signal_count,
                "statistics_count": len(default.signal_statistics),
                "authority_scope": default.authority_scope,
                "warning_reason_codes": [
                    warning.reason_code for warning in default.warnings
                ],
            },
            "limitations": [
                "temporary validation-only snapshot, not official materialized Daily Close runtime evidence",
                "UNADJUSTED price return, not total return; dividends, fees, tax and corporate actions are excluded",
                "NOT_OOS and NOT_SEALED; no statistical-significance or causal claim",
                "validation-only eligible clones do not mutate the default CONTRACT_ONLY catalog",
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
