from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from app.pipeline.daily_close_snapshot import materialize_daily_close_snapshot
from app.signals import (
    INITIAL_SIGNAL_SPECS,
    SignalCalendarPolicy,
    SignalEligibilityStatus,
)


SOURCE = {
    "provider_identity": "scanner-fixture@2026-09-07",
    "adapter_contract": "scanner-fixture.v1",
    "endpoint_contract": {
        "method": "GET",
        "path": "/daily-close",
        "finalization_authority": "OFFICIAL_FINALIZED_DAILY_ENDPOINT_V1",
    },
}
INDICATOR_SEMANTICS_REF = "git-sha1:" + "1" * 40


def _quotes(
    *,
    dates: tuple[str, ...] = ("2026-09-01", "2026-09-02", "2026-09-03"),
    stocks: tuple[tuple[str, str], ...] = (("2330", "TWSE"), ("6488", "TPEX")),
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for day_index, day in enumerate(dates):
        for stock_index, (stock_id, market) in enumerate(stocks):
            close = 100 + stock_index * 20 + day_index
            rows.append(
                {
                    "date": day,
                    "stock_id": stock_id,
                    "stock_name": f"測試股票{stock_id}",
                    "market": market,
                    "open": close - 1,
                    "high": close + 2,
                    "low": close - 2,
                    "close": close,
                    "volume": 1_000 + day_index,
                    "value": close * (1_000 + day_index),
                    "transactions": 100 + day_index,
                }
            )
    return pd.DataFrame(rows)


def _snapshot(
    tmp_path: Path,
    frame: pd.DataFrame | None = None,
    *,
    requested_start: str = "2026-09-01",
    requested_end: str = "2026-09-03",
    expected_markets: tuple[str, ...] = ("TPEX", "TWSE"),
):
    return materialize_daily_close_snapshot(
        _quotes() if frame is None else frame,
        root=tmp_path / "snapshots",
        source=SOURCE,
        fetched_at="2026-09-07T09:30:00Z",
        requested_start=requested_start,
        requested_end=requested_end,
        expected_markets=expected_markets,
    )


def _features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["ma5"] = 10.0
    output["ma20"] = 11.0
    output["rsi"] = 50.0
    output["ma5_cross_ma20_up"] = 0
    output["ma5_cross_ma20_down"] = 0
    output["rsi_rebound_from_40"] = 0
    output["rsi_break_below_50"] = 0

    first = output["stock_id"].eq("2330")
    second = output["stock_id"].eq("6488")
    dates = pd.to_datetime(output["date"])
    output.loc[first & dates.eq(pd.Timestamp("2026-09-01")), "rsi"] = 35
    output.loc[first & dates.eq(pd.Timestamp("2026-09-02")), "rsi"] = 38
    output.loc[first & dates.eq(pd.Timestamp("2026-09-03")), "rsi"] = 45
    output.loc[
        first & dates.eq(pd.Timestamp("2026-09-03")), "rsi_rebound_from_40"
    ] = 1
    output.loc[second & dates.eq(pd.Timestamp("2026-09-01")), "rsi"] = 55
    output.loc[second & dates.eq(pd.Timestamp("2026-09-02")), "rsi"] = 52
    output.loc[second & dates.eq(pd.Timestamp("2026-09-03")), "rsi"] = 48
    output.loc[
        second & dates.eq(pd.Timestamp("2026-09-03")), "rsi_break_below_50"
    ] = 1
    return output


def _write_features(tmp_path: Path, frame: pd.DataFrame) -> Path:
    path = tmp_path / "features.parquet"
    frame.to_parquet(path, index=False)
    return path


def _eligible(signal_id: str = "rsi_rebound_from_40"):
    return replace(
        INITIAL_SIGNAL_SPECS[signal_id],
        evaluation_horizon_days=5,
        research_evidence_ref="test-only://radar-p1b/scanner-behavior",
        eligibility_status=SignalEligibilityStatus.RADAR_ELIGIBLE,
    )


def test_scanner_evaluates_each_as_of_market_row_exactly_once(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScanStatus, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    feature_path = _write_features(tmp_path, _features(snapshot.frame))

    report = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(_eligible(),),
    )

    assert report.status is DailySignalScanStatus.COMPLETE
    assert report.scan_date == "2026-09-03"
    assert report.snapshot_row_count == 2
    assert report.feature_matched_row_count == 2
    assert report.feature_missing_row_count == 0
    assert report.eligible_signal_count == 1
    assert len(report.signal_summaries) == 1
    summary = report.signal_summaries[0]
    assert summary.evaluated_rows == 2
    assert summary.triggered_rows == 1
    assert summary.not_triggered_rows == 1
    assert summary.not_observable_rows == 0
    assert summary.evaluated_rows == (
        summary.triggered_rows
        + summary.not_triggered_rows
        + summary.not_observable_rows
    )
    assert [(hit.stock_id, hit.signal_id) for hit in report.hits] == [
        ("2330", "rsi_rebound_from_40")
    ]


def test_default_catalog_cannot_bypass_radar_eligibility(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScanStatus, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    feature_path = _write_features(tmp_path, _features(snapshot.frame))

    report = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
    )

    assert report.status is DailySignalScanStatus.NO_RADAR_ELIGIBLE_SIGNAL_SPEC
    assert report.eligible_signal_count == 0
    assert report.signal_summaries == ()
    assert report.hits == ()
    assert [warning.reason_code for warning in report.warnings] == [
        "NO_RADAR_ELIGIBLE_SIGNAL_SPEC"
    ]


def test_explicit_contract_only_spec_is_rejected(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    feature_path = _write_features(tmp_path, _features(snapshot.frame))

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=(INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"],),
        )

    assert caught.value.reason_code == "SCAN_SPEC_NOT_RADAR_ELIGIBLE"


def test_unresolved_empty_snapshot_is_rejected(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    empty = _quotes().iloc[0:0]
    snapshot = _snapshot(tmp_path, empty)
    feature_path = _write_features(tmp_path, _features(empty))

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        )

    assert caught.value.reason_code == "SCAN_SNAPSHOT_UNRESOLVED"


def test_records_hash_drift_is_rejected(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    feature_path = _write_features(tmp_path, _features(snapshot.frame))
    snapshot.records_path.write_bytes(b"corrupt")

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        )

    assert caught.value.reason_code == "SCAN_SNAPSHOT_INVALID"


def test_feature_symlink_is_rejected(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    feature_path = _write_features(tmp_path, _features(snapshot.frame))
    symlink = tmp_path / "features-link.parquet"
    symlink.symlink_to(feature_path)

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            symlink,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        )

    assert caught.value.reason_code == "SCAN_FEATURE_ARTIFACT_INVALID"


def test_feature_key_outside_snapshot_is_rejected(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    frame = _features(snapshot.frame)
    extra = frame.iloc[[-1]].copy()
    extra["stock_id"] = "9999"
    feature_path = _write_features(tmp_path, pd.concat([frame, extra], ignore_index=True))

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=(_eligible(),),
        )

    assert caught.value.reason_code == "SCAN_FEATURE_KEY_OUTSIDE_SNAPSHOT"


def test_missing_required_signal_column_has_stable_schema_error(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    frame = _features(snapshot.frame).drop(columns=["rsi_rebound_from_40"])
    feature_path = _write_features(tmp_path, frame)

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=(_eligible(),),
        )

    assert caught.value.reason_code == "SCAN_FEATURE_SCHEMA_INVALID"


def test_daily_close_value_drift_is_rejected(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    frame = _features(snapshot.frame)
    frame.loc[frame.index[-1], "close"] += 1
    feature_path = _write_features(tmp_path, frame)

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=(_eligible(),),
        )

    assert caught.value.reason_code == "SCAN_DAILY_CLOSE_VALUE_DRIFT"


def test_missing_feature_projection_row_is_not_observable(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScanStatus, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    frame = _features(snapshot.frame)
    as_of_missing = pd.to_datetime(frame["date"]).eq(pd.Timestamp("2026-09-03")) & frame[
        "stock_id"
    ].eq("6488")
    feature_path = _write_features(tmp_path, frame.loc[~as_of_missing].copy())

    report = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(_eligible(),),
    )

    assert report.status is DailySignalScanStatus.PARTIAL
    assert report.feature_missing_row_count == 1
    summary = report.signal_summaries[0]
    assert summary.evaluated_rows == 2
    assert summary.triggered_rows == 1
    assert summary.not_triggered_rows == 0
    assert summary.not_observable_rows == 1
    warning = next(
        item
        for item in report.warnings
        if item.reason_code == "FEATURE_PROJECTION_ROW_MISSING"
    )
    assert warning.record_key == "2026-09-03/6488"
    assert warning.affected_count == 1


def test_invalid_nullable_raw_value_cannot_masquerade_as_missing(tmp_path: Path) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    quotes = _quotes().drop(columns=["transactions"])
    snapshot = _snapshot(tmp_path, quotes)
    frame = _features(snapshot.frame)
    frame["transactions"] = frame["transactions"].astype(object)
    frame.loc[frame.index[-1], "transactions"] = "invalid"
    feature_path = _write_features(tmp_path, frame)

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=(_eligible(),),
        )

    assert caught.value.reason_code == "SCAN_DAILY_CLOSE_VALUE_DRIFT"


def test_dataset_session_policy_does_not_cross_unresolved_weekday_gap(
    tmp_path: Path,
) -> None:
    from app.signals.scanner import DailySignalScanStatus, scan_finalized_daily_signals

    quotes = _quotes(
        dates=("2026-09-01", "2026-09-02", "2026-09-04"),
        stocks=(("2330", "TWSE"),),
    )
    snapshot = _snapshot(
        tmp_path,
        quotes,
        requested_end="2026-09-04",
        expected_markets=("TWSE",),
    )
    frame = _features(snapshot.frame)
    frame.loc[pd.to_datetime(frame["date"]).eq(pd.Timestamp("2026-09-02")), "rsi"] = 38
    frame.loc[pd.to_datetime(frame["date"]).eq(pd.Timestamp("2026-09-04")), "rsi"] = 45
    frame.loc[
        pd.to_datetime(frame["date"]).eq(pd.Timestamp("2026-09-04")),
        "rsi_rebound_from_40",
    ] = 1
    feature_path = _write_features(tmp_path, frame)

    strict_report = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(_eligible(),),
    )
    observed_report = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(
            replace(
                _eligible(),
                calendar_policy=SignalCalendarPolicy.PREVIOUS_OBSERVED_ROW,
            ),
        ),
    )

    assert strict_report.status is DailySignalScanStatus.PARTIAL
    assert strict_report.signal_summaries[0].not_observable_rows == 1
    assert any(
        item.reason_code == "REQUIRED_HISTORY_UNAVAILABLE"
        for item in strict_report.warnings
    )
    assert observed_report.status is DailySignalScanStatus.PARTIAL
    assert observed_report.signal_summaries[0].triggered_rows == 1
    assert any(
        item.reason_code == "SNAPSHOT_RESOLVED_WITH_GAPS"
        for item in observed_report.warnings
    )


def test_scan_report_is_deterministic_for_same_input_bytes(tmp_path: Path) -> None:
    from app.signals.scanner import scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    feature_path = _write_features(tmp_path, _features(snapshot.frame))

    first = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(_eligible(),),
    )
    second = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(_eligible(),),
    )

    assert first == second
    assert first.scan_content_id.startswith("sha256:")


def test_indicator_semantics_ref_is_required_and_identity_bearing(
    tmp_path: Path,
) -> None:
    from app.signals.scanner import DailySignalScannerError, scan_finalized_daily_signals

    snapshot = _snapshot(tmp_path)
    feature_path = _write_features(tmp_path, _features(snapshot.frame))

    with pytest.raises(DailySignalScannerError) as caught:
        scan_finalized_daily_signals(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref="latest",
            specs=(_eligible(),),
        )
    first = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(_eligible(),),
    )
    second = scan_finalized_daily_signals(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref="git-sha1:" + "2" * 40,
        specs=(_eligible(),),
    )

    assert caught.value.reason_code == "SCAN_INDICATOR_SEMANTICS_REF_INVALID"
    assert first.scan_content_id != second.scan_content_id


def test_offline_validation_snapshot_etl_scans_canonical_feature_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.pipeline import (
        ETLPipeline,
        EventStage,
        FetchStage,
        FilterStage,
        FundamentalStage,
        IndicatorStage,
    )
    from app.pipeline import fetch_stage
    from app.signals.scanner import scan_finalized_daily_signals

    dates = pd.bdate_range("2026-01-02", periods=80)
    rows: list[dict[str, object]] = []
    for stock_index, stock_id in enumerate(
        ("1101", "1216", "1301", "2330", "3008", "6488")
    ):
        market = "TWSE" if stock_index < 3 else "TPEX"
        for day_index, date in enumerate(dates):
            close = 50 + stock_index * 10 + day_index * 0.2
            rows.append(
                {
                    "date": date,
                    "stock_id": stock_id,
                    "stock_name": f"離線行情{stock_id}",
                    "market": market,
                    "open": close - 0.5,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1_000_000 + day_index,
                    "value": close * (1_000_000 + day_index),
                    "transactions": 10_000 + day_index,
                }
            )
    input_path = tmp_path / "validation-quotes.csv"
    pd.DataFrame(rows).to_csv(input_path, index=False)
    output = tmp_path / "output"
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SNAPSHOT_INPUT", str(input_path))

    class ProviderMustNotRun:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("offline validation must not construct network provider")

    monkeypatch.setattr(fetch_stage, "DataFetcherOrchestrator", ProviderMustNotRun)
    pipeline = (
        ETLPipeline(
            data_dir=str(output / "data"),
            artifacts_dir=str(output / "artifacts"),
        )
        .add_stage(FetchStage())
        .add_stage(IndicatorStage())
        .add_stage(FundamentalStage())
        .add_stage(EventStage())
        .add_stage(FilterStage())
    )
    pipeline.run(
        start_date=dates.min().date().isoformat(),
        end_date=dates.max().date().isoformat(),
    )

    report = scan_finalized_daily_signals(
        pipeline.context["stats"]["daily_close_snapshot"]["manifest_path"],
        output / "data" / "clean" / "features.parquet",
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(_eligible(),),
    )

    assert report.snapshot_id == pipeline.context["stats"]["daily_close_snapshot"][
        "snapshot_id"
    ]
    assert report.snapshot_row_count == 6
    assert report.feature_matched_row_count == 6
    assert report.signal_summaries[0].evaluated_rows == 6
