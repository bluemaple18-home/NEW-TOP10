#!/usr/bin/env python3
"""驗證 feature group regime walk-forward 的防洩漏不變量。"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_feature_group_regime_walkforward as walkforward  # noqa: E402
from scripts import build_append_only_market_regime_history as append_history  # noqa: E402


ARTIFACT = PROJECT_ROOT / "artifacts" / "model_experiments" / "feature_group_regime_walkforward_verification_2026-07-23.json"


def main() -> int:
    checks = {
        "fold_has_exact_embargo": _fold_has_exact_embargo(),
        "selection_uses_train_signal_and_direction": _selection_uses_train_signal_and_direction(),
        "negative_feature_orientation_is_reversed": _negative_feature_orientation_is_reversed(),
        "conditional_summary_keeps_regime_boundary": _conditional_summary_keeps_regime_boundary(),
        "append_only_history_preserves_base_labels": _append_only_history_preserves_base_labels(),
        "clean_group_contract_removes_availability_and_price_level": _clean_group_contract_removes_availability_and_price_level(),
        "unavailable_chip_source_is_masked": _unavailable_chip_source_is_masked(),
        "constant_daily_feature_is_skipped": _constant_daily_feature_is_skipped(),
        "point_in_time_universe_reranks_each_day": _point_in_time_universe_reranks_each_day(),
        "partial_ic_detects_incremental_signal": _partial_ic_detects_incremental_signal(),
    }
    status = "OK" if all(checks.values()) else "FAILED"
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(
            {
                "schema_version": "feature-group-regime-walkforward-verification.v1",
                "status": status,
                "checks": checks,
                "production_writes": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"FEATURE_GROUP_REGIME_WALKFORWARD_{status} output={ARTIFACT}")
    return 0 if status == "OK" else 1


def _fold_has_exact_embargo() -> bool:
    dates = list(pd.date_range("2026-01-01", periods=30, freq="D"))
    folds = walkforward.build_folds(
        dates,
        min_train_days=10,
        embargo_days=3,
        test_days=5,
        min_test_days=3,
    )
    first = folds[0]
    return (
        first.train_days == 10
        and first.embargo_days == 3
        and first.test_days == 5
        and first.train_end < first.embargo_start <= first.embargo_end < first.test_start
    )


def _selection_uses_train_signal_and_direction() -> bool:
    dates = list(pd.date_range("2026-01-01", periods=12, freq="D"))
    daily_ic = pd.DataFrame(
        {
            "positive_signal": [0.05] * 12,
            "negative_signal": [-0.04] * 12,
            "unstable_noise": [0.08, -0.08] * 6,
        },
        index=dates,
    )
    selected, _ = walkforward.select_features(
        daily_ic,
        {date: "RISK_OFF" for date in dates},
        dates,
        {"test_group": list(daily_ic.columns)},
        min_regime_days=8,
        top_n=3,
        min_abs_ic=0.02,
    )
    items = selected["RISK_OFF"]["test_group"]
    directions = {item["feature"]: item["direction"] for item in items}
    return directions == {"positive_signal": 1, "negative_signal": -1}


def _negative_feature_orientation_is_reversed() -> bool:
    values = list(range(40))
    daily = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2026-01-01")] * 40,
            "stock_id": [str(index).zfill(4) for index in range(40)],
            "negative_feature": values,
            "future_return_10d": [-value / 100 for value in values],
        }
    )
    ic, spread, rows = walkforward.score_group_day(
        daily,
        [{"feature": "negative_feature", "direction": -1}],
        "future_return_10d",
        30,
        0.70,
    )
    return rows == 40 and ic is not None and ic > 0.99 and spread is not None and spread > 0


def _conditional_summary_keeps_regime_boundary() -> bool:
    rows = [
        {
            "fold_id": fold_id,
            "regime_label": "NARROW_LEADER",
            "group": "industry_momentum",
            "test_days": 10,
            "oos_ic_mean": 0.03,
            "oos_top_bottom_spread_mean": 0.005,
        }
        for fold_id in range(1, 4)
    ]
    summary = walkforward.summarize_regime_groups(rows)
    return len(summary) == 1 and summary[0]["decision"] == "MONITOR_ONLY"


def _append_only_history_preserves_base_labels() -> bool:
    base = {
        "rows": [
            {"trade_date": "2026-01-01", "regime_label": "RISK_OFF"},
            {"trade_date": "2026-01-02", "regime_label": "NARROW_LEADER"},
        ]
    }
    extension = {
        "rows": [
            {"trade_date": "2026-01-01", "regime_label": "NARROW_LEADER"},
            {"trade_date": "2026-01-02", "regime_label": "NARROW_LEADER"},
            {"trade_date": "2026-01-03", "regime_label": "MIXED_NEUTRAL"},
        ]
    }
    merged = append_history.merge_histories(base, extension)
    by_date = {row["trade_date"]: row["regime_label"] for row in merged["rows"]}
    return (
        by_date["2026-01-01"] == "RISK_OFF"
        and by_date["2026-01-03"] == "MIXED_NEUTRAL"
        and merged["summary"]["overlap_label_drift_days"] == 1
    )


def _clean_group_contract_removes_availability_and_price_level() -> bool:
    cleaned, excluded = walkforward.clean_feature_groups(
        {
            "price_volume": ["close", "avg_value_20d"],
            "cost_basis": ["daily_vwap", "close_vs_vwap_20d"],
            "trend_momentum": ["institutional_available", "macd", "inst_buy_ratio_5d"],
        }
    )
    return (
        cleaned["liquidity_activity"] == ["avg_value_20d"]
        and cleaned["cost_basis"] == ["close_vs_vwap_20d"]
        and cleaned["technical_trend"] == ["macd"]
        and cleaned["chip_flow"] == ["inst_buy_ratio_5d"]
        and set(excluded) == {"close", "daily_vwap", "institutional_available"}
    )


def _unavailable_chip_source_is_masked() -> bool:
    frame = pd.DataFrame(
        {
            "institutional_available": [True, False],
            "trust_buy_days_5d": [3.0, 0.0],
        }
    )
    masked, receipt = walkforward.mask_unavailable_source_features(
        frame,
        {"chip_flow": ["trust_buy_days_5d"]},
    )
    return (
        masked.loc[0, "trust_buy_days_5d"] == 3.0
        and pd.isna(masked.loc[1, "trust_buy_days_5d"])
        and receipt["chip_flow_masked_rows"] == 1
    )


def _constant_daily_feature_is_skipped() -> bool:
    frame = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2026-01-01")] * 40,
            "signal": list(range(40)),
            "constant": [1.0] * 40,
            "future_return_10d": [value / 100 for value in range(40)],
        }
    )
    daily = walkforward.daily_feature_ic(
        frame,
        ["signal", "constant"],
        "future_return_10d",
        30,
        0.70,
    )
    return bool(len(daily) == 1 and daily["signal"].notna().all() and daily["constant"].isna().all())


def _point_in_time_universe_reranks_each_day() -> bool:
    frame = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2026-01-01")] * 3 + [pd.Timestamp("2026-01-02")] * 3,
            "stock_id": ["0001", "0002", "0003"] * 2,
            "avg_value_20d": [30.0, 20.0, 10.0, 10.0, 20.0, 30.0],
            "institutional_available": [True] * 6,
        }
    )
    selected, receipt = walkforward.apply_research_universe(
        frame,
        mode="point-in-time-liquidity",
        liquidity_top_n=2,
    )
    by_date = {
        str(date.date()): set(group["stock_id"])
        for date, group in selected.groupby("trade_date")
    }
    return (
        by_date["2026-01-01"] == {"0001", "0002"}
        and by_date["2026-01-02"] == {"0002", "0003"}
        and receipt["daily_selected_min"] == 2
        and receipt["daily_selected_max"] == 2
    )


def _partial_ic_detects_incremental_signal() -> bool:
    control = pd.Series(range(40), dtype=float)
    independent = pd.Series([value % 7 for value in range(40)], dtype=float)
    primary = control * 0.4 + independent
    target = control * 0.4 + independent * 2
    ic, rows = walkforward.partial_spearman_ic(
        primary,
        control,
        target,
        min_rows=30,
        min_coverage=0.70,
    )
    return rows == 40 and ic is not None and ic > 0.80


if __name__ == "__main__":
    raise SystemExit(main())
