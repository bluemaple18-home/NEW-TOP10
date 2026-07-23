#!/usr/bin/env python3
"""依市場盤勢做 feature group expanding-window walk-forward 研究。

每個測試 fold 的特徵選擇只使用已成熟的訓練標籤，並保留與預測
horizon 等長的交易日 embargo。本腳本只產生研究 artifact，不修改模型、
production ranking 或任何正式權重。
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.research_feature_group_ablation_by_regime import (  # noqa: E402
    add_forward_returns,
    daily_top_bottom_spreads,
    load_frame,
)


SCHEMA_VERSION = "feature-group-regime-walkforward.v1"
CHIP_PREFIXES = ("foreign_", "trust_", "dealer_", "inst_", "margin_", "short_sale_")
PRICE_LEVEL_FEATURES = {"open", "high", "low", "close"}
ABSOLUTE_COST_FEATURES = {"daily_vwap", "rolling_vwap_5d", "rolling_vwap_20d"}


@dataclass(frozen=True)
class Fold:
    fold_id: int
    train_start: str
    train_end: str
    embargo_start: str
    embargo_end: str
    test_start: str
    test_end: str
    train_days: int
    embargo_days: int
    test_days: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="feature group regime walk-forward")
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-05-29.json")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--min-train-days", type=int, default=100)
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--min-test-days", type=int, default=10)
    parser.add_argument("--min-regime-train-days", type=int, default=12)
    parser.add_argument("--min-daily-stocks", type=int, default=30)
    parser.add_argument("--min-daily-coverage", type=float, default=0.70)
    parser.add_argument("--top-features-per-group", type=int, default=3)
    parser.add_argument("--min-train-abs-ic", type=float, default=0.02)
    parser.add_argument("--output", default="artifacts/model_experiments/feature_group_regime_walkforward_2026-07-23.json")
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def build_folds(
    dates: list[pd.Timestamp],
    *,
    min_train_days: int,
    embargo_days: int,
    test_days: int,
    min_test_days: int,
) -> list[Fold]:
    """建立 expanding folds；train label 在 test 開始前已完整成熟。"""
    if min_train_days <= 0 or embargo_days <= 0 or test_days <= 0 or min_test_days <= 0:
        raise ValueError("fold 參數必須為正數")
    unique_dates = sorted(pd.Timestamp(date).normalize() for date in set(dates))
    first_test = min_train_days + embargo_days
    folds: list[Fold] = []
    for test_start_index in range(first_test, len(unique_dates), test_days):
        test_end_index = min(test_start_index + test_days, len(unique_dates))
        if test_end_index - test_start_index < min_test_days:
            continue
        train_end_index = test_start_index - embargo_days
        train = unique_dates[:train_end_index]
        embargo = unique_dates[train_end_index:test_start_index]
        test = unique_dates[test_start_index:test_end_index]
        folds.append(
            Fold(
                fold_id=len(folds) + 1,
                train_start=str(train[0].date()),
                train_end=str(train[-1].date()),
                embargo_start=str(embargo[0].date()),
                embargo_end=str(embargo[-1].date()),
                test_start=str(test[0].date()),
                test_end=str(test[-1].date()),
                train_days=len(train),
                embargo_days=len(embargo),
                test_days=len(test),
            )
        )
    return folds


def daily_feature_ic(
    frame: pd.DataFrame,
    features: list[str],
    target: str,
    min_daily_stocks: int,
    min_daily_coverage: float,
) -> pd.DataFrame:
    """一次計算所有特徵的逐日橫斷面 Spearman IC。"""
    rows: list[pd.Series] = []
    for trade_date, daily in frame.groupby("trade_date", sort=True):
        columns = features + [target]
        numeric = daily[columns].apply(pd.to_numeric, errors="coerce")
        target_valid = numeric[target].notna()
        pair_counts = numeric[features].notna().mul(target_valid, axis=0).sum()
        if int(target_valid.sum()) < min_daily_stocks or numeric.loc[target_valid, target].nunique() < 2:
            continue
        required_pairs = max(min_daily_stocks, math.ceil(target_valid.sum() * min_daily_coverage))
        ranks = numeric.rank(pct=True)
        variable = numeric[features].nunique(dropna=True) >= 2
        variable_features = variable[variable].index.tolist()
        correlations = pd.Series(index=features, dtype=float)
        correlations.loc[variable_features] = ranks[variable_features].corrwith(ranks[target])
        correlations = correlations.where(pair_counts >= required_pairs)
        correlations.name = pd.Timestamp(trade_date).normalize()
        rows.append(correlations)
    if not rows:
        return pd.DataFrame(columns=features, dtype=float)
    result = pd.DataFrame(rows)
    result.index.name = "trade_date"
    return result.sort_index()


def select_features(
    daily_ic: pd.DataFrame,
    regime_by_date: dict[pd.Timestamp, str],
    train_dates: list[pd.Timestamp],
    groups: dict[str, list[str]],
    *,
    min_regime_days: int,
    top_n: int,
    min_abs_ic: float,
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], list[dict[str, Any]]]:
    """只用單一 fold 訓練日期選出各 regime/group 特徵與方向。"""
    selected: dict[str, dict[str, list[dict[str, Any]]]] = {}
    warnings: list[dict[str, Any]] = []
    train_index = pd.DatetimeIndex(pd.to_datetime(train_dates)).normalize()
    regimes = sorted({regime_by_date.get(date, "UNKNOWN") for date in train_index} - {"UNKNOWN"})
    for regime in regimes:
        regime_dates = [date for date in train_index if regime_by_date.get(date) == regime]
        selected[regime] = {}
        for group_name, columns in groups.items():
            available = [column for column in columns if column in daily_ic.columns]
            metrics: list[dict[str, Any]] = []
            for feature in available:
                values = daily_ic.reindex(regime_dates)[feature].dropna()
                if len(values) < min_regime_days:
                    continue
                mean_ic = float(values.mean())
                direction = 1 if mean_ic >= 0 else -1
                consistency = float(((values * direction) > 0).mean())
                if abs(mean_ic) < min_abs_ic or consistency < 0.55:
                    continue
                metrics.append(
                    {
                        "feature": feature,
                        "direction": direction,
                        "train_days": int(len(values)),
                        "train_ic_mean": round(mean_ic, 6),
                        "train_direction_consistency": round(consistency, 6),
                    }
                )
            metrics.sort(key=lambda item: abs(item["train_ic_mean"]), reverse=True)
            selected[regime][group_name] = metrics[:top_n]
            if not selected[regime][group_name]:
                warnings.append(
                    {
                        "record": f"{regime}/{group_name}",
                        "reason_code": "NO_TRAIN_FEATURE_PASSED",
                        "stage": "feature_selection",
                        "impact_count": len(available),
                    }
                )
    return selected, warnings


def score_group_day(
    daily: pd.DataFrame,
    selected_features: list[dict[str, Any]],
    target: str,
    min_daily_stocks: int,
    min_daily_coverage: float,
) -> tuple[float | None, float | None, int]:
    """依訓練期決定的方向合成單日 group score 並評估 OOS。"""
    if not selected_features:
        return None, None, 0
    oriented = []
    for item in selected_features:
        values = pd.to_numeric(daily[item["feature"]], errors="coerce")
        percentile = values.rank(pct=True)
        oriented.append(percentile if item["direction"] > 0 else 1 - percentile)
    score = pd.concat(oriented, axis=1).mean(axis=1, skipna=True)
    future_return = pd.to_numeric(daily[target], errors="coerce")
    valid = pd.DataFrame(
        {
            "trade_date": daily["trade_date"],
            "stock_id": daily["stock_id"],
            "factor": score,
            "future_return": future_return,
        }
    ).dropna(subset=["factor", "future_return"])
    target_rows = int(future_return.notna().sum())
    required_rows = max(min_daily_stocks, math.ceil(target_rows * min_daily_coverage))
    if len(valid) < required_rows or valid["factor"].nunique() < 3:
        return None, None, int(len(valid))
    ic = valid["factor"].corr(valid["future_return"], method="spearman")
    spreads = daily_top_bottom_spreads(valid)
    spread = float(spreads.iloc[0]) if len(spreads) == 1 else None
    return float(ic) if pd.notna(ic) else None, spread, int(len(valid))


def evaluate_fold(
    frame: pd.DataFrame,
    fold: Fold,
    groups: dict[str, list[str]],
    selected: dict[str, dict[str, list[dict[str, Any]]]],
    target: str,
    min_daily_stocks: int,
    min_daily_coverage: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    test = frame[frame["trade_date"].between(fold.test_start, fold.test_end)].copy()
    observations: dict[tuple[str, str], list[dict[str, Any]]] = {}
    warnings: list[dict[str, Any]] = []
    for trade_date, daily in test.groupby("trade_date", sort=True):
        regime = str(daily["regime_label"].iloc[0])
        for group_name in groups:
            chosen = selected.get(regime, {}).get(group_name, [])
            ic, spread, rows = score_group_day(
                daily,
                chosen,
                target,
                min_daily_stocks,
                min_daily_coverage,
            )
            if ic is None:
                warnings.append(
                    {
                        "record": f"fold={fold.fold_id}/{trade_date.date()}/{regime}/{group_name}",
                        "reason_code": "OOS_DAY_UNAVAILABLE",
                        "stage": "walkforward_evaluation",
                        "impact_count": rows,
                    }
                )
                continue
            observations.setdefault((regime, group_name), []).append(
                {"trade_date": str(trade_date.date()), "ic": ic, "spread": spread, "rows": rows}
            )
    results = []
    for (regime, group_name), rows in observations.items():
        ic = pd.Series([row["ic"] for row in rows], dtype=float)
        spreads = pd.Series([row["spread"] for row in rows], dtype=float).dropna()
        results.append(
            {
                "fold_id": fold.fold_id,
                "regime_label": regime,
                "group": group_name,
                "test_days": len(rows),
                "rows": int(sum(row["rows"] for row in rows)),
                "oos_ic_mean": round(float(ic.mean()), 6),
                "oos_ic_median": round(float(ic.median()), 6),
                "oos_positive_ic_rate": round(float((ic > 0).mean()), 6),
                "oos_top_bottom_spread_mean": round(float(spreads.mean()), 6) if not spreads.empty else None,
                "selected_features": selected.get(regime, {}).get(group_name, []),
            }
        )
    return results, warnings


def summarize(results: list[dict[str, Any]], groups: list[str]) -> dict[str, Any]:
    summaries = []
    for group_name in groups:
        rows = [row for row in results if row["group"] == group_name]
        total_days = sum(row["test_days"] for row in rows)
        if not rows or total_days == 0:
            summaries.append({"group": group_name, "decision": "INSUFFICIENT_DATA", "test_days": 0})
            continue
        weighted_ic = sum(row["oos_ic_mean"] * row["test_days"] for row in rows) / total_days
        spread_rows = [row for row in rows if row["oos_top_bottom_spread_mean"] is not None]
        spread_days = sum(row["test_days"] for row in spread_rows)
        weighted_spread = (
            sum(row["oos_top_bottom_spread_mean"] * row["test_days"] for row in spread_rows) / spread_days
            if spread_days
            else None
        )
        stable_rows = [
            row
            for row in rows
            if row["test_days"] >= 5 and row["oos_top_bottom_spread_mean"] is not None
        ]
        positive_buckets = sum(
            row["oos_ic_mean"] > 0 and row["oos_top_bottom_spread_mean"] > 0
            for row in stable_rows
        )
        positive_rate = positive_buckets / len(stable_rows) if stable_rows else 0.0
        if total_days >= 40 and weighted_ic >= 0.01 and (weighted_spread or 0) >= 0.001 and positive_rate >= 0.60:
            decision = "WALKFORWARD_CANDIDATE"
        elif total_days >= 20 and weighted_ic > 0 and (weighted_spread or 0) > 0 and positive_rate >= 0.50:
            decision = "MONITOR_ONLY"
        else:
            decision = "REJECTED"
        summaries.append(
            {
                "group": group_name,
                "decision": decision,
                "test_days": total_days,
                "fold_regime_buckets": len(rows),
                "stable_buckets": len(stable_rows),
                "positive_bucket_rate": round(positive_rate, 6),
                "weighted_oos_ic_mean": round(weighted_ic, 6),
                "weighted_oos_top_bottom_spread_mean": round(weighted_spread, 6) if weighted_spread is not None else None,
            }
        )
    order = {"WALKFORWARD_CANDIDATE": 0, "MONITOR_ONLY": 1, "REJECTED": 2, "INSUFFICIENT_DATA": 3}
    summaries.sort(key=lambda row: (order[row["decision"]], -float(row.get("weighted_oos_ic_mean") or -999)))
    regime_rows = summarize_regime_groups(results)
    return {
        "groups_tested": len(summaries),
        "walkforward_candidates": [row["group"] for row in summaries if row["decision"] == "WALKFORWARD_CANDIDATE"],
        "monitor_only": [row["group"] for row in summaries if row["decision"] == "MONITOR_ONLY"],
        "by_group": summaries,
        "conditional_walkforward_candidates": [
            f"{row['regime_label']}/{row['group']}"
            for row in regime_rows
            if row["decision"] == "WALKFORWARD_CANDIDATE"
        ],
        "conditional_monitor_only": [
            f"{row['regime_label']}/{row['group']}"
            for row in regime_rows
            if row["decision"] == "MONITOR_ONLY"
        ],
        "by_regime_group": regime_rows,
        "promotion_ready": False,
    }


def summarize_regime_groups(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """分開判斷條件式訊號，避免全域平均掩蓋特定盤勢。"""
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in results:
        buckets.setdefault((row["regime_label"], row["group"]), []).append(row)
    summaries = []
    for (regime, group_name), rows in buckets.items():
        total_days = sum(row["test_days"] for row in rows)
        weighted_ic = sum(row["oos_ic_mean"] * row["test_days"] for row in rows) / total_days
        spread_rows = [row for row in rows if row["oos_top_bottom_spread_mean"] is not None]
        spread_days = sum(row["test_days"] for row in spread_rows)
        weighted_spread = (
            sum(row["oos_top_bottom_spread_mean"] * row["test_days"] for row in spread_rows) / spread_days
            if spread_days
            else None
        )
        positive_rate = sum(
            row["oos_ic_mean"] > 0 and (row["oos_top_bottom_spread_mean"] or 0) > 0
            for row in rows
        ) / len(rows)
        if total_days >= 40 and len(rows) >= 3 and weighted_ic >= 0.01 and (weighted_spread or 0) >= 0.001 and positive_rate >= 0.60:
            decision = "WALKFORWARD_CANDIDATE"
        elif total_days >= 20 and len(rows) >= 3 and weighted_ic > 0 and (weighted_spread or 0) > 0 and positive_rate >= 0.60:
            decision = "MONITOR_ONLY"
        else:
            decision = "REJECTED_OR_INSUFFICIENT"
        summaries.append(
            {
                "regime_label": regime,
                "group": group_name,
                "decision": decision,
                "test_days": total_days,
                "fold_buckets": len(rows),
                "positive_bucket_rate": round(positive_rate, 6),
                "weighted_oos_ic_mean": round(weighted_ic, 6),
                "weighted_oos_top_bottom_spread_mean": round(weighted_spread, 6) if weighted_spread is not None else None,
            }
        )
    order = {"WALKFORWARD_CANDIDATE": 0, "MONITOR_ONLY": 1, "REJECTED_OR_INSUFFICIENT": 2}
    return sorted(
        summaries,
        key=lambda row: (order[row["decision"]], -float(row["weighted_oos_ic_mean"])),
    )


def clean_feature_groups(groups: dict[str, list[str]]) -> tuple[dict[str, list[str]], list[str]]:
    """移除資料可得性/價格層級代理，並拆開技術趨勢與籌碼流。"""
    excluded = sorted(
        {
            feature
            for columns in groups.values()
            for feature in columns
            if feature.endswith("_available") or feature in PRICE_LEVEL_FEATURES or feature in ABSOLUTE_COST_FEATURES
        }
    )
    cleaned: dict[str, list[str]] = {}
    for group_name, columns in groups.items():
        available = [feature for feature in columns if feature not in excluded]
        if group_name == "trend_momentum":
            chip = [feature for feature in available if feature.startswith(CHIP_PREFIXES)]
            technical = [feature for feature in available if feature not in chip]
            if technical:
                cleaned["technical_trend"] = technical
            if chip:
                cleaned["chip_flow"] = chip
        elif group_name == "price_volume":
            if available:
                cleaned["liquidity_activity"] = available
        elif available:
            cleaned[group_name] = available
    return cleaned, excluded


def mask_unavailable_source_features(
    frame: pd.DataFrame,
    groups: dict[str, list[str]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """衍生欄位仍須服從原始來源 availability，缺資料不可視為 0。"""
    result = frame.copy()
    chip_columns = groups.get("chip_flow", [])
    if not chip_columns or "institutional_available" not in result.columns:
        return result, {"chip_flow_masked_rows": 0, "institutional_available_rate": None}
    available = result["institutional_available"].fillna(False).astype(bool)
    affected = result.loc[~available, chip_columns].notna().any(axis=1)
    result.loc[~available, chip_columns] = pd.NA
    return result, {
        "chip_flow_masked_rows": int(affected.sum()),
        "institutional_available_rate": round(float(available.mean()), 6),
        "reason_code": "SOURCE_UNAVAILABLE_NOT_ZERO",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if not 0 < args.min_daily_coverage <= 1:
        raise ValueError("--min-daily-coverage 必須介於 0 與 1 之間")
    data_dir = resolve_path(args.data_dir)
    regime_path = resolve_path(args.market_regime_history)
    industry_path = resolve_path(args.industry_map)
    frame, source_groups, source_contract = load_frame(data_dir, regime_path, industry_path)
    groups, excluded_features = clean_feature_groups(source_groups)
    frame, source_mask_receipt = mask_unavailable_source_features(frame, groups)
    frame = add_forward_returns(frame, [args.horizon])
    target = f"future_return_{args.horizon}d"
    frame = frame[frame["regime_label"].ne("UNKNOWN")].copy()
    dates = sorted(frame.loc[frame[target].notna(), "trade_date"].drop_duplicates().tolist())
    folds = build_folds(
        dates,
        min_train_days=args.min_train_days,
        embargo_days=args.horizon,
        test_days=args.test_days,
        min_test_days=args.min_test_days,
    )
    if not folds:
        raise ValueError("可用日期不足以建立 walk-forward fold")
    features = sorted({feature for columns in groups.values() for feature in columns})
    daily_ic = daily_feature_ic(
        frame,
        features,
        target,
        args.min_daily_stocks,
        args.min_daily_coverage,
    )
    regime_by_date = {
        pd.Timestamp(date).normalize(): str(label)
        for date, label in frame[["trade_date", "regime_label"]].drop_duplicates("trade_date").itertuples(index=False)
    }
    results: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    for fold in folds:
        train_dates = [date for date in dates if str(date.date()) <= fold.train_end]
        selected, selection_warnings = select_features(
            daily_ic,
            regime_by_date,
            train_dates,
            groups,
            min_regime_days=args.min_regime_train_days,
            top_n=args.top_features_per_group,
            min_abs_ic=args.min_train_abs_ic,
        )
        for warning in selection_warnings:
            warning["record"] = f"fold={fold.fold_id}/{warning['record']}"
        fold_results, fold_warnings = evaluate_fold(
            frame,
            fold,
            groups,
            selected,
            target,
            args.min_daily_stocks,
            args.min_daily_coverage,
        )
        results.extend(fold_results)
        warnings.extend(selection_warnings)
        warnings.extend(fold_warnings)
        selections.append({"fold_id": fold.fold_id, "selected": selected})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "data_contract": {
            "source_and_grain": "data/clean stock_id × trade_date；regime history trade_date",
            "confirmed_schema_and_status_semantics": "feature frame 由 M4 contract 載入；UNKNOWN regime 排除並可觀測",
            "joins_and_cardinality": "regime 以 trade_date many-to-one；industry factors 使用 leave-one-out",
            "aggregation_invariants": "每 fold 選特徵只讀 train；label embargo 等於 horizon；test 不參與選擇或方向判定",
        },
        "execution_boundary": {
            "database_pushdown": "not_applicable_local_controlled_snapshot",
            "controlled_artifacts": "artifacts/model_experiments only",
        },
        "degradation": {
            "unavailable_data": "UNKNOWN regime 或 regime/group 訓練日不足時不評分",
            "provisional_thresholds": "candidate thresholds are research-only and fixed before this run",
            "model_limits": "univariate group composite; does not estimate portfolio return or interactions",
        },
        "contract": {
            **source_contract,
            "expanding_window": True,
            "label_embargo_trade_days": args.horizon,
            "test_data_used_for_selection": False,
            "writes_model": False,
            "changes_production_ranking": False,
            "promotion_ready": False,
        },
        "inputs": {
            "data_dir": repo_path(data_dir),
            "market_regime_history": repo_path(regime_path),
            "industry_map": repo_path(industry_path),
            "horizon": args.horizon,
            "min_train_days": args.min_train_days,
            "test_days": args.test_days,
            "min_test_days": args.min_test_days,
            "min_regime_train_days": args.min_regime_train_days,
            "min_daily_stocks": args.min_daily_stocks,
            "min_daily_coverage": args.min_daily_coverage,
            "top_features_per_group": args.top_features_per_group,
            "min_train_abs_ic": args.min_train_abs_ic,
            "available_dates": len(dates),
            "start_date": str(dates[0].date()),
            "end_date": str(dates[-1].date()),
        },
        "validation": {
            "fixture_or_unit": "scripts/verify_feature_group_regime_walkforward.py",
            "representative_real_data": True,
            "old_vs_new_reconciliation": "old fixed-weight replay retained as exploratory evidence; not treated as strict OOS",
            "business_invariants": [
                "train_end < embargo_start <= embargo_end < test_start",
                "embargo_days == horizon",
                "models/latest_lgbm.pkl and production ranking are not written",
            ],
        },
        "feature_groups": groups,
        "excluded_features": excluded_features,
        "source_mask_receipt": source_mask_receipt,
        "folds": [asdict(fold) for fold in folds],
        "selections": selections,
        "fold_regime_results": results,
        "summary": summarize(results, list(groups)),
        "warnings_and_exclusions": warnings,
        "remaining_risk": [
            f"regime history ends at {max(regime_by_date).date()} and remains a controlled research history",
            "multiple feature hypotheses remain; this gate only nominates bounded follow-up candidates",
            "transaction costs and portfolio construction are deferred until a group survives this gate",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Feature Group Regime Walk-forward",
        "",
        f"- status: {payload['status']}",
        f"- folds: {len(payload['folds'])}",
        f"- available_dates: {payload['inputs']['available_dates']}",
        f"- horizon / embargo: {payload['inputs']['horizon']} trading days",
        "- production ranking changed: false",
        "- promotion_ready: false",
        "",
        "| Group | Decision | OOS Days | IC | Top-Bottom Spread | Positive Buckets |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]["by_group"]:
        lines.append(
            "| {group} | {decision} | {days} | {ic} | {spread} | {positive} |".format(
                group=row["group"],
                decision=row["decision"],
                days=row.get("test_days", 0),
                ic=_fmt(row.get("weighted_oos_ic_mean")),
                spread=_fmt(row.get("weighted_oos_top_bottom_spread_mean")),
                positive=_fmt(row.get("positive_bucket_rate")),
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- WALKFORWARD_CANDIDATE: {', '.join(payload['summary']['walkforward_candidates']) or 'none'}",
            f"- MONITOR_ONLY: {', '.join(payload['summary']['monitor_only']) or 'none'}",
            f"- Conditional candidate: {', '.join(payload['summary']['conditional_walkforward_candidates']) or 'none'}",
            f"- Conditional monitor: {', '.join(payload['summary']['conditional_monitor_only']) or 'none'}",
            "- 本 artifact 不能直接支持 production promotion。",
            "",
        ]
    )
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    return "--" if value is None else f"{float(value):.4f}"


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "folds": len(payload["folds"]),
                "walkforward_candidates": payload["summary"]["walkforward_candidates"],
                "monitor_only": payload["summary"]["monitor_only"],
                "warnings": len(payload["warnings_and_exclusions"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
