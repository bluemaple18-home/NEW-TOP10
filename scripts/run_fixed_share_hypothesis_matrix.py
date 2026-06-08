#!/usr/bin/env python3
"""固定股數 Top10 假設矩陣。

此腳本只讀歷史 ranking、features、盤勢與產業對照，不訓練模型、不修改正式
ranking。它用同一套固定 100 股帳本，一次檢查出場、rank、入榜持續性、盤勢
與產業集中假設。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import build_candidate_persistence, run_backtest_replay  # noqa: E402
from scripts.build_high_choppy_context_overlay import load_regime_frame, rolling_high_choppy, strict_high_choppy  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SCHEMA_VERSION = "fixed-share-hypothesis-matrix.v1"


@dataclass(frozen=True)
class ExitPolicy:
    name: str
    max_horizon: int
    early_take_profit_pct: float | None = None
    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None
    trailing_stop_pct: float | None = None


EXIT_POLICIES = [
    ExitPolicy("fixed_20d", 20),
    ExitPolicy("fixed_30d", 30),
    ExitPolicy("fixed_40d", 40),
    ExitPolicy("h20_early_tp07", 20, early_take_profit_pct=0.07),
    ExitPolicy("h30_early_tp07", 30, early_take_profit_pct=0.07),
    ExitPolicy("h40_early_tp07", 40, early_take_profit_pct=0.07),
    ExitPolicy("h30_early_tp10", 30, early_take_profit_pct=0.10),
    ExitPolicy("h30_early_tp12", 30, early_take_profit_pct=0.12),
    ExitPolicy("h30_early_tp15", 30, early_take_profit_pct=0.15),
    ExitPolicy("h40_early_tp10", 40, early_take_profit_pct=0.10),
    ExitPolicy("h40_early_tp12", 40, early_take_profit_pct=0.12),
    ExitPolicy("h40_early_tp15", 40, early_take_profit_pct=0.15),
    ExitPolicy("h30_early_tp07_late_tp18", 30, early_take_profit_pct=0.07, take_profit_pct=0.18),
    ExitPolicy("h30_early_tp07_late_tp25", 30, early_take_profit_pct=0.07, take_profit_pct=0.25),
    ExitPolicy("h40_early_tp07_trail12", 40, early_take_profit_pct=0.07, trailing_stop_pct=0.12),
    ExitPolicy("h30_tp18_sl08", 30, take_profit_pct=0.18, stop_loss_pct=0.08),
    ExitPolicy("h30_tp25_sl10", 30, take_profit_pct=0.25, stop_loss_pct=0.10),
    ExitPolicy("h30_trail10", 30, trailing_stop_pct=0.10),
    ExitPolicy("h30_trail15", 30, trailing_stop_pct=0.15),
    ExitPolicy("h30_trail18", 30, trailing_stop_pct=0.18),
    ExitPolicy("h30_trail22", 30, trailing_stop_pct=0.22),
    ExitPolicy("h40_trail12", 40, trailing_stop_pct=0.12),
    ExitPolicy("h40_trail15", 40, trailing_stop_pct=0.15),
    ExitPolicy("h40_trail18", 40, trailing_stop_pct=0.18),
    ExitPolicy("h40_trail22", 40, trailing_stop_pct=0.22),
    ExitPolicy("h40_trail25", 40, trailing_stop_pct=0.25),
    ExitPolicy("h40_tp25_sl10", 40, take_profit_pct=0.25, stop_loss_pct=0.10),
    ExitPolicy("h40_tp35_sl12", 40, take_profit_pct=0.35, stop_loss_pct=0.12),
]

RANK_SCOPES = {
    "all_top10": lambda rank: rank <= 10,
    "top1_3": lambda rank: rank <= 3,
    "top4_7": lambda rank: 4 <= rank <= 7,
    "top8_10": lambda rank: 8 <= rank <= 10,
    "top5": lambda rank: rank <= 5,
    "top7": lambda rank: rank <= 7,
}

PERSISTENCE_SCOPES = {
    "all": lambda item: True,
    "new_today": lambda item: int(item.get("consecutive_ranked_days") or 0) == 1,
    "streak_2_3": lambda item: 2 <= int(item.get("consecutive_ranked_days") or 0) <= 3,
    "streak_4plus": lambda item: int(item.get("consecutive_ranked_days") or 0) >= 4,
    "rank_improved": lambda item: item.get("rank_delta") is not None and float(item.get("rank_delta") or 0) > 0,
    "rank_worsened": lambda item: item.get("rank_delta") is not None and float(item.get("rank_delta") or 0) < 0,
    "not_worsened": lambda item: item.get("rank_delta") is None or float(item.get("rank_delta") or 0) >= 0,
}

REGIME_SCOPES = ("ALL", "BIG_BULL", "HIGH_CHOPPY_CONTEXT", "OTHER")

SIZING_POLICIES = {
    "equal_100_shares": lambda row: float(row.get("buy_cash") or 0),
    "equal_cash_per_stock": lambda row: 1.0,
    "rank_linear_10_to_1": lambda row: float(max(1, 11 - int(row.get("rank") or 10))),
    "rank_bucket_top_heavy": lambda row: 1.5 if int(row.get("rank") or 10) <= 3 else 1.0 if int(row.get("rank") or 10) <= 7 else 0.75,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run fixed-share hypothesis matrix")
    parser.add_argument("--rankings-dir", default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--group-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--variant-label", default="production")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--shares", type=int, default=100)
    parser.add_argument("--min-holding-days", type=int, default=5)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_group_map(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype={"stock_id": str})
    required = {"stock_id", "industry_name", "sector_name"}
    if not required <= set(frame.columns):
        return {}
    result = {}
    for row in frame.itertuples(index=False):
        stock_id = str(row.stock_id).zfill(4)
        result[stock_id] = {
            "industry_name": str(getattr(row, "industry_name", "") or ""),
            "sector_name": str(getattr(row, "sector_name", "") or ""),
        }
    return result


def build_regime_map(path: Path) -> dict[str, dict[str, Any]]:
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_STRICT"] = frame.apply(strict_high_choppy, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    return {
        str(row.trade_date_text): {
            "base_regime": str(row.regime_label),
            "BIG_BULL": bool(row.BIG_BULL),
            "HIGH_CHOPPY_STRICT": bool(row.HIGH_CHOPPY_STRICT),
            "HIGH_CHOPPY_CONTEXT": bool(row.HIGH_CHOPPY_CONTEXT),
        }
        for row in frame.itertuples(index=False)
    }


def regime_match(scope: str, info: dict[str, Any]) -> bool:
    if scope == "ALL":
        return True
    if scope == "BIG_BULL":
        return bool(info.get("BIG_BULL"))
    if scope == "HIGH_CHOPPY_CONTEXT":
        return bool(info.get("HIGH_CHOPPY_CONTEXT"))
    if scope == "OTHER":
        return not bool(info.get("BIG_BULL")) and not bool(info.get("HIGH_CHOPPY_CONTEXT"))
    return False


def persistence_index(rankings_dir: Path, top_n: int) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for path in run_backtest_replay.ranking_files(rankings_dir, None):
        payload = build_candidate_persistence.build_payload(target_ranking=path, rankings_dir=rankings_dir, limit=top_n)
        date_text = str(payload["ranking_date"])
        for item in payload.get("items", []):
            index[(date_text, str(item.get("stock_id", "")).zfill(4))] = item
    return index


def buy_cash(entry_open: float, shares: int, fee_rate: float, slippage_rate: float) -> float:
    return entry_open * shares * (1 + slippage_rate) * (1 + fee_rate)


def sell_cash(exit_price: float, shares: int, fee_rate: float, tax_rate: float, slippage_rate: float) -> float:
    return exit_price * shares * (1 - slippage_rate) * (1 - fee_rate - tax_rate)


def simulate_exit(
    holding: pd.DataFrame,
    policy: ExitPolicy,
    min_holding_days: int,
) -> tuple[str, Any, float]:
    entry_open = float(holding.iloc[0]["open"])
    high_water = entry_open
    for index, row in enumerate(holding.itertuples(index=False), start=1):
        high = float(row.high)
        low = float(row.low)
        high_water = max(high_water, high)
        early_take_price = entry_open * (1 + policy.early_take_profit_pct) if policy.early_take_profit_pct is not None else None
        if early_take_price is not None and high >= early_take_price:
            return "early_take_profit", row.trade_date, early_take_price
        if index < min_holding_days:
            continue
        stop_price = entry_open * (1 - policy.stop_loss_pct) if policy.stop_loss_pct is not None else None
        take_price = entry_open * (1 + policy.take_profit_pct) if policy.take_profit_pct is not None else None
        trailing_price = high_water * (1 - policy.trailing_stop_pct) if policy.trailing_stop_pct is not None else None
        if stop_price is not None and low <= stop_price:
            return "stop_loss", row.trade_date, stop_price
        if trailing_price is not None and low <= trailing_price:
            return "trailing_stop", row.trade_date, trailing_price
        if take_price is not None and high >= take_price:
            return "take_profit", row.trade_date, take_price
    exit_row = holding.iloc[-1]
    return "horizon_close", exit_row["trade_date"], float(exit_row["close"])


def risk_metrics(stock_prices: pd.DataFrame, holding_dates: list[Any], entry_open: float, exit_date: Any, exit_price: float) -> dict[str, Any]:
    holding = stock_prices[stock_prices["trade_date"].isin(holding_dates)].reset_index(drop=True)
    if holding.empty or "high" not in holding.columns or "low" not in holding.columns:
        return {"mae": None, "mfe": None, "giveback": None, "risk_bar_count": 0}
    holding = holding[holding["trade_date"] <= exit_date]
    highs = pd.to_numeric(holding["high"], errors="coerce").dropna()
    lows = pd.to_numeric(holding["low"], errors="coerce").dropna()
    if highs.empty or lows.empty or entry_open <= 0:
        return {"mae": None, "mfe": None, "giveback": None, "risk_bar_count": int(len(holding))}
    mfe = float(highs.max()) / entry_open - 1
    mae = float(lows.min()) / entry_open - 1
    gross_exit_return = float(exit_price) / entry_open - 1
    return {
        "mae": round(mae, 6),
        "mfe": round(mfe, 6),
        "giveback": round(max(0.0, mfe - gross_exit_return), 6),
        "risk_bar_count": int(len(holding)),
    }


def policy_needs_intraday(policy: ExitPolicy) -> bool:
    return (
        policy.early_take_profit_pct is not None
        or policy.take_profit_pct is not None
        or policy.stop_loss_pct is not None
        or policy.trailing_stop_pct is not None
    )


def has_missing_required_prices(holding: pd.DataFrame, policy: ExitPolicy) -> bool:
    required = ["open", "close"]
    if policy_needs_intraday(policy):
        required.extend(["high", "low"])
    return bool(holding[required].isna().any().any())


def build_base_trades(args: argparse.Namespace) -> list[dict[str, Any]]:
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    price_frame = run_backtest_replay.load_price_frame(features_path)
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    persistence = persistence_index(rankings_dir, args.top_n)
    group_map = load_group_map(resolve_path(args.group_map))
    regime_map = build_regime_map(resolve_path(args.market_regime_history))
    files = run_backtest_replay.ranking_files(rankings_dir, None)

    trades: list[dict[str, Any]] = []
    for ranking_path in files:
        ranking_date = run_backtest_replay.ranking_date(ranking_path)
        entry_date = run_backtest_replay.next_market_trade_date(trade_dates, ranking_date, args.entry_delay_trade_days)
        if entry_date is None:
            continue
        regime = regime_map.get(ranking_date, {})
        ranking_rows = run_backtest_replay.read_ranking(ranking_path, args.top_n)
        for item in ranking_rows:
            stock_id = item["stock_id"]
            stock_prices = price_index.get(stock_id)
            if stock_prices is None:
                continue
            persistence_item = persistence.get((ranking_date, stock_id), {})
            group_info = group_map.get(stock_id, {})
            for policy in EXIT_POLICIES:
                holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, policy.max_horizon)
                if holding_dates is None:
                    continue
                if policy_needs_intraday(policy):
                    holding = run_backtest_replay.stock_holding_bars(stock_prices, holding_dates)
                    if holding is None or has_missing_required_prices(holding, policy):
                        continue
                    entry_open = float(holding.iloc[0]["open"])
                    exit_reason, exit_date, exit_price = simulate_exit(holding, policy, args.min_holding_days)
                else:
                    exit_date = holding_dates[-1]
                    entry_bar = stock_prices[stock_prices["trade_date"] == entry_date]
                    exit_bar = stock_prices[stock_prices["trade_date"] == exit_date]
                    if entry_bar.empty or exit_bar.empty:
                        continue
                    entry_open = float(entry_bar.iloc[0]["open"])
                    exit_price = float(exit_bar.iloc[0]["close"])
                    if pd.isna(entry_open) or pd.isna(exit_price):
                        continue
                    exit_reason = "horizon_close"
                cost = buy_cash(entry_open, args.shares, args.fee_rate, args.slippage_rate)
                proceeds = sell_cash(exit_price, args.shares, args.fee_rate, args.tax_rate, args.slippage_rate)
                net_pnl = proceeds - cost
                risk = risk_metrics(stock_prices, holding_dates, entry_open, exit_date, exit_price)
                trades.append(
                    {
                        "variant": args.variant_label,
                        "policy": policy.name,
                        "ranking_date": ranking_date,
                        "rank": int(item["rank"]),
                        "stock_id": stock_id,
                        "stock_name": item.get("stock_name"),
                        "entry_date": entry_date.isoformat(),
                        "exit_date": exit_date.isoformat(),
                        "exit_reason": exit_reason,
                        "entry_open": round(entry_open, 4),
                        "exit_price": round(float(exit_price), 4),
                        "shares": int(args.shares),
                        "buy_cash": round(cost, 2),
                        "sell_cash": round(proceeds, 2),
                        "net_pnl": round(net_pnl, 2),
                        "net_return": round(net_pnl / cost, 6) if cost else None,
                        **risk,
                        "consecutive_ranked_days": int(persistence_item.get("consecutive_ranked_days") or 0),
                        "rank_delta": persistence_item.get("rank_delta"),
                        "industry_name": group_info.get("industry_name") or item.get("industry_name"),
                        "sector_name": group_info.get("sector_name") or item.get("sector_name"),
                        "base_regime": regime.get("base_regime"),
                        "BIG_BULL": bool(regime.get("BIG_BULL")),
                        "HIGH_CHOPPY_CONTEXT": bool(regime.get("HIGH_CHOPPY_CONTEXT")),
                    }
                )
    return trades


def metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"trade_count": 0}
    frame = pd.DataFrame(rows)
    pnl = pd.to_numeric(frame["net_pnl"], errors="coerce")
    buy = pd.to_numeric(frame["buy_cash"], errors="coerce")
    returns = pd.to_numeric(frame["net_return"], errors="coerce")
    mae = pd.to_numeric(frame.get("mae"), errors="coerce") if "mae" in frame else pd.Series(dtype=float)
    mfe = pd.to_numeric(frame.get("mfe"), errors="coerce") if "mfe" in frame else pd.Series(dtype=float)
    giveback = pd.to_numeric(frame.get("giveback"), errors="coerce") if "giveback" in frame else pd.Series(dtype=float)
    total_pnl = float(pnl.sum())
    total_buy = float(buy.sum())
    summary = {
        "trade_count": int(len(frame)),
        "ranking_day_count": int(frame["ranking_date"].nunique()),
        "total_buy_cash": round(total_buy, 2),
        "total_net_pnl": round(total_pnl, 2),
        "return_on_buy_cash": round(total_pnl / total_buy, 6) if total_buy else None,
        "avg_trade_net_return": round(float(returns.mean()), 6),
        "median_trade_net_return": round(float(returns.median()), 6),
        "win_rate": round(float((returns > 0).mean()), 6),
    }
    risk_count = int(giveback.notna().sum())
    if risk_count:
        summary.update(
            {
                "risk_metric_count": risk_count,
                "avg_mae": round(float(mae.mean()), 6),
                "worst_mae": round(float(mae.min()), 6),
                "avg_mfe": round(float(mfe.mean()), 6),
                "avg_giveback": round(float(giveback.mean()), 6),
                "p90_giveback": round(float(giveback.quantile(0.9)), 6),
            }
        )
    else:
        summary.update(
            {
                "risk_metric_count": 0,
                "avg_mae": None,
                "worst_mae": None,
                "avg_mfe": None,
                "avg_giveback": None,
                "p90_giveback": None,
            }
        )
    return summary


def sizing_summary(rows: list[dict[str, Any]], sizing_name: str) -> dict[str, Any]:
    if not rows:
        return {"trade_count": 0}
    frame = pd.DataFrame(rows)
    weights = frame.apply(SIZING_POLICIES[sizing_name], axis=1).astype(float)
    returns = pd.to_numeric(frame["net_return"], errors="coerce").fillna(0.0)
    weighted_return = float((weights * returns).sum() / weights.sum()) if float(weights.sum()) > 0 else None
    return {
        "trade_count": int(len(frame)),
        "ranking_day_count": int(frame["ranking_date"].nunique()),
        "weighted_avg_return": round(weighted_return, 6) if weighted_return is not None else None,
        "win_rate": round(float((returns > 0).mean()), 6),
    }


def sector_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"trade_count": 0}
    frame = pd.DataFrame(rows)
    buy = pd.to_numeric(frame["buy_cash"], errors="coerce")
    pnl = pd.to_numeric(frame["net_pnl"], errors="coerce")
    total_buy = float(buy.sum())
    total_pnl = float(pnl.sum())
    grouped = []
    for sector, group in frame.groupby("sector_name", dropna=False):
        group_buy = float(pd.to_numeric(group["buy_cash"], errors="coerce").sum())
        group_pnl = float(pd.to_numeric(group["net_pnl"], errors="coerce").sum())
        grouped.append(
            {
                "sector_name": str(sector),
                "trade_count": int(len(group)),
                "buy_share": round(group_buy / total_buy, 6) if total_buy else None,
                "pnl_share": round(group_pnl / total_pnl, 6) if total_pnl else None,
                "return_on_buy_cash": round(group_pnl / group_buy, 6) if group_buy else None,
            }
        )
    top_by_buy = sorted(grouped, key=lambda row: float(row.get("buy_share") or 0), reverse=True)[:5]
    top_by_pnl = sorted(grouped, key=lambda row: float(row.get("pnl_share") or -999), reverse=True)[:5]
    return {
        "trade_count": int(len(frame)),
        "sector_count": len(grouped),
        "max_sector_buy_share": top_by_buy[0]["buy_share"] if top_by_buy else None,
        "top_by_buy": top_by_buy,
        "top_by_pnl": top_by_pnl,
    }


def filtered(rows: list[dict[str, Any]], **criteria: Any) -> list[dict[str, Any]]:
    result = rows
    if policy := criteria.get("policy"):
        result = [row for row in result if row["policy"] == policy]
    if rank_scope := criteria.get("rank_scope"):
        pred = RANK_SCOPES[rank_scope]
        result = [row for row in result if pred(int(row["rank"]))]
    if persistence_scope := criteria.get("persistence_scope"):
        pred = PERSISTENCE_SCOPES[persistence_scope]
        result = [row for row in result if pred(row)]
    if regime_scope := criteria.get("regime_scope"):
        result = [
            row
            for row in result
            if regime_match(
                regime_scope,
                {"BIG_BULL": row.get("BIG_BULL"), "HIGH_CHOPPY_CONTEXT": row.get("HIGH_CHOPPY_CONTEXT")},
            )
        ]
    return result


def matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    exit_policy = {policy.name: metric_summary(filtered(rows, policy=policy.name)) for policy in EXIT_POLICIES}
    rank_policy = {}
    persistence_policy = {}
    regime_policy = {}
    sector_policy = {}
    sizing_policy = {}
    concentration_policy = {}
    for policy in EXIT_POLICIES:
        policy_rows = filtered(rows, policy=policy.name)
        for sizing_name in SIZING_POLICIES:
            sizing_policy[f"{policy.name}::{sizing_name}"] = sizing_summary(policy_rows, sizing_name)
        concentration_policy[policy.name] = sector_concentration(policy_rows)
        for scope in RANK_SCOPES:
            rank_policy[f"{policy.name}::{scope}"] = metric_summary(filtered(rows, policy=policy.name, rank_scope=scope))
        for scope in PERSISTENCE_SCOPES:
            persistence_policy[f"{policy.name}::{scope}"] = metric_summary(filtered(rows, policy=policy.name, persistence_scope=scope))
        for scope in REGIME_SCOPES:
            regime_policy[f"{policy.name}::{scope}"] = metric_summary(filtered(rows, policy=policy.name, regime_scope=scope))

    frame = pd.DataFrame(rows)
    if not frame.empty:
        for (policy, sector), group in frame.groupby(["policy", "sector_name"], dropna=False):
            sector_policy[f"{policy}::{sector}"] = metric_summary(group.to_dict(orient="records"))
    return {
        "exit_policy": exit_policy,
        "rank_policy": rank_policy,
        "persistence_policy": persistence_policy,
        "regime_policy": regime_policy,
        "sector_policy": sector_policy,
        "sizing_policy": sizing_policy,
        "sector_concentration": concentration_policy,
    }


def top_rows(mapping: dict[str, dict[str, Any]], min_trades: int = 50, limit: int = 15) -> list[dict[str, Any]]:
    rows = []
    for key, item in mapping.items():
        if int(item.get("trade_count") or 0) < min_trades:
            continue
        rows.append({"key": key, **item})
    return sorted(rows, key=lambda item: float(item.get("return_on_buy_cash") or -999), reverse=True)[:limit]


def top_sizing_rows(mapping: dict[str, dict[str, Any]], min_trades: int = 50, limit: int = 15) -> list[dict[str, Any]]:
    rows = []
    for key, item in mapping.items():
        if int(item.get("trade_count") or 0) < min_trades:
            continue
        rows.append({"key": key, **item})
    return sorted(rows, key=lambda item: float(item.get("weighted_avg_return") or -999), reverse=True)[:limit]


def top_risk_rows(mapping: dict[str, dict[str, Any]], min_trades: int = 50, limit: int = 15) -> list[dict[str, Any]]:
    rows = []
    for key, item in mapping.items():
        if int(item.get("trade_count") or 0) < min_trades:
            continue
        rows.append({"key": key, **item})
    return sorted(
        rows,
        key=lambda item: (
            float(item.get("return_on_buy_cash") or -999),
            -float(item.get("avg_giveback") or 999),
        ),
        reverse=True,
    )[:limit]


def exit_by_regime_top(regime_policy: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for scope in REGIME_SCOPES:
        scoped = {key: value for key, value in regime_policy.items() if key.endswith(f"::{scope}")}
        result[scope] = top_rows(scoped, min_trades=50, limit=8)
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = build_base_trades(args)
    result = matrix(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_changes": False,
            "min_holding_days": args.min_holding_days,
            "exit_hit_priority": "stop_loss_or_trailing_before_take_profit after min_holding_days",
        },
        "inputs": {
            "rankings_dir": repo_path(resolve_path(args.rankings_dir)),
            "features": repo_path(resolve_path(args.features)),
            "market_regime_history": repo_path(resolve_path(args.market_regime_history)),
            "group_map": repo_path(resolve_path(args.group_map)),
            "variant_label": args.variant_label,
            "top_n": args.top_n,
            "shares": args.shares,
        },
        "summary": {
            "base_trade_rows": len(rows),
            "exit_policy_top": top_rows(result["exit_policy"], min_trades=100),
            "rank_policy_top": top_rows(result["rank_policy"], min_trades=100),
            "persistence_policy_top": top_rows(result["persistence_policy"], min_trades=100),
            "regime_policy_top": top_rows(result["regime_policy"], min_trades=50),
            "sector_policy_top": top_rows(result["sector_policy"], min_trades=30),
            "risk_policy_top": top_risk_rows(result["exit_policy"], min_trades=100),
            "sizing_policy_top": top_sizing_rows(result["sizing_policy"], min_trades=100),
            "exit_by_regime_top": exit_by_regime_top(result["regime_policy"]),
            "sector_concentration": result["sector_concentration"],
        },
        "matrix": result,
    }


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


def money(value: Any) -> str:
    return f"{float(value):,.0f}"


def table(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.extend(["", f"## {title}", "", "| Key | Trades | Days | Buy Cash | Net PnL | Return | Win Rate | Avg MAE | Avg Giveback |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in rows:
        lines.append(
            "| {key} | {trades} | {days} | {buy} | {pnl} | {ret} | {win} | {mae} | {giveback} |".format(
                key=row["key"],
                trades=row.get("trade_count"),
                days=row.get("ranking_day_count"),
                buy=money(row.get("total_buy_cash", 0)),
                pnl=money(row.get("total_net_pnl", 0)),
                ret=pct(row.get("return_on_buy_cash")),
                win=pct(row.get("win_rate")),
                mae=pct(row.get("avg_mae")),
                giveback=pct(row.get("avg_giveback")),
            )
        )


def sizing_table(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.extend(["", f"## {title}", "", "| Key | Trades | Days | Weighted Avg Return | Win Rate |", "|---|---:|---:|---:|---:|"])
    for row in rows:
        lines.append(
            "| {key} | {trades} | {days} | {ret} | {win} |".format(
                key=row["key"],
                trades=row.get("trade_count"),
                days=row.get("ranking_day_count"),
                ret=pct(row.get("weighted_avg_return")),
                win=pct(row.get("win_rate")),
            )
        )


def concentration_table(lines: list[str], payload: dict[str, Any]) -> None:
    lines.extend(["", "## Sector Concentration", "", "| Policy | Max Sector Buy Share | Top Buy Sector | Top PnL Sector |", "|---|---:|---|---|"])
    for policy, item in payload["summary"]["sector_concentration"].items():
        top_buy = item.get("top_by_buy") or []
        top_pnl = item.get("top_by_pnl") or []
        if not top_buy:
            continue
        lines.append(
            "| {policy} | {share} | {buy} | {pnl} |".format(
                policy=policy,
                share=pct(item.get("max_sector_buy_share")),
                buy=f"{top_buy[0].get('sector_name')} {pct(top_buy[0].get('buy_share'))}",
                pnl=f"{top_pnl[0].get('sector_name')} {pct(top_pnl[0].get('pnl_share'))}" if top_pnl else "n/a",
            )
        )


def regime_tables(lines: list[str], payload: dict[str, Any]) -> None:
    for regime, rows in payload["summary"]["exit_by_regime_top"].items():
        table(lines, f"Exit By Regime: {regime}", rows)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Fixed Share Hypothesis Matrix",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- variant: {payload['inputs']['variant_label']}",
        f"- base_trade_rows: {payload['summary']['base_trade_rows']}",
        f"- min_holding_days: {payload['contract']['min_holding_days']}",
        f"- model_changes: {payload['contract']['model_changes']}",
        f"- production_changes: {payload['contract']['production_changes']}",
    ]
    table(lines, "Exit Policy Top", payload["summary"]["exit_policy_top"])
    table(lines, "Risk-Aware Policy Top", payload["summary"]["risk_policy_top"])
    sizing_table(lines, "Sizing Policy Top", payload["summary"]["sizing_policy_top"])
    table(lines, "Rank Policy Top", payload["summary"]["rank_policy_top"])
    table(lines, "Persistence Policy Top", payload["summary"]["persistence_policy_top"])
    table(lines, "Regime Policy Top", payload["summary"]["regime_policy_top"])
    regime_tables(lines, payload)
    table(lines, "Sector Policy Top", payload["summary"]["sector_policy_top"])
    concentration_table(lines, payload)
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- 所有停利/停損/移動停損都至少持有 5 個交易日後才允許觸發。",
            "- 這是研究矩陣，不是正式交易規則，不可直接改 production ranking。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "backtest" / f"fixed_share_hypothesis_matrix_{date.today().isoformat()}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
