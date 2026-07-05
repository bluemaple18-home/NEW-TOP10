#!/usr/bin/env python3
"""建立大盤壓力防守閘門 replay artifact。

本腳本只讀既有 features 與 ranking artifacts，不訓練模型、不重排 Top10、
不改 production ranking。用途是把 MARKET-DEFENSE-01 的候選規則轉成可驗證證據。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay


SCHEMA_VERSION = "market-defense-guard-replay.v1"
LEVEL_ORDER = {
    "NORMAL": 0,
    "CAUTION": 1,
    "DEFENSIVE": 2,
    "RISK_OFF_BLOCK": 3,
}


@dataclass(frozen=True)
class VariantSpec:
    name: str
    defensive_gross_cap: float | None = None
    risk_off_gross_cap: float | None = None
    block_level3: bool = False
    message_only: bool = False


VARIANTS = [
    VariantSpec("baseline_production"),
    VariantSpec("defense_message_only", message_only=True),
    VariantSpec("defense_gross_cap_55", defensive_gross_cap=0.55, risk_off_gross_cap=0.35),
    VariantSpec("defense_gross_cap_45", defensive_gross_cap=0.45, risk_off_gross_cap=0.30),
    VariantSpec("defense_gross_cap_35", defensive_gross_cap=0.35, risk_off_gross_cap=0.20),
    VariantSpec("defense_block_primary", defensive_gross_cap=0.35, risk_off_gross_cap=0.0, block_level3=True),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build market defense guard replay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument(
        "--long-rankings-dir",
        default="artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15",
    )
    parser.add_argument(
        "--recent-rankings-dir",
        default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15",
    )
    parser.add_argument("--event-rankings-dir", default="artifacts")
    parser.add_argument("--start-date", default="2023-11-21")
    parser.add_argument("--recent-start-date", default="2025-11-17")
    parser.add_argument("--end-date", default="2026-05-15")
    parser.add_argument("--event-start-date", default="2026-06-22")
    parser.add_argument("--event-end-date", default="2026-06-26")
    parser.add_argument("--horizons", default="1,3,5,10")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--max-position-weight", type=float, default=0.2)
    parser.add_argument("--default-gross-exposure", type=float, default=0.65)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def number(value: Any, digits: int = 6) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return round(float(parsed), digits)


def parse_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def ranking_files(rankings_dir: Path, start_date: str, end_date: str) -> list[Path]:
    files: list[Path] = []
    for path in sorted(rankings_dir.glob("ranking_*.csv"), key=lambda item: item.name):
        if not re.fullmatch(r"ranking_\d{4}-\d{2}-\d{2}\.csv", path.name):
            continue
        date_text = run_backtest_replay.ranking_date(path)
        if start_date <= date_text <= end_date:
            files.append(path)
    if not files:
        raise FileNotFoundError(f"找不到 ranking 檔：{rankings_dir} {start_date}~{end_date}")
    return files


def load_market_frame(features_path: Path) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"features 不存在：{features_path}")
    columns = ["date", "stock_id", "open", "high", "low", "close", "ma20"]
    frame = pd.read_parquet(features_path, columns=columns)
    frame = frame.dropna(subset=["date", "stock_id", "close"]).copy()
    frame["trade_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    frame = frame.dropna(subset=["trade_date"]).sort_values(["stock_id", "trade_date"]).copy()
    frame["daily_return"] = frame.groupby("stock_id", sort=False)["close"].pct_change()
    return frame


def build_market_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    index_level = 1.0
    levels: list[float] = []
    dates: list[date] = []
    for trade_date, day in frame.groupby("trade_date", sort=True):
        daily_return = pd.to_numeric(day["daily_return"], errors="coerce")
        equal_weight_return = number(daily_return.mean())
        if equal_weight_return is not None:
            index_level *= 1 + equal_weight_return
        levels.append(index_level)
        dates.append(trade_date)
        close = pd.to_numeric(day["close"], errors="coerce")
        ma20 = pd.to_numeric(day["ma20"], errors="coerce")
        rows.append(
            {
                "trade_date": trade_date,
                "equal_weight_return": equal_weight_return,
                "market_index": index_level,
                "breadth_ma20": number((close > ma20).mean()),
                "stock_count": int(len(day)),
            }
        )

    metrics = pd.DataFrame(rows).sort_values("trade_date").reset_index(drop=True)
    metrics["market_return_3d"] = metrics["market_index"].pct_change(3)
    metrics["market_return_5d"] = metrics["market_index"].pct_change(5)
    metrics["rolling_high_20d"] = metrics["market_index"].rolling(20, min_periods=1).max()
    metrics["drawdown_from_20d_high"] = metrics["market_index"] / metrics["rolling_high_20d"] - 1
    down_streaks: list[int] = []
    streak = 0
    for value in metrics["equal_weight_return"]:
        if pd.notna(value) and float(value) < 0:
            streak += 1
        else:
            streak = 0
        down_streaks.append(streak)
    metrics["down_streak"] = down_streaks
    levels_out = [classify_defense_level(row) for _, row in metrics.iterrows()]
    metrics["defense_level"] = [item["level"] for item in levels_out]
    metrics["defense_reason"] = [item["reason"] for item in levels_out]
    metrics["fragility_watch"] = metrics.apply(fragility_watch, axis=1)
    return metrics


def classify_defense_level(row: pd.Series | dict[str, Any]) -> dict[str, str]:
    r3 = value_or_none(row.get("market_return_3d"))
    r5 = value_or_none(row.get("market_return_5d"))
    drawdown = value_or_none(row.get("drawdown_from_20d_high"))
    breadth = value_or_none(row.get("breadth_ma20"))
    down_streak = int(row.get("down_streak") or 0)

    if (r5 is not None and r5 <= -0.04) or (drawdown is not None and drawdown <= -0.06):
        return {"level": "RISK_OFF_BLOCK", "reason": "5日跌幅或20日高點回撤觸發 Level 3"}
    if breadth is not None and breadth <= 0.35 and r3 is not None and r3 <= -0.02:
        return {"level": "RISK_OFF_BLOCK", "reason": "MA20廣度 <=35% 且3日跌幅 <=-2%"}
    if (r3 is not None and r3 <= -0.02) or (drawdown is not None and drawdown <= -0.04):
        return {"level": "DEFENSIVE", "reason": "3日跌幅或20日高點回撤觸發 Level 2"}
    if down_streak >= 3 and r3 is not None and r3 <= -0.015:
        return {"level": "DEFENSIVE", "reason": "連跌>=3且3日跌幅<=-1.5%"}
    if (r3 is not None and r3 <= -0.015) or (drawdown is not None and drawdown <= -0.03):
        return {"level": "CAUTION", "reason": "3日跌幅或20日高點回撤觸發 Level 1"}
    if down_streak >= 2 and breadth is not None and breadth <= 0.45:
        return {"level": "CAUTION", "reason": "連跌>=2且MA20廣度<=45%"}
    return {"level": "NORMAL", "reason": "未觸發防守條件"}


def fragility_watch(row: pd.Series | dict[str, Any]) -> str | None:
    """標記尚未降曝險、但盤面廣度已經很脆弱的早期提醒。"""
    level = str(row.get("defense_level") or "NORMAL")
    breadth = value_or_none(row.get("breadth_ma20"))
    r3 = value_or_none(row.get("market_return_3d"))
    drawdown = value_or_none(row.get("drawdown_from_20d_high"))
    if level != "NORMAL" or breadth is None:
        return None
    if breadth <= 0.25 and (r3 is None or r3 <= 0.01):
        return "FRAGILE_BREADTH"
    if breadth <= 0.30 and drawdown is not None and drawdown <= -0.02:
        return "FRAGILE_PULLBACK"
    return None


def value_or_none(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def market_row(metrics: pd.DataFrame, ranking_date_text: str) -> dict[str, Any] | None:
    ranking_date_value = parse_date(ranking_date_text)
    rows = metrics[metrics["trade_date"] == ranking_date_value]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return {
        "trade_date": ranking_date_text,
        "defense_level": row["defense_level"],
        "defense_reason": row["defense_reason"],
        "fragility_watch": row["fragility_watch"] if pd.notna(row["fragility_watch"]) else None,
        "equal_weight_return": number(row["equal_weight_return"]),
        "market_return_3d": number(row["market_return_3d"]),
        "market_return_5d": number(row["market_return_5d"]),
        "drawdown_from_20d_high": number(row["drawdown_from_20d_high"]),
        "breadth_ma20": number(row["breadth_ma20"]),
        "down_streak": int(row["down_streak"]),
        "stock_count": int(row["stock_count"]),
    }


def rescale_weights(weights: dict[str, float], target_gross: float) -> dict[str, float]:
    current = sum(weights.values())
    if current <= 0 or target_gross <= 0:
        return {stock_id: 0.0 for stock_id in weights}
    scale = min(1.0, target_gross / current)
    return {stock_id: round(weight * scale, 6) for stock_id, weight in weights.items()}


def weights_for_variant(base_weights: dict[str, float], level: str, variant: VariantSpec) -> dict[str, float]:
    if variant.name == "baseline_production" or variant.message_only:
        return dict(base_weights)
    order = LEVEL_ORDER.get(level, 0)
    if variant.block_level3 and order >= LEVEL_ORDER["RISK_OFF_BLOCK"]:
        return {stock_id: 0.0 for stock_id in base_weights}
    cap = None
    if order >= LEVEL_ORDER["RISK_OFF_BLOCK"]:
        cap = variant.risk_off_gross_cap
    elif order >= LEVEL_ORDER["DEFENSIVE"]:
        cap = variant.defensive_gross_cap
    if cap is None:
        return dict(base_weights)
    return rescale_weights(base_weights, cap)


def simulate_rankings(
    ranking_paths: list[Path],
    price_frame: pd.DataFrame,
    market_metrics: pd.DataFrame,
    args: argparse.Namespace,
) -> dict[str, Any]:
    horizons = [int(value.strip()) for value in args.horizons.split(",") if value.strip()]
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    trades: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    ranking_days: list[dict[str, Any]] = []

    for ranking_path in ranking_paths:
        ranking_date_text = run_backtest_replay.ranking_date(ranking_path)
        context = market_row(market_metrics, ranking_date_text)
        if context is None:
            skipped.append({"ranking_date": ranking_date_text, "reason": "missing_market_context"})
            continue
        items = run_backtest_replay.read_ranking(ranking_path, args.top_n)
        entry_date = run_backtest_replay.next_market_trade_date(trade_dates, ranking_date_text, args.entry_delay_trade_days)
        base_weights = run_backtest_replay.portfolio_weights(
            items,
            default_gross_exposure=args.default_gross_exposure,
            max_position_weight=args.max_position_weight,
        )
        ranking_days.append(
            {
                **context,
                "ranking_path": repo_path(ranking_path),
                "entry_date": entry_date.isoformat() if entry_date else None,
                "market_regime_in_ranking": ranking_field(ranking_path, "market_regime"),
                "baseline_gross_weight": round(sum(base_weights.values()), 6),
            }
        )
        if entry_date is None:
            skipped.append({"ranking_date": ranking_date_text, "reason": "missing_entry_date"})
            continue

        base_trades_by_horizon: dict[int, list[dict[str, Any]]] = {horizon: [] for horizon in horizons}
        for item in items:
            stock_prices = price_index.get(item["stock_id"])
            if stock_prices is None:
                skipped.append({"ranking_date": ranking_date_text, "stock_id": item["stock_id"], "reason": "missing_price_history"})
                continue
            for horizon in horizons:
                holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, horizon)
                if holding_dates is None:
                    skipped.append(
                        {
                            "ranking_date": ranking_date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "insufficient_future_market_bars",
                        }
                    )
                    continue
                holding = run_backtest_replay.stock_holding_bars(stock_prices, holding_dates)
                if holding is None or run_backtest_replay.has_missing_ohlc(holding):
                    skipped.append(
                        {
                            "ranking_date": ranking_date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "missing_ohlc_bar",
                            "expected_entry_date": entry_date.isoformat(),
                            "expected_exit_date": holding_dates[-1].isoformat(),
                        }
                    )
                    continue
                outcome = run_backtest_replay.simulate_trade(holding, args.fee_rate, args.tax_rate, args.slippage_rate)
                if outcome is None:
                    skipped.append({"ranking_date": ranking_date_text, "stock_id": item["stock_id"], "reason": "invalid_ohlc_bar"})
                    continue
                trade = {
                    "ranking_date": ranking_date_text,
                    "horizon": horizon,
                    "stock_id": item["stock_id"],
                    "stock_name": item.get("stock_name"),
                    "rank": item["rank"],
                    "defense_level": context["defense_level"],
                    "baseline_weight": base_weights.get(item["stock_id"], 0.0),
                    **outcome,
                }
                trades.append(trade)
                base_trades_by_horizon[horizon].append(trade)

        for horizon, horizon_trades in base_trades_by_horizon.items():
            for variant in VARIANTS:
                variant_weights = weights_for_variant(base_weights, str(context["defense_level"]), variant)
                observation = variant_observation(ranking_date_text, horizon, horizon_trades, variant_weights, variant.name)
                if observation:
                    observations.append({**observation, "defense_level": context["defense_level"]})

    return {
        "ranking_days": ranking_days,
        "trades": trades,
        "portfolio_observations": observations,
        "skipped": skipped,
    }


def ranking_field(path: Path, field: str) -> str | None:
    try:
        frame = pd.read_csv(path, dtype=str, nrows=1)
    except Exception:
        return None
    if frame.empty or field not in frame.columns:
        return None
    value = frame.iloc[0].get(field)
    if value is None or pd.isna(value):
        return None
    return str(value)


def variant_observation(
    ranking_date_text: str,
    horizon: int,
    trades: list[dict[str, Any]],
    weights: dict[str, float],
    variant_name: str,
) -> dict[str, Any] | None:
    if not trades:
        return None
    invested_weight = sum(float(weights.get(trade["stock_id"], 0.0)) for trade in trades)
    weighted_return = sum(float(weights.get(trade["stock_id"], 0.0)) * float(trade["net_return"]) for trade in trades)
    return {
        "variant": variant_name,
        "ranking_date": ranking_date_text,
        "horizon": horizon,
        "positions": sum(1 for trade in trades if weights.get(trade["stock_id"], 0.0) > 0),
        "invested_weight": round(invested_weight, 6),
        "cash_weight": round(max(0.0, 1 - invested_weight), 6),
        "portfolio_return": round(weighted_return, 6),
    }


def summarize_window(window: str, replay: dict[str, Any]) -> dict[str, Any]:
    observations = pd.DataFrame(replay["portfolio_observations"])
    ranking_days = pd.DataFrame(replay["ranking_days"])
    if observations.empty:
        return {"window": window, "status": "NO_OBSERVATIONS"}

    variant_summary: dict[str, Any] = {}
    for (variant, horizon), group in observations.groupby(["variant", "horizon"]):
        returns = pd.to_numeric(group["portfolio_return"], errors="coerce")
        key = f"{variant}:h{int(horizon)}"
        variant_summary[key] = {
            "observation_count": int(len(group)),
            "avg_portfolio_return": round(float(returns.mean()), 6),
            "hit_rate": round(float((returns > 0).mean()), 6),
            "total_compounded_return": round(float((1 + returns).prod() - 1), 6),
            "max_drawdown": round(run_backtest_replay.max_drawdown(list(returns)), 6),
            "avg_invested_weight": round(float(pd.to_numeric(group["invested_weight"], errors="coerce").mean()), 6),
        }

    level_counts = ranking_days["defense_level"].value_counts().to_dict() if not ranking_days.empty else {}
    by_level = summarize_by_level(observations)
    warning = warning_metrics(observations)
    return {
        "window": window,
        "ranking_day_count": int(len(ranking_days)),
        "level_counts": {str(key): int(value) for key, value in level_counts.items()},
        "variant_summary": variant_summary,
        "by_defense_level": by_level,
        "warning_metrics": warning,
        "skipped_count": int(len(replay["skipped"])),
    }


def summarize_by_level(observations: pd.DataFrame) -> dict[str, Any]:
    baseline = observations[observations["variant"] == "baseline_production"].copy()
    result: dict[str, Any] = {}
    for (level, horizon), group in baseline.groupby(["defense_level", "horizon"]):
        returns = pd.to_numeric(group["portfolio_return"], errors="coerce")
        result[f"{level}:h{int(horizon)}"] = {
            "observation_count": int(len(group)),
            "avg_portfolio_return": round(float(returns.mean()), 6),
            "hit_rate": round(float((returns > 0).mean()), 6),
        }
    return result


def warning_metrics(observations: pd.DataFrame) -> dict[str, Any]:
    baseline_5d = observations[(observations["variant"] == "baseline_production") & (observations["horizon"] == 5)].copy()
    if baseline_5d.empty:
        return {"status": "NO_5D_BASELINE"}
    baseline_5d["is_warning"] = baseline_5d["defense_level"].map(lambda value: LEVEL_ORDER.get(str(value), 0) >= 2)
    baseline_5d["is_adverse"] = pd.to_numeric(baseline_5d["portfolio_return"], errors="coerce") < 0
    warning_count = int(baseline_5d["is_warning"].sum())
    adverse_count = int(baseline_5d["is_adverse"].sum())
    true_positive = int((baseline_5d["is_warning"] & baseline_5d["is_adverse"]).sum())
    positive_warning = baseline_5d[baseline_5d["is_warning"] & ~baseline_5d["is_adverse"]]
    return {
        "status": "OK",
        "warning_definition": "DEFENSIVE or RISK_OFF_BLOCK on ranking date",
        "adverse_definition": "baseline 5D portfolio_return < 0",
        "warning_count": warning_count,
        "adverse_count": adverse_count,
        "precision": round(true_positive / warning_count, 6) if warning_count else None,
        "recall": round(true_positive / adverse_count, 6) if adverse_count else None,
        "missed_rebound_count": int(len(positive_warning)),
        "missed_rebound_avg_baseline_return": round(float(positive_warning["portfolio_return"].mean()), 6)
        if not positive_warning.empty
        else None,
    }


def compare_variants(long_summary: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = long_summary.get("variant_summary", {})
    rows: list[dict[str, Any]] = []
    for key, item in baseline.items():
        if not key.startswith("baseline_production:"):
            continue
        horizon = key.split(":", 1)[1]
        base_return = item.get("avg_portfolio_return")
        base_dd = item.get("max_drawdown")
        for variant in [spec.name for spec in VARIANTS if spec.name != "baseline_production"]:
            candidate = baseline.get(f"{variant}:{horizon}")
            if not candidate:
                continue
            rows.append(
                {
                    "variant": variant,
                    "horizon": horizon,
                    "avg_return_delta_vs_baseline": round(float(candidate["avg_portfolio_return"]) - float(base_return), 6),
                    "drawdown_avoided_vs_baseline": round(float(candidate["max_drawdown"]) - float(base_dd), 6),
                    "avg_invested_weight": candidate["avg_invested_weight"],
                }
            )
    return rows


def event_postcheck(event_files: list[Path], market_metrics: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in event_files:
        date_text = run_backtest_replay.ranking_date(path)
        context = market_row(market_metrics, date_text)
        items = run_backtest_replay.read_ranking(path, 10)
        rows.append(
            {
                **(context or {"trade_date": date_text, "defense_level": "UNKNOWN", "defense_reason": "missing_market_context"}),
                "ranking_path": repo_path(path),
                "market_regime_in_ranking": ranking_field(path, "market_regime"),
                "gross_exposure_in_ranking": next((item.get("gross_exposure") for item in items if item.get("gross_exposure") is not None), None),
            }
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    price_frame = run_backtest_replay.load_price_frame(features_path)
    market_frame = load_market_frame(features_path)
    market_metrics = build_market_metrics(market_frame)

    long_files = ranking_files(resolve_path(args.long_rankings_dir), args.start_date, args.end_date)
    recent_files = ranking_files(resolve_path(args.recent_rankings_dir), args.recent_start_date, args.end_date)
    event_files = ranking_files(resolve_path(args.event_rankings_dir), args.event_start_date, args.event_end_date)

    long_replay = simulate_rankings(long_files, price_frame, market_metrics, args)
    recent_replay = simulate_rankings(recent_files, price_frame, market_metrics, args)
    long_summary = summarize_window("long", long_replay)
    recent_summary = summarize_window("recent", recent_replay)
    comparisons = compare_variants(long_summary)
    event_rows = event_postcheck(event_files, market_metrics)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "RESEARCH_REPLAY_READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "contract": {
            "research_only": True,
            "reads_existing_features": True,
            "reads_existing_ranking_artifacts": True,
            "trains_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_clawd_message": False,
            "live_send": False,
            "promotion_ready": False,
        },
        "inputs": {
            "features": repo_path(features_path),
            "long_rankings_dir": repo_path(resolve_path(args.long_rankings_dir)),
            "recent_rankings_dir": repo_path(resolve_path(args.recent_rankings_dir)),
            "event_rankings_dir": repo_path(resolve_path(args.event_rankings_dir)),
            "long_file_count": len(long_files),
            "recent_file_count": len(recent_files),
            "event_file_count": len(event_files),
            "horizons": [int(value.strip()) for value in args.horizons.split(",") if value.strip()],
            "entry_delay_trade_days": args.entry_delay_trade_days,
            "top_n": args.top_n,
        },
        "policy": {
            "level_1": "CAUTION：3日跌幅<=-1.5%、20日高點回撤<=-3%、或連跌>=2且MA20廣度<=45%",
            "level_2": "DEFENSIVE：3日跌幅<=-2%、20日高點回撤<=-4%、或連跌>=3且3日跌幅<=-1.5%",
            "level_3": "RISK_OFF_BLOCK：5日跌幅<=-4%、20日高點回撤<=-6%、或MA20廣度<=35%且3日跌幅<=-2%",
        },
        "summary": {
            "long": long_summary,
            "recent": recent_summary,
            "variant_comparison_long": comparisons,
            "event_postcheck": {
                "window": f"{args.event_start_date}~{args.event_end_date}",
                "note": "事件週只做 market/ranking 狀態 post-check；forward 3D/5D/10D 尚未完全成熟，不作調參來源。",
                "rows": event_rows,
            },
        },
        "details": {
            "long_ranking_days": long_replay["ranking_days"],
            "recent_ranking_days": recent_replay["ranking_days"],
            "long_portfolio_observations": long_replay["portfolio_observations"],
            "recent_portfolio_observations": recent_replay["portfolio_observations"],
            "long_skipped_sample": long_replay["skipped"][:50],
            "recent_skipped_sample": recent_replay["skipped"][:50],
        },
    }


def fmt_pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    long_summary = payload["summary"]["long"]
    recent_summary = payload["summary"]["recent"]
    lines = [
        "# Market Defense Guard Replay",
        "",
        f"- run_date: `{payload['run_date']}`",
        f"- status: `{payload['status']}`",
        f"- long ranking days: `{long_summary.get('ranking_day_count')}`",
        f"- recent ranking days: `{recent_summary.get('ranking_day_count')}`",
        "",
        "## 結論讀法",
        "",
        "- 本 artifact 只驗證 MARKET-DEFENSE-01 候選防守閘門，不改 production ranking / model / Clawd live send。",
        "- 防守訊號以 ranking 日收盤後可得的大盤等權跌幅、MA20 廣度、20 日高點回撤判斷。",
        "- 2026-06-22~2026-06-26 只做事件 post-check；未成熟 forward horizon 不拿來調參。",
        "",
        "## Long Window Level Counts",
        "",
        "| Level | Days |",
        "|---|---:|",
    ]
    for level, count in sorted(long_summary.get("level_counts", {}).items(), key=lambda item: LEVEL_ORDER.get(item[0], 99)):
        lines.append(f"| `{level}` | {count} |")
    lines.extend(["", "## Baseline By Defense Level", "", "| Level:Horizon | Buckets | Avg Return | Hit Rate |", "|---|---:|---:|---:|"])
    for key, item in sorted(long_summary.get("by_defense_level", {}).items()):
        lines.append(f"| `{key}` | {item['observation_count']} | {fmt_pct(item['avg_portfolio_return'])} | {fmt_pct(item['hit_rate'])} |")
    lines.extend(["", "## Warning Metrics", ""])
    warning = long_summary.get("warning_metrics", {})
    lines.extend(
        [
            f"- precision: `{fmt_pct(warning.get('precision'))}`",
            f"- recall: `{fmt_pct(warning.get('recall'))}`",
            f"- warning_count: `{warning.get('warning_count')}`",
            f"- adverse_count: `{warning.get('adverse_count')}`",
            f"- missed_rebound_count: `{warning.get('missed_rebound_count')}`",
            f"- missed_rebound_avg_baseline_return: `{fmt_pct(warning.get('missed_rebound_avg_baseline_return'))}`",
            "",
            "## Variant Comparison - Long Window",
            "",
            "| Variant | Horizon | Return Delta | Drawdown Delta | Avg Invested |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in payload["summary"]["variant_comparison_long"]:
        lines.append(
            "| `{variant}` | `{horizon}` | {ret} | {dd} | {weight} |".format(
                variant=row["variant"],
                horizon=row["horizon"],
                ret=fmt_pct(row["avg_return_delta_vs_baseline"]),
                dd=fmt_pct(row["drawdown_avoided_vs_baseline"]),
                weight=fmt_pct(row["avg_invested_weight"]),
            )
        )
    lines.extend(["", "## Event Postcheck", "", "| Date | Defense Level | Watch | Ranking Regime | Gross | Reason |", "|---|---|---|---|---:|---|"])
    for row in payload["summary"]["event_postcheck"]["rows"]:
        lines.append(
            "| `{date}` | `{level}` | `{watch}` | `{regime}` | {gross} | {reason} |".format(
                date=row.get("trade_date"),
                level=row.get("defense_level"),
                watch=row.get("fragility_watch"),
                regime=row.get("market_regime_in_ranking"),
                gross=fmt_pct(row.get("gross_exposure_in_ranking")),
                reason=row.get("defense_reason"),
            )
        )
    lines.extend(["", "## 邊界", "", "- 第一階段建議只接 daily report risk notes / 主攻候補語氣，不直接改排序。"])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"market_defense_guard_replay_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "markdown": repo_path(output.with_suffix(".md")),
                "long_ranking_days": payload["summary"]["long"].get("ranking_day_count"),
                "recent_ranking_days": payload["summary"]["recent"].get("ranking_day_count"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
