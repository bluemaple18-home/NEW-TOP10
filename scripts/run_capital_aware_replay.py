#!/usr/bin/env python3
"""有限本金 replay。

這支腳本用來驗證小白真的照推播交易時會遇到的限制：

- 本金有限，不再假設每天 Top10 每檔都能買 100 股且資金無上限。
- 買進預設支援零股，避免高價股在小本金下被整張限制錯誤排除。
- 依盤勢調整總曝險，牛市不過度保守，弱勢盤保留現金。
- 支援 TP15 partial runner 狀態機，測試「先鎖一部分獲利，剩下讓強股跑」。

只讀既有 ranking / features / market regime artifacts，不訓練模型、不改 ranking。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay  # noqa: E402
from scripts import build_candidate_persistence  # noqa: E402
from scripts.build_high_choppy_context_overlay import load_regime_frame, rolling_high_choppy  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SCHEMA_VERSION = "capital-aware-replay.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run capital-aware replay")
    parser.add_argument("--rankings-dir", default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--group-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--group-column", default="sector_name")
    parser.add_argument("--scenario", choices=["fixed40", "tp15_partial_runner"], default="fixed40")
    parser.add_argument("--gross-policy", choices=["fixed", "regime"], default="regime")
    parser.add_argument("--initial-cash", type=float, default=500_000.0)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--horizon", type=int, default=40)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument(
        "--entry-filter",
        choices=["all", "first_day", "streak_2_plus", "improved_or_new", "improved_only", "non_worsening"],
        default="all",
    )
    parser.add_argument(
        "--max-entry-premium-pct",
        type=float,
        default=None,
        help="D+1 開盤價相對 ranking 當日收盤價的最高追價幅度；超過則不進場。",
    )
    parser.add_argument("--max-ranking-files", type=int, default=None)
    parser.add_argument("--buy-lot-size", type=int, default=1)
    parser.add_argument("--sell-lot-size", type=int, default=1)
    parser.add_argument("--max-new-positions-per-day", type=int, default=3)
    parser.add_argument("--max-open-positions", type=int, default=10)
    parser.add_argument("--max-position-pct", type=float, default=0.10)
    parser.add_argument("--max-group-pct", type=float, default=0.30)
    parser.add_argument("--fixed-gross", type=float, default=0.65)
    parser.add_argument("--big-bull-gross", type=float, default=0.90)
    parser.add_argument("--risk-on-gross", type=float, default=0.80)
    parser.add_argument("--high-choppy-gross", type=float, default=0.70)
    parser.add_argument("--neutral-gross", type=float, default=0.60)
    parser.add_argument("--risk-off-gross", type=float, default=0.30)
    parser.add_argument("--tp-pct", type=float, default=0.15)
    parser.add_argument("--stop-loss-source", choices=["pct", "ranking", "ranking_or_pct"], default="pct")
    parser.add_argument("--stop-trigger", choices=["low", "close"], default="low")
    parser.add_argument("--stop-loss-pct", type=float, default=None)
    parser.add_argument("--stop-sell-pct", type=float, default=1.0)
    parser.add_argument("--min-stop-holding-days", type=int, default=1)
    parser.add_argument("--partial-sell-pct", type=float, default=0.40)
    parser.add_argument("--runner-drawdown-pct", type=float, default=0.10)
    parser.add_argument(
        "--drawdown-state-enabled",
        action="store_true",
        help="即使尚未部分停利，也啟用 runner drawdown / MA20 / TopN / risk-off 出場狀態機。",
    )
    parser.add_argument("--min-holding-days", type=int, default=5)
    parser.add_argument("--top-valid-n", type=int, default=20)
    parser.add_argument("--top-valid-miss-days", type=int, default=3)
    parser.add_argument("--below-ma20-days", type=int, default=2)
    parser.add_argument("--cooldown-days", type=int, default=3)
    parser.add_argument("--max-reentry-premium-pct", type=float, default=0.08)
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


def load_price_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"features 不存在：{path}")
    columns = ["stock_id", "open", "high", "low", "close", "ma20"]
    try:
        frame = pd.read_parquet(path, columns=[*columns, "trade_date"])
    except Exception as exc:
        if "trade_date" not in str(exc):
            raise
        frame = pd.read_parquet(path, columns=[*columns, "date"])
        frame = frame.rename(columns={"date": "trade_date"})
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame.sort_values(["stock_id", "trade_date"]).reset_index(drop=True)


def price_lookup(price_frame: pd.DataFrame) -> dict[tuple[str, date], dict[str, float | None]]:
    lookup: dict[tuple[str, date], dict[str, float | None]] = {}
    for row in price_frame.itertuples(index=False):
        lookup[(str(row.stock_id).zfill(4), row.trade_date)] = {
            "open": none_if_nan(row.open),
            "high": none_if_nan(row.high),
            "low": none_if_nan(row.low),
            "close": none_if_nan(row.close),
            "ma20": none_if_nan(row.ma20),
        }
    return lookup


def none_if_nan(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def load_group_map(path: Path, group_column: str) -> dict[str, str]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype={"stock_id": str})
    if "stock_id" not in frame.columns or group_column not in frame.columns:
        return {}
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    result: dict[str, str] = {}
    for stock_id, group in frame[["stock_id", group_column]].dropna().itertuples(index=False, name=None):
        text = str(group).strip()
        if text:
            result[str(stock_id).zfill(4)] = text
    return result


def load_regimes(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    regimes: dict[str, dict[str, Any]] = {}
    for row in frame.itertuples(index=False):
        date_text = str(getattr(row, "trade_date_text"))
        label = str(getattr(row, "regime_label", "UNKNOWN"))
        regimes[date_text] = {
            "regime_label": label,
            "big_bull": bool(getattr(row, "BIG_BULL", False)),
            "high_choppy_context": bool(getattr(row, "HIGH_CHOPPY_CONTEXT", False)),
        }
    return regimes


def gross_limit_for_date(args: argparse.Namespace, regimes: dict[str, dict[str, Any]], trade_date: date) -> tuple[float, str]:
    if args.gross_policy == "fixed":
        return float(args.fixed_gross), "fixed"

    info = regimes.get(trade_date.isoformat(), {})
    label = str(info.get("regime_label") or "UNKNOWN")
    if bool(info.get("high_choppy_context")):
        return float(args.high_choppy_gross), "HIGH_CHOPPY_CONTEXT"
    if bool(info.get("big_bull")):
        return float(args.big_bull_gross), "BIG_BULL"
    if label in {"BROAD_RISK_ON", "NARROW_LEADER", "EARLY_REVERSAL"}:
        return float(args.risk_on_gross), label
    if label in {"RISK_OFF", "PANIC_SELLING"}:
        return float(args.risk_off_gross), label
    return float(args.neutral_gross), label


def ranking_item_weights(items: list[dict[str, Any]], gross_limit: float, max_position_pct: float) -> dict[str, float]:
    suggested = {
        item["stock_id"]: float(item.get("suggested_weight") or 0)
        for item in items
        if float(item.get("suggested_weight") or 0) > 0
    }
    if suggested:
        total = sum(suggested.values())
        return {stock_id: min(max_position_pct, value / total * gross_limit) for stock_id, value in suggested.items()}

    scores = {
        item["stock_id"]: max(0.0, float(item.get("risk_adjusted_score") or 0))
        for item in items
    }
    total = sum(scores.values()) or float(len(items) or 1)
    return {
        item["stock_id"]: min(max_position_pct, (scores.get(item["stock_id"], 0.0) or 1.0) / total * gross_limit)
        for item in items
    }


def build_top_membership(rankings_dir: Path, max_files: int | None, top_n: int) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in run_backtest_replay.ranking_files(rankings_dir, max_files):
        date_text = run_backtest_replay.ranking_date(path)
        result[date_text] = {item["stock_id"] for item in run_backtest_replay.read_ranking(path, top_n)}
    return result


def build_entry_plans(args: argparse.Namespace, trade_dates: list[date], group_map: dict[str, str]) -> tuple[dict[date, list[dict[str, Any]]], list[dict[str, Any]]]:
    rankings_dir = resolve_path(args.rankings_dir)
    files = run_backtest_replay.ranking_files(rankings_dir, args.max_ranking_files)
    plans_by_entry: dict[date, list[dict[str, Any]]] = {}
    skipped: list[dict[str, Any]] = []
    for path in files:
        ranking_date = run_backtest_replay.ranking_date(path)
        entry_date = run_backtest_replay.next_market_trade_date(trade_dates, ranking_date, args.entry_delay_trade_days)
        if entry_date is None:
            skipped.append({"ranking_date": ranking_date, "reason": "missing_entry_date"})
            continue
        holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, args.horizon)
        if holding_dates is None:
            skipped.append({"ranking_date": ranking_date, "reason": "insufficient_future_bars"})
            continue
        items = run_backtest_replay.read_ranking(path, args.top_n)
        persistence_by_stock = persistence_for_ranking(path, rankings_dir, args.top_n) if args.entry_filter != "all" else {}
        for item in items:
            item = dict(item)
            persistence = persistence_by_stock.get(item["stock_id"], {})
            item["consecutive_ranked_days"] = persistence.get("consecutive_ranked_days")
            item["ranked_history_count"] = persistence.get("ranked_history_count")
            item["rank_delta"] = persistence.get("rank_delta")
            if not entry_filter_passes(item, args.entry_filter):
                skipped.append(
                    {
                        "ranking_date": ranking_date,
                        "stock_id": item["stock_id"],
                        "reason": f"entry_filter_{args.entry_filter}",
                        "consecutive_ranked_days": item.get("consecutive_ranked_days"),
                        "rank_delta": item.get("rank_delta"),
                    }
                )
                continue
            item["ranking_date"] = ranking_date
            item["entry_date"] = entry_date
            item["scheduled_exit_date"] = holding_dates[-1]
            item["group"] = group_map.get(item["stock_id"], item.get("sector_name") or item.get("industry_name") or "未分類")
            plans_by_entry.setdefault(entry_date, []).append(item)
    return plans_by_entry, skipped


def persistence_for_ranking(path: Path, rankings_dir: Path, top_n: int) -> dict[str, dict[str, Any]]:
    payload = build_candidate_persistence.build_payload(target_ranking=path, rankings_dir=rankings_dir, limit=top_n)
    return {str(item.get("stock_id", "")).zfill(4): item for item in payload.get("items", [])}


def entry_filter_passes(item: dict[str, Any], entry_filter: str) -> bool:
    if entry_filter == "all":
        return True
    consecutive = int(item.get("consecutive_ranked_days") or 0)
    ranked_history_count = int(item.get("ranked_history_count") or 0)
    rank_delta = item.get("rank_delta")
    if entry_filter == "first_day":
        return consecutive == 1 and ranked_history_count == 1
    if entry_filter == "streak_2_plus":
        return consecutive >= 2
    if entry_filter == "improved_or_new":
        return rank_delta is None or float(rank_delta) > 0
    if entry_filter == "improved_only":
        return rank_delta is not None and float(rank_delta) > 0
    if entry_filter == "non_worsening":
        return rank_delta is None or float(rank_delta) >= 0
    raise ValueError(f"unknown entry_filter: {entry_filter}")


def position_market_value(position: dict[str, Any], bar: dict[str, float | None], field: str) -> float:
    price = bar.get(field)
    if price is None:
        price = position.get("last_mark_price")
    if price is None:
        return 0.0
    return float(position["shares"]) * float(price)


def portfolio_value(positions: list[dict[str, Any]], prices: dict[tuple[str, date], dict[str, float | None]], trade_date: date, field: str) -> float:
    return sum(position_market_value(position, prices.get((position["stock_id"], trade_date), {}), field) for position in positions)


def group_exposure_values(positions: list[dict[str, Any]], prices: dict[tuple[str, date], dict[str, float | None]], trade_date: date, field: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for position in positions:
        value = position_market_value(position, prices.get((position["stock_id"], trade_date), {}), field)
        if value <= 0:
            continue
        group = str(position.get("group") or "未分類")
        values[group] = values.get(group, 0.0) + value
    return values


def buy_cost(notional: float, fee_rate: float, slippage_rate: float) -> float:
    return notional * (1 + fee_rate + slippage_rate)


def sell_proceeds(notional: float, fee_rate: float, tax_rate: float, slippage_rate: float) -> float:
    return notional * (1 - fee_rate - tax_rate - slippage_rate)


def close_position(
    position: dict[str, Any],
    trade_date: date,
    exit_price: float,
    shares: int,
    reason: str,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], float]:
    shares = int(min(shares, int(position["shares"])))
    notional = shares * exit_price
    proceeds = sell_proceeds(notional, args.fee_rate, args.tax_rate, args.slippage_rate)
    entry_cost_per_share = float(position["entry_cash_cost_per_share"])
    allocated_entry_cost = entry_cost_per_share * shares
    net_return = proceeds / allocated_entry_cost - 1 if allocated_entry_cost else 0.0
    trade = {
        "stock_id": position["stock_id"],
        "stock_name": position.get("stock_name"),
        "group": position.get("group"),
        "ranking_date": position["ranking_date"],
        "entry_date": position["entry_date"].isoformat(),
        "exit_date": trade_date.isoformat(),
        "exit_reason": reason,
        "entry_price": round(float(position["entry_price"]), 4),
        "exit_price": round(float(exit_price), 4),
        "shares": shares,
        "remaining_after_exit": int(position["shares"] - shares),
        "net_return": round(net_return, 6),
        "pnl": round(proceeds - allocated_entry_cost, 2),
        "partial_done_before_exit": bool(position.get("partial_done")),
    }
    position["shares"] = int(position["shares"] - shares)
    position["entry_cash_cost"] = float(position["entry_cash_cost"]) - allocated_entry_cost
    position["entry_notional"] = float(position["entry_notional"]) - (float(position["entry_notional"]) / max(1, int(position["initial_shares"]))) * shares
    return trade, proceeds


def round_down_lot(shares: float, lot_size: int) -> int:
    lot = max(1, int(lot_size))
    return int(math.floor(max(0.0, shares) / lot) * lot)


def stop_loss_price_for_plan(plan: dict[str, Any], open_price: float, args: argparse.Namespace) -> float | None:
    ranking_stop = plan.get("stop_loss")
    if args.stop_loss_source in {"ranking", "ranking_or_pct"} and ranking_stop is not None:
        try:
            parsed = float(ranking_stop)
        except (TypeError, ValueError):
            parsed = 0.0
        if parsed > 0:
            return parsed
    if args.stop_loss_source in {"pct", "ranking_or_pct"} and args.stop_loss_pct is not None:
        return float(open_price) * (1 - float(args.stop_loss_pct))
    return None


def should_runner_exit(
    position: dict[str, Any],
    trade_date: date,
    bar: dict[str, float | None],
    args: argparse.Namespace,
    regime_label: str,
    top_membership: dict[str, set[str]],
) -> tuple[str | None, float | None]:
    low = bar.get("low")
    close = bar.get("close")
    ma20 = bar.get("ma20")
    if low is None or close is None:
        return None, None

    high_water = float(position.get("high_water") or position["entry_price"])
    runner_stop = high_water * (1 - args.runner_drawdown_pct)
    if float(low) <= runner_stop:
        return "runner_drawdown", runner_stop

    if ma20 is not None and float(close) < float(ma20):
        position["below_ma20_count"] = int(position.get("below_ma20_count") or 0) + 1
    else:
        position["below_ma20_count"] = 0
    if int(position.get("below_ma20_count") or 0) >= args.below_ma20_days:
        return "below_ma20", float(close)

    todays_top = top_membership.get(trade_date.isoformat())
    if todays_top is not None:
        if position["stock_id"] in todays_top:
            position["top_miss_count"] = 0
        else:
            position["top_miss_count"] = int(position.get("top_miss_count") or 0) + 1
    if int(position.get("top_miss_count") or 0) >= args.top_valid_miss_days:
        return "top20_miss", float(close)

    if regime_label in {"RISK_OFF", "PANIC_SELLING"}:
        return "risk_off", float(close)

    if position["scheduled_exit_date"] == trade_date:
        return "scheduled_horizon", float(close)
    return None, None


def run_replay(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    rankings_dir = resolve_path(args.rankings_dir)
    price_frame = load_price_frame(features_path)
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    prices = price_lookup(price_frame)
    regimes = load_regimes(resolve_path(args.market_regime_history))
    group_map = load_group_map(resolve_path(args.group_map), args.group_column)
    plans_by_entry, skipped = build_entry_plans(args, trade_dates, group_map)
    top_membership = build_top_membership(rankings_dir, args.max_ranking_files, args.top_valid_n)

    if not plans_by_entry:
        raise RuntimeError("沒有可回測的 entry plans")

    cash = float(args.initial_cash)
    equity = float(args.initial_cash)
    positions: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    last_exit_by_stock: dict[str, dict[str, Any]] = {}
    first_entry = min(plans_by_entry)
    last_exit = max(plan["scheduled_exit_date"] for plans in plans_by_entry.values() for plan in plans)
    sim_dates = [trade_date for trade_date in trade_dates if first_entry <= trade_date <= last_exit]
    date_index = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    previous_equity = equity

    for trade_date in sim_dates:
        gross_limit, gross_label = gross_limit_for_date(args, regimes, trade_date)
        open_exposure = portfolio_value(positions, prices, trade_date, "open")
        open_group_values = group_exposure_values(positions, prices, trade_date, "open")
        equity_at_open = cash + open_exposure
        open_stock_ids = {position["stock_id"] for position in positions}

        entry_count = 0
        blocked_cash = 0
        blocked_lot = 0
        blocked_duplicate = 0
        entry_plans = plans_by_entry.get(trade_date, [])
        weights = ranking_item_weights(entry_plans, gross_limit, args.max_position_pct) if entry_plans else {}
        for plan in entry_plans:
            if entry_count >= args.max_new_positions_per_day or len(positions) >= args.max_open_positions:
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "position_count_limit"})
                continue
            if plan["stock_id"] in open_stock_ids:
                blocked_duplicate += 1
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "already_holding"})
                continue
            last_exit = last_exit_by_stock.get(plan["stock_id"])
            if last_exit is not None:
                current_i = date_index.get(trade_date, 0)
                exit_i = int(last_exit.get("date_index") or -999)
                if current_i - exit_i <= args.cooldown_days:
                    skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "cooldown"})
                    continue
                entry_bar = prices.get((plan["stock_id"], trade_date), {})
                open_price = entry_bar.get("open")
                if open_price is not None and float(open_price) > float(last_exit["exit_price"]) * (1 + args.max_reentry_premium_pct):
                    skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "reentry_price_too_high"})
                    continue

            bar = prices.get((plan["stock_id"], trade_date), {})
            open_price = bar.get("open")
            if open_price is None:
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "missing_entry_open"})
                continue
            if args.max_entry_premium_pct is not None:
                ranking_close = plan.get("close")
                if ranking_close is not None and float(ranking_close) > 0:
                    max_entry_price = float(ranking_close) * (1 + float(args.max_entry_premium_pct))
                    if float(open_price) > max_entry_price:
                        skipped.append(
                            {
                                "ranking_date": plan["ranking_date"],
                                "stock_id": plan["stock_id"],
                                "reason": "entry_price_too_high",
                                "ranking_close": float(ranking_close),
                                "entry_open": float(open_price),
                                "max_entry_price": float(max_entry_price),
                                "max_entry_premium_pct": float(args.max_entry_premium_pct),
                            }
                        )
                        continue
            planned_stop_loss = stop_loss_price_for_plan(plan, float(open_price), args)
            if planned_stop_loss is not None and args.stop_loss_source in {"ranking", "ranking_or_pct"} and float(open_price) <= float(planned_stop_loss):
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "entry_already_below_stop_loss"})
                continue

            group = str(plan.get("group") or "未分類")
            current_gross_headroom = max(0.0, equity_at_open * gross_limit - open_exposure)
            current_group_headroom = max(0.0, equity_at_open * args.max_group_pct - open_group_values.get(group, 0.0))
            desired_notional = min(equity_at_open * weights.get(plan["stock_id"], 0.0), current_gross_headroom, current_group_headroom)
            max_affordable_notional = cash / (1 + args.fee_rate + args.slippage_rate)
            desired_notional = min(desired_notional, max_affordable_notional)
            shares = round_down_lot(desired_notional / float(open_price), args.buy_lot_size)
            if shares <= 0:
                blocked_lot += 1
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "below_buy_lot_or_cash"})
                continue
            notional = shares * float(open_price)
            cost = buy_cost(notional, args.fee_rate, args.slippage_rate)
            if cost > cash + 1e-6:
                blocked_cash += 1
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "insufficient_cash"})
                continue

            cash -= cost
            position = {
                **plan,
                "shares": int(shares),
                "initial_shares": int(shares),
                "entry_price": float(open_price),
                "stop_loss_price": planned_stop_loss,
                "entry_notional": float(notional),
                "entry_cash_cost": float(cost),
                "entry_cash_cost_per_share": float(cost) / float(shares),
                "high_water": float(open_price),
                "last_mark_price": float(open_price),
                "holding_days": 0,
                "partial_done": False,
                "below_ma20_count": 0,
                "top_miss_count": 0,
            }
            positions.append(position)
            open_stock_ids.add(plan["stock_id"])
            open_exposure += notional
            open_group_values[group] = open_group_values.get(group, 0.0) + notional
            entry_count += 1

        exits_today = 0
        partial_exits_today = 0
        remaining_positions: list[dict[str, Any]] = []
        for position in positions:
            bar = prices.get((position["stock_id"], trade_date), {})
            high = bar.get("high")
            close = bar.get("close")
            if high is not None:
                position["high_water"] = max(float(position.get("high_water") or position["entry_price"]), float(high))
            if close is not None:
                position["last_mark_price"] = float(close)
            position["holding_days"] = int(position.get("holding_days") or 0) + 1

            if close is None:
                remaining_positions.append(position)
                continue

            exit_reason: str | None = None
            exit_price: float | None = None
            sell_shares = int(position["shares"])
            low = bar.get("low")
            open_price = bar.get("open")

            if position.get("stop_loss_price") is not None and int(position.get("holding_days") or 0) >= int(args.min_stop_holding_days):
                stop_price = float(position.get("stop_loss_price") or 0)
                trigger_price = low if args.stop_trigger == "low" else close
                if stop_price > 0 and trigger_price is not None and float(trigger_price) <= stop_price:
                    if args.stop_trigger == "close":
                        gap_exit_price = float(close)
                    else:
                        gap_exit_price = float(open_price) if open_price is not None and float(open_price) < stop_price else stop_price
                    stop_sell_ratio = max(0.0, min(1.0, float(args.stop_sell_pct)))
                    sell_shares = int(position["shares"]) if stop_sell_ratio >= 1 else max(
                        1,
                        round_down_lot(int(position["shares"]) * stop_sell_ratio, args.sell_lot_size),
                    )
                    trade, proceeds = close_position(position, trade_date, gap_exit_price, sell_shares, "stop_loss", args)
                    cash += proceeds
                    trades.append(trade)
                    exits_today += 1
                    if int(position["shares"]) <= 0:
                        last_exit_by_stock[position["stock_id"]] = {"date_index": date_index.get(trade_date, 0), "exit_price": gap_exit_price}
                        continue

            if args.scenario == "tp15_partial_runner":
                if (
                    not bool(position.get("partial_done"))
                    and int(position["holding_days"]) >= args.min_holding_days
                    and high is not None
                    and float(high) >= float(position["entry_price"]) * (1 + args.tp_pct)
                ):
                    target_price = float(position["entry_price"]) * (1 + args.tp_pct)
                    raw_partial = int(position["initial_shares"]) * float(args.partial_sell_pct)
                    sell_shares = max(1, round_down_lot(raw_partial, args.sell_lot_size))
                    sell_shares = min(sell_shares, int(position["shares"]))
                    trade, proceeds = close_position(position, trade_date, target_price, sell_shares, "partial_take_profit", args)
                    cash += proceeds
                    trades.append(trade)
                    exits_today += 1
                    partial_exits_today += 1
                    position["partial_done"] = True
                    if int(position["shares"]) <= 0:
                        last_exit_by_stock[position["stock_id"]] = {"date_index": date_index.get(trade_date, 0), "exit_price": target_price}
                        continue

                regime_label = gross_label
                if bool(position.get("partial_done")) or (
                    args.drawdown_state_enabled and int(position["holding_days"]) >= args.min_holding_days
                ):
                    exit_reason, exit_price = should_runner_exit(
                        position=position,
                        trade_date=trade_date,
                        bar=bar,
                        args=args,
                        regime_label=regime_label,
                        top_membership=top_membership,
                    )
            else:
                if args.drawdown_state_enabled and int(position["holding_days"]) >= args.min_holding_days:
                    exit_reason, exit_price = should_runner_exit(
                        position=position,
                        trade_date=trade_date,
                        bar=bar,
                        args=args,
                        regime_label=gross_label,
                        top_membership=top_membership,
                    )
                elif position["scheduled_exit_date"] == trade_date:
                    exit_reason = "scheduled_horizon"
                    exit_price = float(close)

            if exit_reason and exit_price is not None:
                trade, proceeds = close_position(position, trade_date, float(exit_price), int(position["shares"]), exit_reason, args)
                cash += proceeds
                trades.append(trade)
                exits_today += 1
                last_exit_by_stock[position["stock_id"]] = {"date_index": date_index.get(trade_date, 0), "exit_price": float(exit_price)}
                continue

            if int(position["shares"]) > 0:
                remaining_positions.append(position)
        positions = remaining_positions

        close_exposure = portfolio_value(positions, prices, trade_date, "close")
        group_values = group_exposure_values(positions, prices, trade_date, "close")
        equity = cash + close_exposure
        daily_return = equity / previous_equity - 1 if previous_equity else 0.0
        previous_equity = equity
        daily.append(
            {
                "date": trade_date.isoformat(),
                "equity": round(equity, 2),
                "cash": round(cash, 2),
                "daily_return": round(daily_return, 6),
                "gross_exposure": round(close_exposure / equity, 6) if equity else 0.0,
                "cash_ratio": round(cash / equity, 6) if equity else 0.0,
                "gross_limit": round(float(gross_limit), 6),
                "gross_label": gross_label,
                "positions": len(positions),
                "entries": entry_count,
                "exits": exits_today,
                "partial_exits": partial_exits_today,
                "blocked_cash": blocked_cash,
                "blocked_lot": blocked_lot,
                "blocked_duplicate": blocked_duplicate,
                "group_exposures": {group: round(value / equity, 6) for group, value in sorted(group_values.items())} if equity else {},
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "changes_model": False,
            "changes_ranking_score": False,
            "finite_capital": True,
            "buy_lot_size": args.buy_lot_size,
            "sell_lot_size": args.sell_lot_size,
            "entry_timing": f"D+{args.entry_delay_trade_days} open",
            "partial_runner_state_machine": args.scenario == "tp15_partial_runner",
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "market_regime_history": repo_path(resolve_path(args.market_regime_history)),
            "scenario": args.scenario,
            "gross_policy": args.gross_policy,
            "entry_filter": args.entry_filter,
            "max_entry_premium_pct": args.max_entry_premium_pct,
            "initial_cash": args.initial_cash,
            "top_n": args.top_n,
            "horizon": args.horizon,
            "max_position_pct": args.max_position_pct,
            "max_group_pct": args.max_group_pct,
            "max_new_positions_per_day": args.max_new_positions_per_day,
            "max_open_positions": args.max_open_positions,
            "regime_gross": {
                "big_bull": args.big_bull_gross,
                "risk_on": args.risk_on_gross,
                "high_choppy": args.high_choppy_gross,
                "neutral": args.neutral_gross,
                "risk_off": args.risk_off_gross,
            },
            "tp_partial_runner": {
                "tp_pct": args.tp_pct,
                "stop_loss_source": args.stop_loss_source,
                "stop_trigger": args.stop_trigger,
                "stop_loss_pct": args.stop_loss_pct,
                "stop_sell_pct": args.stop_sell_pct,
                "min_stop_holding_days": args.min_stop_holding_days,
                "partial_sell_pct": args.partial_sell_pct,
                "runner_drawdown_pct": args.runner_drawdown_pct,
                "drawdown_state_enabled": args.drawdown_state_enabled,
                "min_holding_days": args.min_holding_days,
                "top_valid_n": args.top_valid_n,
                "top_valid_miss_days": args.top_valid_miss_days,
                "below_ma20_days": args.below_ma20_days,
                "cooldown_days": args.cooldown_days,
                "max_reentry_premium_pct": args.max_reentry_premium_pct,
            },
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
            },
        },
        "summary": summarize(args.initial_cash, daily, trades, skipped),
        "daily": daily,
        "trades": trades,
        "skipped": skipped,
    }


def summarize(initial_cash: float, daily: list[dict[str, Any]], trades: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    if not daily:
        return {"final_equity": initial_cash, "total_return": 0.0, "trade_count": 0, "skipped_count": len(skipped)}
    equity_values = [float(item["equity"]) for item in daily]
    max_equity = equity_values[0]
    max_drawdown = 0.0
    for value in equity_values:
        max_equity = max(max_equity, value)
        max_drawdown = min(max_drawdown, value / max_equity - 1)
    trade_returns = [float(item["net_return"]) for item in trades]
    pnl_values = [float(item["pnl"]) for item in trades]
    exit_counts = Counter(str(item["exit_reason"]) for item in trades)
    skip_counts = Counter(str(item.get("reason")) for item in skipped)
    return {
        "initial_cash": round(float(initial_cash), 2),
        "final_equity": round(equity_values[-1], 2),
        "total_return": round(equity_values[-1] / float(initial_cash) - 1, 6),
        "max_drawdown": round(max_drawdown, 6),
        "daily_count": len(daily),
        "trade_count": len(trades),
        "win_rate": round(sum(value > 0 for value in trade_returns) / len(trade_returns), 6) if trade_returns else None,
        "avg_trade_return": round(sum(trade_returns) / len(trade_returns), 6) if trade_returns else None,
        "total_realized_pnl": round(sum(pnl_values), 2),
        "max_gross_exposure": round(max(float(item["gross_exposure"]) for item in daily), 6),
        "avg_gross_exposure": round(sum(float(item["gross_exposure"]) for item in daily) / len(daily), 6),
        "min_cash_ratio": round(min(float(item["cash_ratio"]) for item in daily), 6),
        "avg_cash_ratio": round(sum(float(item["cash_ratio"]) for item in daily) / len(daily), 6),
        "partial_take_profit_count": int(exit_counts.get("partial_take_profit", 0)),
        "exit_reason_counts": dict(sorted(exit_counts.items())),
        "skipped_count": len(skipped),
        "skip_reason_counts": dict(sorted(skip_counts.items())),
        "buy_lot_block_count": int(skip_counts.get("below_buy_lot_or_cash", 0)),
        "cash_block_count": int(skip_counts.get("insufficient_cash", 0)),
        "cooldown_block_count": int(skip_counts.get("cooldown", 0)),
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    inputs = payload["inputs"]
    return "\n".join(
        [
            "# Capital-Aware Replay",
            "",
            f"- scenario: `{inputs.get('scenario')}`",
            f"- gross_policy: `{inputs.get('gross_policy')}`",
            f"- initial_cash: `{summary.get('initial_cash')}`",
            f"- final_equity: `{summary.get('final_equity')}`",
            f"- total_return: `{pct(summary.get('total_return'))}`",
            f"- max_drawdown: `{pct(summary.get('max_drawdown'))}`",
            f"- max_gross_exposure: `{pct(summary.get('max_gross_exposure'))}`",
            f"- min_cash_ratio: `{pct(summary.get('min_cash_ratio'))}`",
            f"- trade_count: `{summary.get('trade_count')}`",
            f"- partial_take_profit_count: `{summary.get('partial_take_profit_count')}`",
            f"- skipped_count: `{summary.get('skipped_count')}`",
            "",
            "## Exit Counts",
            "",
            json.dumps(summary.get("exit_reason_counts", {}), ensure_ascii=False, indent=2),
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = run_replay(args)
    today = datetime.now().strftime("%Y-%m-%d")
    label = f"{args.scenario}_{args.gross_policy}"
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "backtest" / f"capital_aware_replay_{label}_{today}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": repo_path(output),
                "scenario": args.scenario,
                "gross_policy": args.gross_policy,
                "total_return": payload["summary"].get("total_return"),
                "max_drawdown": payload["summary"].get("max_drawdown"),
                "final_equity": payload["summary"].get("final_equity"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
