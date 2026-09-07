from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from app.signals import INITIAL_SIGNAL_SPECS, SignalEligibilityStatus
from app.research.contracts import content_hash
from app.signals.scanner import (
    DailySignalScanHit,
    DailySignalScanStatus,
    DailySignalScanWarning,
    scan_finalized_daily_signals,
)
from app.signals.radar_projection import build_daily_radar_projection
from app.signals.occurrences import SignalOccurrenceError

from tests.test_daily_signal_scanner import (
    INDICATOR_SEMANTICS_REF,
    _features,
    _snapshot,
    _write_features,
)


def _eligible(signal_id: str):
    return replace(
        INITIAL_SIGNAL_SPECS[signal_id],
        evaluation_horizon_days=5,
        research_evidence_ref=f"test-only://radar-p1c/{signal_id}",
        eligibility_status=SignalEligibilityStatus.RADAR_ELIGIBLE,
    )


def _report(tmp_path: Path, *, specs=None, frame: pd.DataFrame | None = None):
    snapshot = _snapshot(tmp_path)
    feature_frame = _features(snapshot.frame) if frame is None else frame
    feature_path = _write_features(tmp_path, feature_frame)
    report = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=specs,
    )
    return snapshot, report


def test_triggered_hits_become_content_addressed_occurrences(tmp_path: Path) -> None:
    spec = _eligible("rsi_rebound_from_40")
    snapshot, report = _report(tmp_path, specs=(spec,))

    projection = build_daily_radar_projection(
        report,
        snapshot.manifest_path,
        specs=(spec,),
    )

    assert projection.ranking_impact == "NONE"
    assert projection.no_eligible is False
    assert projection.occurrence_count == 1
    occurrence = projection.occurrences[0]
    assert occurrence.occurrence_id.startswith("sha256:")
    assert occurrence.instrument_id == "2330"
    assert occurrence.trading_date == "2026-09-03"
    assert occurrence.evaluation == "TRIGGERED"
    assert occurrence.signal_id == spec.signal_id
    assert occurrence.signal_version == spec.signal_version
    assert occurrence.spec_content_id == spec.spec_content_id
    assert occurrence.direction == spec.direction.value
    assert occurrence.snapshot_id == snapshot.manifest["snapshot_id"]
    assert occurrence.records_content_id == report.records_content_id
    assert occurrence.feature_artifact_content_id == report.feature_artifact_content_id
    assert occurrence.indicator_semantics_ref == INDICATOR_SEMANTICS_REF
    assert occurrence.research_evidence_ref == spec.research_evidence_ref
    assert occurrence.provider_identity == snapshot.manifest["identity_payload"]["source"][
        "provider_identity"
    ]
    assert occurrence.source_endpoint_provenance_content_id == content_hash(
        snapshot.manifest["identity_payload"]["source"]
    )
    assert not hasattr(occurrence, "endpoint_contract")
    assert occurrence.occurrence_id == content_hash(occurrence.identity_payload())
    assert projection.items[0].bullish_occurrence_ids == (occurrence.occurrence_id,)
    assert projection.items[0].bearish_occurrence_ids == ()
    assert projection.items[0].neutral_occurrence_ids == ()


def test_projection_replay_is_deterministic(tmp_path: Path) -> None:
    spec = _eligible("rsi_rebound_from_40")
    snapshot, report = _report(tmp_path, specs=(spec,))

    first = build_daily_radar_projection(report, snapshot.manifest_path, specs=(spec,))
    second = build_daily_radar_projection(report, snapshot.manifest_path, specs=(spec,))

    assert first == second
    assert first.projection_id == second.projection_id
    assert first.projection_id == content_hash(first.identity_payload())
    assert [item.instrument_id for item in first.items] == ["2330"]


def test_default_catalog_outputs_explicit_no_eligible_projection(tmp_path: Path) -> None:
    snapshot, report = _report(tmp_path)

    projection = build_daily_radar_projection(report, snapshot.manifest_path)

    assert projection.no_eligible is True
    assert projection.eligible_signal_count == 0
    assert projection.occurrences == ()
    assert projection.items == ()
    assert projection.ranking_impact == "NONE"
    assert [warning.reason_code for warning in projection.warnings] == [
        "NO_RADAR_ELIGIBLE_SIGNAL_SPEC"
    ]


@pytest.mark.parametrize(
    ("mutate", "reason_code"),
    [
        (
            lambda report: replace(report, snapshot_id="sha256:" + "0" * 64),
            "RADAR_REPORT_SNAPSHOT_ID_MISMATCH",
        ),
        (
            lambda report: replace(report, scan_date="2026-09-02"),
            "RADAR_REPORT_SCAN_DATE_MISMATCH",
        ),
        (
            lambda report: replace(report, feature_artifact_content_id="latest"),
            "RADAR_REPORT_FEATURE_ARTIFACT_ID_INVALID",
        ),
        (
            lambda report: replace(report, indicator_semantics_ref="latest"),
            "RADAR_REPORT_INDICATOR_SEMANTICS_REF_INVALID",
        ),
        (
            lambda report: replace(
                report,
                signal_summaries=(
                    replace(report.signal_summaries[0], triggered_rows=2),
                ),
            ),
            "RADAR_REPORT_SUMMARY_COUNT_DRIFT",
        ),
        (
            lambda report: replace(
                report,
                hits=(
                    replace(report.hits[0], direction="BEARISH"),
                ),
            ),
            "RADAR_REPORT_HIT_SPEC_DRIFT",
        ),
        (
            lambda report: replace(report, hits=(report.hits[0], report.hits[0])),
            "RADAR_REPORT_HIT_DUPLICATE",
        ),
    ],
)
def test_tampered_report_fails_closed(tmp_path: Path, mutate, reason_code: str) -> None:
    spec = _eligible("rsi_rebound_from_40")
    snapshot, report = _report(tmp_path, specs=(spec,))

    with pytest.raises(SignalOccurrenceError) as caught:
        build_daily_radar_projection(mutate(report), snapshot.manifest_path, specs=(spec,))

    assert caught.value.reason_code == reason_code


def test_partial_report_preserves_warning_evidence(tmp_path: Path) -> None:
    spec = _eligible("rsi_rebound_from_40")
    snapshot = _snapshot(tmp_path)
    frame = _features(snapshot.frame)
    missing = pd.to_datetime(frame["date"]).eq(pd.Timestamp("2026-09-03")) & frame[
        "stock_id"
    ].eq("6488")
    feature_path = _write_features(tmp_path, frame.loc[~missing].copy())
    report = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(spec,),
    )

    projection = build_daily_radar_projection(report, snapshot.manifest_path, specs=(spec,))

    assert projection.coverage_status == "PARTIAL"
    assert projection.feature_missing_row_count == 1
    assert projection.warnings == report.warnings
    assert [warning.stage for warning in projection.warnings] == [
        "FEATURE_PROJECTION_ALIGNMENT",
        "SIGNAL_EVALUATION",
    ]
    assert projection.occurrence_count == 1


def test_multidirection_hits_are_grouped_without_score_or_rank(tmp_path: Path) -> None:
    bullish = _eligible("rsi_rebound_from_40")
    bearish = _eligible("rsi_break_below_50")
    snapshot, report = _report(tmp_path, specs=(bearish, bullish))

    projection = build_daily_radar_projection(
        report,
        snapshot.manifest_path,
        specs=(bearish, bullish),
    )

    assert [item.instrument_id for item in projection.items] == ["2330", "6488"]
    assert projection.items[0].bullish_occurrence_ids
    assert projection.items[0].bearish_occurrence_ids == ()
    assert projection.items[1].bullish_occurrence_ids == ()
    assert projection.items[1].bearish_occurrence_ids
    assert not hasattr(projection.items[0], "score")
    assert not hasattr(projection.items[0], "rank")


def test_occurrence_builder_rejects_non_triggered_synthetic_hit(
    tmp_path: Path,
) -> None:
    spec = _eligible("rsi_rebound_from_40")
    snapshot, report = _report(tmp_path, specs=(spec,))
    synthetic = DailySignalScanHit(
        trading_date=report.scan_date,
        stock_id="6488",
        signal_id=spec.signal_id,
        signal_version=spec.signal_version,
        spec_content_id=spec.spec_content_id,
        direction=spec.direction.value,
    )

    with pytest.raises(SignalOccurrenceError) as caught:
        build_daily_radar_projection(
            replace(report, hits=(report.hits[0], synthetic)),
            snapshot.manifest_path,
            specs=(spec,),
        )

    assert caught.value.reason_code == "RADAR_REPORT_HIT_COUNT_DRIFT"


@pytest.mark.parametrize(
    ("mutate", "reason_code"),
    [
        (
            lambda report: replace(report, hits=(replace(report.hits[0], stock_id="9999"),)),
            "RADAR_REPORT_HIT_INSTRUMENT_OUTSIDE_SNAPSHOT",
        ),
        (
            lambda report: replace(report, hits=(replace(report.hits[0], stock_id=""),)),
            "RADAR_REPORT_NESTED_FIELD_INVALID",
        ),
        (
            lambda report: replace(report, hits=(replace(report.hits[0], stock_id=2330),)),
            "RADAR_REPORT_NESTED_FIELD_INVALID",
        ),
        (lambda report: replace(report, status="COMPLETE"), "RADAR_REPORT_STATUS_TYPE_INVALID"),
        (lambda report: replace(report, eligible_signal_count=True), "RADAR_REPORT_COVERAGE_COUNT_INVALID"),
        (
            lambda report: replace(
                report,
                signal_summaries=(replace(report.signal_summaries[0], evaluated_rows=True),),
            ),
            "RADAR_REPORT_SUMMARY_COUNT_INVALID",
        ),
        (
            lambda report: replace(report, signal_summaries=(object(),)),
            "RADAR_REPORT_NESTED_TYPE_INVALID",
        ),
        (lambda report: replace(report, hits=(object(),)), "RADAR_REPORT_NESTED_TYPE_INVALID"),
        (lambda report: replace(report, warnings=(object(),)), "RADAR_REPORT_NESTED_TYPE_INVALID"),
        (
            lambda report: replace(report, warnings=(replace(report.warnings[0], affected_count=True),)),
            "RADAR_REPORT_WARNING_FIELD_INVALID",
        ),
        (
            lambda report: replace(report, feature_artifact_content_id=None),
            "RADAR_REPORT_FIELD_INVALID",
        ),
        (
            lambda report: replace(report, indicator_semantics_ref=None),
            "RADAR_REPORT_FIELD_INVALID",
        ),
        (lambda report: replace(report, records_content_id=None), "RADAR_REPORT_FIELD_INVALID"),
    ],
)
def test_malformed_report_is_rejected_before_projection(
    tmp_path: Path, mutate, reason_code: str
) -> None:
    spec = _eligible("rsi_rebound_from_40")
    snapshot, report = _report(tmp_path, specs=(spec,))
    if not report.warnings:
        report = replace(
            report,
            status=DailySignalScanStatus.PARTIAL,
            warnings=(
                DailySignalScanWarning(
                    record_key="2026-09-03|2330",
                    signal_id=spec.signal_id,
                    reason_code="TEST_WARNING",
                    stage="TEST",
                    affected_count=1,
                ),
            ),
        )

    with pytest.raises(SignalOccurrenceError) as caught:
        build_daily_radar_projection(mutate(report), snapshot.manifest_path, specs=(spec,))

    assert caught.value.reason_code == reason_code
