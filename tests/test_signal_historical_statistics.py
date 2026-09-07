from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import inspect
from pathlib import Path

import pandas as pd
import pytest

from app.signals import (
    INITIAL_SIGNAL_SPECS,
    SignalDirection,
    SignalEligibilityStatus,
)

from tests.test_daily_signal_scanner import (
    INDICATOR_SEMANTICS_REF,
    _snapshot,
    _write_features,
)


def _history_quotes() -> pd.DataFrame:
    dates = pd.bdate_range("2026-08-24", periods=8)
    rows: list[dict[str, object]] = []
    closes = {
        "2330": (100, 101, 102, 103, 104, 105, 106, 107),
        "6488": (120, 118, 116, 114, 112, 110, 108, 106),
    }
    for stock_id, values in closes.items():
        market = "TWSE" if stock_id == "2330" else "TPEX"
        for date, close in zip(dates, values, strict=True):
            rows.append(
                {
                    "date": date,
                    "stock_id": stock_id,
                    "stock_name": f"測試股票{stock_id}",
                    "market": market,
                    "open": close - 1,
                    "high": close + 2,
                    "low": close - 2,
                    "close": close,
                    "volume": 1_000,
                    "value": close * 1_000,
                    "transactions": 100,
                }
            )
    return pd.DataFrame(rows)


def _history_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["rsi"] = 50.0
    output["rsi_rebound_from_40"] = 0
    output["rsi_break_below_50"] = 0
    by_stock_position = output.groupby("stock_id", sort=False).cumcount()
    output.loc[
        output["stock_id"].eq("2330") & by_stock_position.isin([1, 2, 4, 7]),
        "rsi_rebound_from_40",
    ] = 1
    output.loc[
        output["stock_id"].eq("6488") & by_stock_position.isin([1, 3, 5]),
        "rsi_break_below_50",
    ] = 1
    return output


def _eligible(signal_id: str):
    return replace(
        INITIAL_SIGNAL_SPECS[signal_id],
        evaluation_horizon_days=2,
        research_evidence_ref=f"test-only://radar-p1d/{signal_id}",
        eligibility_status=SignalEligibilityStatus.RADAR_ELIGIBLE,
    )


def _inputs(tmp_path: Path, *, features: pd.DataFrame | None = None):
    snapshot = _snapshot(
        tmp_path,
        _history_quotes(),
        requested_start="2026-08-24",
        requested_end="2026-09-02",
    )
    feature_frame = _history_features(snapshot.frame) if features is None else features
    return snapshot, _write_features(tmp_path, feature_frame)


def test_bullish_statistics_use_internal_aligned_base_rate_and_effective_policy(
    tmp_path: Path,
) -> None:
    from app.signals.historical_statistics import (
        HistoricalStatisticsStatus,
        build_signal_historical_statistics,
    )

    spec = _eligible("rsi_rebound_from_40")
    snapshot, feature_path = _inputs(tmp_path)

    report = build_signal_historical_statistics(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(spec,),
    )

    assert report.status is HistoricalStatisticsStatus.COMPLETE_WITH_EXCLUSIONS
    assert report.result_content_id.startswith("sha256:")
    assert report.price_return_basis == "UNADJUSTED_PRICE_RETURN"
    assert report.currency == "TWD"
    assert report.research_status == "VALIDATION_ONLY"
    assert report.oos_status == "NOT_OOS"
    assert report.sealed_status == "NOT_SEALED"
    assert report.authority_scope == "NO_ELIGIBILITY_OR_RANKING_AUTHORITY"
    assert report.effective_sample_policy == "PER_INSTRUMENT_NON_OVERLAPPING_FORWARD_WINDOWS_V1"
    assert (
        report.maximum_adverse_excursion_basis
        == "FUTURE_SESSION_LOW_HIGH_VS_ENTRY_CLOSE"
    )
    assert report.universe.instrument_ids == ("2330", "6488")

    result = report.signal_statistics[0]
    assert result.forward_horizon_sessions == 2
    assert result.coverage.triggered_rows == 4
    assert result.coverage.triggered_complete_outcomes == 3
    assert result.coverage.triggered_outcome_incomplete_rows == 1
    assert result.conditional.raw_sample_size == 3
    assert result.conditional.effective_sample_size == 2
    assert result.conditional.event_date_count == 3
    assert result.conditional.overlap_count == 1
    assert result.conditional.direction_positive_rate == 1.0
    assert result.baseline.raw_sample_size == 12
    assert result.baseline.effective_sample_size == 6
    assert result.baseline.overlap_count == 6
    assert result.baseline.direction_positive_rate == 0.5
    assert result.incremental_edge.direction_positive_rate_percentage_points == 50.0
    assert result.incremental_edge.mean_return_edge == pytest.approx(
        result.conditional.mean_return - result.baseline.mean_return
    )
    assert result.incremental_edge.median_return_edge == pytest.approx(
        result.conditional.median_return - result.baseline.median_return
    )
    assert {item.reason_code: item.affected_count for item in report.warnings} == {
        "BASELINE_OUTCOME_HORIZON_UNAVAILABLE": 4,
        "REQUIRED_HISTORY_UNAVAILABLE": 2,
        "TRIGGERED_OUTCOME_HORIZON_UNAVAILABLE": 1,
    }


def test_bearish_returns_are_direction_adjusted_and_include_mae_summary(
    tmp_path: Path,
) -> None:
    from app.signals.historical_statistics import build_signal_historical_statistics

    spec = _eligible("rsi_break_below_50")
    snapshot, feature_path = _inputs(tmp_path)

    result = build_signal_historical_statistics(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(spec,),
    ).signal_statistics[0]

    assert result.direction == "BEARISH"
    assert result.conditional.raw_sample_size == 3
    assert result.conditional.effective_sample_size == 3
    assert result.conditional.direction_positive_rate == 1.0
    assert result.conditional.mean_return > 0
    assert result.conditional.maximum_adverse_excursion_mean == 0.0
    assert result.conditional.downside_count == 0


def test_unobservable_and_tail_exclusions_are_structured_and_counted(
    tmp_path: Path,
) -> None:
    from app.signals.historical_statistics import build_signal_historical_statistics

    spec = _eligible("rsi_rebound_from_40")
    snapshot = _snapshot(
        tmp_path,
        _history_quotes(),
        requested_start="2026-08-24",
        requested_end="2026-09-02",
    )
    features = _history_features(snapshot.frame)
    target = features["stock_id"].eq("2330") & features["date"].eq(
        pd.Timestamp("2026-08-27")
    )
    features.loc[target, "rsi"] = None
    missing = features["stock_id"].eq("6488") & features["date"].eq(
        pd.Timestamp("2026-08-28")
    )
    feature_path = _write_features(tmp_path, features.loc[~missing].copy())

    report = build_signal_historical_statistics(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
        specs=(spec,),
    )

    result = report.signal_statistics[0]
    assert result.coverage.evaluated_rows == 16
    assert result.coverage.not_observable_rows >= 2
    reasons = {item.reason_code for item in report.warnings}
    assert "REQUIRED_FEATURE_UNAVAILABLE" in reasons
    assert "FEATURE_PROJECTION_ROW_MISSING" in reasons
    assert "TRIGGERED_OUTCOME_HORIZON_UNAVAILABLE" in reasons


def test_default_catalog_is_explicit_zero_and_has_no_authority(tmp_path: Path) -> None:
    from app.signals.historical_statistics import (
        HistoricalStatisticsStatus,
        build_signal_historical_statistics,
    )

    snapshot, feature_path = _inputs(tmp_path)
    report = build_signal_historical_statistics(
        snapshot.manifest_path,
        feature_path,
        indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
    )

    assert report.status is HistoricalStatisticsStatus.NO_RADAR_ELIGIBLE_SIGNAL_SPEC
    assert report.eligible_signal_count == 0
    assert report.signal_statistics == ()
    assert report.authority_scope == "NO_ELIGIBILITY_OR_RANKING_AUTHORITY"
    assert [item.reason_code for item in report.warnings] == [
        "NO_RADAR_ELIGIBLE_SIGNAL_SPEC"
    ]


def test_replay_is_deterministic_content_addressed_and_immutable(tmp_path: Path) -> None:
    from app.signals.historical_statistics import build_signal_historical_statistics

    spec = _eligible("rsi_rebound_from_40")
    snapshot, feature_path = _inputs(tmp_path)
    kwargs = {
        "indicator_semantics_ref": INDICATOR_SEMANTICS_REF,
        "specs": (spec,),
    }

    first = build_signal_historical_statistics(snapshot.manifest_path, feature_path, **kwargs)
    second = build_signal_historical_statistics(snapshot.manifest_path, feature_path, **kwargs)

    assert first == second
    assert first.result_content_id == second.result_content_id
    with pytest.raises(FrozenInstanceError):
        first.eligible_signal_count = 2
    assert "baseline" not in inspect.signature(build_signal_historical_statistics).parameters


def test_neutral_direction_is_rejected_with_stable_reason(tmp_path: Path) -> None:
    from app.signals.historical_statistics import (
        HistoricalStatisticsError,
        build_signal_historical_statistics,
    )

    spec = replace(_eligible("rsi_rebound_from_40"), direction=SignalDirection.NEUTRAL)
    snapshot, feature_path = _inputs(tmp_path)

    with pytest.raises(HistoricalStatisticsError) as caught:
        build_signal_historical_statistics(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=(spec,),
        )

    assert caught.value.reason_code == "HIST_DIRECTION_UNSUPPORTED"


def test_signal_column_cannot_overlap_required_features(tmp_path: Path) -> None:
    from app.signals.historical_statistics import (
        HistoricalStatisticsError,
        build_signal_historical_statistics,
    )

    snapshot = _snapshot(
        tmp_path,
        _history_quotes(),
        requested_start="2026-08-24",
        requested_end="2026-09-02",
    )
    features = _history_features(snapshot.frame)
    features["rsi"] = 0
    features.loc[features.index[1], "rsi"] = 1
    feature_path = _write_features(tmp_path, features)
    spec = replace(_eligible("rsi_rebound_from_40"), signal_column="rsi")

    with pytest.raises(HistoricalStatisticsError) as caught:
        build_signal_historical_statistics(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=(spec,),
        )

    assert caught.value.reason_code == "HIST_SIGNAL_COLUMN_CONFLICT"


@pytest.mark.parametrize(
    ("path_parameter", "reason_code"),
    [
        (
            "snapshot_manifest_path",
            "HIST_SNAPSHOT_MANIFEST_PATH_TYPE_INVALID",
        ),
        (
            "feature_artifact_path",
            "HIST_FEATURE_ARTIFACT_PATH_TYPE_INVALID",
        ),
    ],
)
def test_non_path_inputs_are_rejected_with_stable_reasons(
    tmp_path: Path,
    path_parameter: str,
    reason_code: str,
) -> None:
    from app.signals.historical_statistics import (
        HistoricalStatisticsError,
        build_signal_historical_statistics,
    )

    snapshot, feature_path = _inputs(tmp_path)
    arguments = {
        "snapshot_manifest_path": snapshot.manifest_path,
        "feature_artifact_path": feature_path,
        "indicator_semantics_ref": INDICATOR_SEMANTICS_REF,
    }
    arguments[path_parameter] = None

    with pytest.raises(HistoricalStatisticsError) as caught:
        build_signal_historical_statistics(**arguments)

    assert caught.value.reason_code == reason_code


def test_unreadable_external_spec_iterable_has_stable_reason(tmp_path: Path) -> None:
    from app.signals.historical_statistics import (
        HistoricalStatisticsError,
        build_signal_historical_statistics,
    )

    class BrokenIterable:
        def __iter__(self):
            raise RuntimeError("broken iterable")

    snapshot, feature_path = _inputs(tmp_path)

    with pytest.raises(HistoricalStatisticsError) as caught:
        build_signal_historical_statistics(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=INDICATOR_SEMANTICS_REF,
            specs=BrokenIterable(),
        )

    assert caught.value.reason_code == "HIST_SPEC_CONTAINER_UNREADABLE"


@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    [
        ("semantics", "HIST_INDICATOR_SEMANTICS_REF_INVALID"),
        ("contract_only", "HIST_SPEC_NOT_RADAR_ELIGIBLE"),
        ("required_feature_value", "HIST_REQUIRED_FEATURE_VALUE_INVALID"),
        ("rule_value", "HIST_RULE_RESULT_INVALID"),
        ("close_drift", "HIST_DAILY_CLOSE_VALUE_DRIFT"),
    ],
)
def test_malformed_or_tampered_input_fails_closed(
    tmp_path: Path,
    mutation: str,
    reason_code: str,
) -> None:
    from app.signals.historical_statistics import (
        HistoricalStatisticsError,
        build_signal_historical_statistics,
    )

    spec = _eligible("rsi_rebound_from_40")
    snapshot, feature_path = _inputs(tmp_path)
    semantics_ref = INDICATOR_SEMANTICS_REF
    specs = (spec,)
    if mutation == "semantics":
        semantics_ref = "latest"
    elif mutation == "contract_only":
        specs = (INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"],)
    else:
        frame = pd.read_parquet(feature_path)
        if mutation == "required_feature_value":
            frame.loc[frame.index[0], "rsi"] = float("inf")
        elif mutation == "rule_value":
            frame.loc[frame.index[0], "rsi_rebound_from_40"] = 2
        else:
            frame.loc[frame.index[0], "close"] += 1
        frame.to_parquet(feature_path, index=False)

    with pytest.raises(HistoricalStatisticsError) as caught:
        build_signal_historical_statistics(
            snapshot.manifest_path,
            feature_path,
            indicator_semantics_ref=semantics_ref,
            specs=specs,
        )

    assert caught.value.reason_code == reason_code
