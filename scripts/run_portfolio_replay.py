#!/usr/bin/env python3
"""重疊持倉 portfolio replay。

此腳本只讀 ranking artifacts 與 features parquet，不訓練模型、不重跑 ranking。
規則：D 日 ranking、D+1 開盤進場、固定 horizon 收盤出場；新增部位受現金
與總曝險上限限制。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay  # noqa: E402


SCHEMA_VERSION = "overlap-portfolio-replay.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run overlapping portfolio replay")
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-ranking-files", type=int, default=None)
    parser.add_argument("--initial-cash", type=float, default=1.0)
    parser.add_argument("--max-gross-exposure", type=float, default=0.65)
    parser.add_argument("--max-position-weight", type=float, default=0.2)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def price_lookup(price_frame: pd.DataFrame) -> dict[tuple[str, Any], dict[str, float]]:
    lookup: dict[tuple[str, Any], dict[str, float]] = {}
    for row in price_frame.itertuples(index=False):
        lookup[(str(row.stock_id).zfill(4), row.trade_date)] = {
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
        }
    return lookup


def build_entry_plans(args: argparse.Namespace, price_frame: pd.DataFrame, trade_dates: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rankings_dir = resolve_path(args.rankings_dir)
    files = run_backtest_replay.ranking_files(rankings_dir, args.max_ranking_files)
    price_index = run_backtest_replay.build_price_index(price_frame)
    plans: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for ranking_path in files:
        ranking_date = run_backtest_replay.ranking_date(ranking_path)
        entry_date = run_backtest_replay.next_market_trade_date(trade_dates, ranking_date)
        if entry_date is None:
            skipped.append({"ranking_date": ranking_date, "reason": "missing_next_market_trade_day"})
            continue
        holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, args.horizon)
        if holding_dates is None:
            skipped.append({"ranking_date": ranking_date, "reason": "insufficient_future_market_bars"})
            continue

        items = run_backtest_replay.read_ranking(ranking_path, args.top_n)
        weights = run_backtest_replay.portfolio_weights(
            items,
            default_gross_exposure=args.max_gross_exposure,
            max_position_weight=args.max_position_weight,
        )
        for item in items:
            stock_prices = price_index.get(item["stock_id"])
            if stock_prices is None:
                skipped.append({"ranking_date": ranking_date, "stock_id": item["stock_id"], "reason": "missing_price_history"})
                continue
            holding = run_backtest_replay.stock_holding_bars(stock_prices, holding_dates)
            if holding is None:
                skipped.append(
                    {
                        "ranking_date": ranking_date,
                        "stock_id": item["stock_id"],
                        "reason": "missing_holding_bars",
                        "entry_date": entry_date.isoformat(),
                        "exit_date": holding_dates[-1].isoformat(),
                    }
                )
                continue
            if run_backtest_replay.has_missing_ohlc(holding):
                skipped.append(
                    {
                        "ranking_date": ranking_date,
                        "stock_id": item["stock_id"],
                        "reason": "missing_ohlc_bar",
                        "entry_date": entry_date.isoformat(),
                        "exit_date": holding_dates[-1].isoformat(),
                    }
                )
                continue
            target_weight = weights.get(item["stock_id"], 0.0)
            if target_weight <= 0:
                continue
            plans.append(
                {
                    "ranking_date": ranking_date,
                    "entry_date": entry_date,
                    "exit_date": holding_dates[-1],
                    "stock_id": item["stock_id"],
                    "stock_name": item.get("stock_name"),
                    "rank": item["rank"],
                    "target_weight": target_weight,
                }
            )
    return plans, skipped


def market_value(positions: list[dict[str, Any]], prices: dict[tuple[str, Any], dict[str, float]], trade_date: Any, field: str) -> float:
    value = 0.0
    for position in positions:
        price = prices.get((position["stock_id"], trade_date), {}).get(field)
        if price is not None:
            value += float(position["shares"]) * float(price)
    return value


def deleverage_to_gross_cap(
    positions: list[dict[str, Any]],
    prices: dict[tuple[str, Any], dict[str, float]],
    trade_date: Any,
    cash: float,
    max_gross_exposure: float,
    fee_rate: float,
    tax_rate: float,
    slippage_rate: float,
) -> tuple[list[dict[str, Any]], float, dict[str, Any]]:
    close_exposure = market_value(positions, prices, trade_date, "close")
    equity_before = cash + close_exposure
    if equity_before <= 0 or close_exposure <= equity_before * max_gross_exposure:
        return positions, cash, {"deleveraged_notional": 0.0, "deleverage_count": 0}

    sell_cost_rate = fee_rate + tax_rate + slippage_rate
    denominator = max(1e-12, 1 - max_gross_exposure * sell_cost_rate)
    sell_notional = min(close_exposure, (close_exposure - equity_before * max_gross_exposure) / denominator)
    if sell_notional <= 0:
        return positions, cash, {"deleveraged_notional": 0.0, "deleverage_count": 0}

    sell_ratio = sell_notional / close_exposure
    remaining: list[dict[str, Any]] = []
    deleverage_count = 0
    realized_notional = 0.0
    for position in positions:
        close_price = prices.get((position["stock_id"], trade_date), {}).get("close")
        if close_price is None or pd.isna(close_price):
            remaining.append(position)
            continue
        position_notional = float(position["shares"]) * float(close_price)
        position_sell_notional = position_notional * sell_ratio
        if position_sell_notional <= 0:
            remaining.append(position)
            continue
        realized_notional += position_sell_notional
        cash += position_sell_notional * (1 - sell_cost_rate)
        keep_ratio = max(0.0, 1 - sell_ratio)
        adjusted = {
            **position,
            "shares": float(position["shares"]) * keep_ratio,
            "entry_notional": float(position["entry_notional"]) * keep_ratio,
            "entry_cash_cost": float(position["entry_cash_cost"]) * keep_ratio,
        }
        if adjusted["shares"] > 1e-12 and adjusted["entry_cash_cost"] > 1e-12:
            remaining.append(adjusted)
        deleverage_count += 1

    return (
        remaining,
        cash,
        {
            "deleveraged_notional": round(realized_notional, 6),
            "deleverage_count": deleverage_count,
        },
    )


def run_portfolio(args: argparse.Namespace) -> dict[str, Any]:
    price_frame = run_backtest_replay.load_price_frame(resolve_path(args.features))
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    prices = price_lookup(price_frame)
    plans, skipped = build_entry_plans(args, price_frame, trade_dates)
    plans_by_entry: dict[Any, list[dict[str, Any]]] = {}
    for plan in plans:
        plans_by_entry.setdefault(plan["entry_date"], []).append(plan)

    cash = float(args.initial_cash)
    equity = float(args.initial_cash)
    positions: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    first_entry = min(plans_by_entry) if plans_by_entry else None
    last_exit = max((plan["exit_date"] for plan in plans), default=None)
    sim_dates = [date for date in trade_dates if first_entry is not None and last_exit is not None and first_entry <= date <= last_exit]
    previous_equity = equity

    for trade_date in sim_dates:
        open_exposure = market_value(positions, prices, trade_date, "open")
        gross_headroom = max(0.0, equity * args.max_gross_exposure - open_exposure)
        cash_headroom = max(0.0, cash)
        entry_plans = plans_by_entry.get(trade_date, [])
        desired_entries = []
        for plan in entry_plans:
            open_price = prices.get((plan["stock_id"], trade_date), {}).get("open")
            if open_price is None or pd.isna(open_price):
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "missing_entry_open"})
                continue
            desired_notional = equity * float(plan["target_weight"])
            desired_entries.append((plan, float(open_price), desired_notional))
        total_desired = sum(item[2] for item in desired_entries)
        scale = min(1.0, gross_headroom / total_desired, cash_headroom / (total_desired * (1 + args.fee_rate + args.slippage_rate))) if total_desired > 0 else 0.0
        entry_count = 0
        for plan, open_price, desired_notional in desired_entries:
            notional = desired_notional * scale
            if notional <= 0:
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "no_cash_or_exposure_headroom"})
                continue
            cash_cost = notional * (1 + args.fee_rate + args.slippage_rate)
            shares = notional / open_price
            cash -= cash_cost
            position = {
                **plan,
                "shares": shares,
                "entry_price": open_price,
                "entry_notional": notional,
                "entry_cash_cost": cash_cost,
            }
            positions.append(position)
            entry_count += 1

        close_exposure_before_exit = market_value(positions, prices, trade_date, "close")
        exit_count = 0
        remaining: list[dict[str, Any]] = []
        for position in positions:
            if position["exit_date"] != trade_date:
                remaining.append(position)
                continue
            close_price = prices.get((position["stock_id"], trade_date), {}).get("close")
            if close_price is None or pd.isna(close_price):
                skipped.append({"ranking_date": position["ranking_date"], "stock_id": position["stock_id"], "reason": "missing_exit_close"})
                remaining.append(position)
                continue
            gross_proceeds = float(position["shares"]) * float(close_price)
            proceeds = gross_proceeds * (1 - args.fee_rate - args.tax_rate - args.slippage_rate)
            cash += proceeds
            trade_return = proceeds / float(position["entry_cash_cost"]) - 1
            trades.append(
                {
                    "ranking_date": position["ranking_date"],
                    "stock_id": position["stock_id"],
                    "stock_name": position.get("stock_name"),
                    "entry_date": position["entry_date"].isoformat(),
                    "exit_date": trade_date.isoformat(),
                    "entry_price": round(float(position["entry_price"]), 4),
                    "exit_price": round(float(close_price), 4),
                    "entry_notional": round(float(position["entry_notional"]), 6),
                    "net_return": round(float(trade_return), 6),
                }
            )
            exit_count += 1
        positions = remaining

        close_exposure_before_deleverage = market_value(positions, prices, trade_date, "close")
        positions, cash, deleverage = deleverage_to_gross_cap(
            positions=positions,
            prices=prices,
            trade_date=trade_date,
            cash=cash,
            max_gross_exposure=float(args.max_gross_exposure),
            fee_rate=float(args.fee_rate),
            tax_rate=float(args.tax_rate),
            slippage_rate=float(args.slippage_rate),
        )
        close_exposure = market_value(positions, prices, trade_date, "close")
        equity = cash + close_exposure
        daily_return = equity / previous_equity - 1 if previous_equity else 0.0
        previous_equity = equity
        daily.append(
            {
                "date": trade_date.isoformat(),
                "equity": round(equity, 6),
                "daily_return": round(daily_return, 6),
                "cash": round(cash, 6),
                "gross_exposure": round(close_exposure / equity, 6) if equity else 0.0,
                "positions": len(positions),
                "entries": entry_count,
                "exits": exit_count,
                "close_exposure_before_exit": round(close_exposure_before_exit, 6),
                "close_exposure_before_deleverage": round(close_exposure_before_deleverage, 6),
                **deleverage,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "signal_timing": "D close ranking artifact",
            "entry_timing": "D+1 open",
            "exit_timing": f"fixed {args.horizon} market bars, exit at close",
            "overlapping_positions": True,
            "exposure_policy": "close exposure is deleveraged after scheduled exits to stay within max_gross_exposure",
            "model_feature": False,
        },
        "inputs": {
            "rankings_dir": str(resolve_path(args.rankings_dir)),
            "features": str(resolve_path(args.features)),
            "top_n": args.top_n,
            "horizon": args.horizon,
            "max_ranking_files": args.max_ranking_files,
            "max_gross_exposure": args.max_gross_exposure,
            "max_position_weight": args.max_position_weight,
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
            },
        },
        "summary": summarize(daily, trades, skipped),
        "daily": daily,
        "trades": trades,
        "skipped": skipped,
    }


def summarize(daily: list[dict[str, Any]], trades: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    if not daily:
        return {"final_equity": 1.0, "total_return": 0.0, "trade_count": 0, "skipped_count": len(skipped)}
    returns = [float(item["daily_return"]) for item in daily]
    equity_values = [float(item["equity"]) for item in daily]
    max_equity = equity_values[0]
    worst_drawdown = 0.0
    for value in equity_values:
        max_equity = max(max_equity, value)
        worst_drawdown = min(worst_drawdown, value / max_equity - 1)
    trade_returns = [float(item["net_return"]) for item in trades]
    return {
        "final_equity": round(equity_values[-1], 6),
        "total_return": round(equity_values[-1] - 1, 6),
        "max_drawdown": round(worst_drawdown, 6),
        "daily_count": len(daily),
        "trade_count": len(trades),
        "skipped_count": len(skipped),
        "win_rate": round(sum(value > 0 for value in trade_returns) / len(trade_returns), 6) if trade_returns else None,
        "avg_trade_return": round(sum(trade_returns) / len(trade_returns), 6) if trade_returns else None,
        "max_gross_exposure": round(max(float(item["gross_exposure"]) for item in daily), 6),
        "avg_gross_exposure": round(sum(float(item["gross_exposure"]) for item in daily) / len(daily), 6),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# Overlap Portfolio Replay",
            "",
            f"- final_equity：{summary.get('final_equity')}",
            f"- total_return：{pct(summary.get('total_return'))}",
            f"- max_drawdown：{pct(summary.get('max_drawdown'))}",
            f"- trade_count：{summary.get('trade_count')}",
            f"- max_gross_exposure：{pct(summary.get('max_gross_exposure'))}",
            "",
        ]
    )


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def main() -> int:
    args = parse_args()
    payload = run_portfolio(args)
    run_date = datetime.now().strftime("%Y-%m-%d")
    output_path = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "backtest" / f"portfolio_replay_{run_date}.json"
    md_path = output_path.with_suffix(".md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
