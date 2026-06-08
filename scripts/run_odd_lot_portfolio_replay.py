#!/usr/bin/env python3
"""固定本金零股 portfolio replay。

這條 replay 模擬小本金使用者照 ranking D 日訊號、D+1 開盤買進。它使用整數
股數，允許零股但不允許小數股；新倉受現金、總曝險與單檔上限限制。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay, run_portfolio_replay  # noqa: E402


SCHEMA_VERSION = "odd-lot-portfolio-replay.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run fixed-capital odd-lot portfolio replay")
    parser.add_argument("--rankings-dir", required=True)
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--horizon", type=int, default=40)
    parser.add_argument("--top-n", type=int, default=7)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--max-ranking-files", type=int, default=None)
    parser.add_argument("--initial-cash", type=float, default=300_000)
    parser.add_argument("--max-gross-exposure", type=float, default=0.85)
    parser.add_argument("--max-position-weight", type=float, default=0.15)
    parser.add_argument("--min-shares", type=int, default=1)
    parser.add_argument("--lot-size", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--stop-loss-pct", type=float, default=None)
    parser.add_argument("--take-profit-pct", type=float, default=None)
    parser.add_argument("--trailing-stop-pct", type=float, default=None)
    parser.add_argument("--min-event-holding-days", type=int, default=5)
    parser.add_argument("--same-day-hit-priority", choices=["stop_loss", "take_profit"], default="stop_loss")
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


def buy_cost(notional: float, fee_rate: float, slippage_rate: float) -> float:
    return float(notional) * (1 + float(fee_rate) + float(slippage_rate))


def floor_to_lot(shares: float, lot_size: int) -> int:
    lot = max(1, int(lot_size))
    return int(math.floor(float(shares) / lot) * lot)


def position_value(
    positions: list[dict[str, Any]],
    prices: dict[tuple[str, Any], dict[str, float]],
    trade_date: Any,
    field: str,
) -> float:
    value = 0.0
    for position in positions:
        price = prices.get((position["stock_id"], trade_date), {}).get(field)
        if price is not None and not pd.isna(price):
            value += float(position["shares"]) * float(price)
    return value


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    price_frame = run_backtest_replay.load_price_frame(resolve_path(args.features))
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    prices = run_portfolio_replay.price_lookup(price_frame)
    plans, skipped = run_portfolio_replay.build_entry_plans(args, price_frame, trade_dates, {})
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
    sim_dates = [day for day in trade_dates if first_entry is not None and last_exit is not None and first_entry <= day <= last_exit]
    previous_equity = equity

    for trade_date in sim_dates:
        open_exposure = position_value(positions, prices, trade_date, "open")
        gross_headroom = max(0.0, equity * float(args.max_gross_exposure) - open_exposure)
        cash_headroom = max(0.0, cash)
        desired_entries = []
        for plan in plans_by_entry.get(trade_date, []):
            open_price = prices.get((plan["stock_id"], trade_date), {}).get("open")
            if open_price is None or pd.isna(open_price):
                skipped.append({"ranking_date": plan["ranking_date"], "stock_id": plan["stock_id"], "reason": "missing_entry_open"})
                continue
            desired_notional = min(equity * float(plan["target_weight"]), equity * float(args.max_position_weight))
            desired_entries.append((plan, float(open_price), desired_notional))
        total_desired = sum(item[2] for item in desired_entries)
        scale = min(1.0, gross_headroom / total_desired, cash_headroom / (total_desired * (1 + args.fee_rate + args.slippage_rate))) if total_desired > 0 else 0.0

        entry_count = 0
        for plan, open_price, desired_notional in desired_entries:
            target_notional = desired_notional * scale
            shares = floor_to_lot(target_notional / open_price, args.lot_size)
            if shares < int(args.min_shares):
                skipped.append(
                    {
                        "ranking_date": plan["ranking_date"],
                        "stock_id": plan["stock_id"],
                        "reason": "below_minimum_odd_lot_size",
                        "target_notional": round(target_notional, 2),
                        "open_price": round(open_price, 4),
                    }
                )
                continue
            notional = shares * open_price
            cost = buy_cost(notional, args.fee_rate, args.slippage_rate)
            if cost > cash + 1e-9 or notional > gross_headroom + 1e-9:
                skipped.append(
                    {
                        "ranking_date": plan["ranking_date"],
                        "stock_id": plan["stock_id"],
                        "reason": "cash_or_exposure_after_integer_rounding",
                        "shares": shares,
                        "cost": round(cost, 2),
                    }
                )
                continue
            cash -= cost
            gross_headroom -= notional
            positions.append(
                {
                    **plan,
                    "shares": shares,
                    "entry_price": open_price,
                    "high_water": open_price,
                    "holding_bar_count": 0,
                    "entry_notional": notional,
                    "entry_cash_cost": cost,
                }
            )
            entry_count += 1

        exit_count = 0
        stop_loss_count = 0
        take_profit_count = 0
        trailing_stop_count = 0
        scheduled_exit_count = 0
        remaining: list[dict[str, Any]] = []
        for position in positions:
            position["holding_bar_count"] = int(position.get("holding_bar_count") or 0) + 1
            event = run_portfolio_replay.event_exit(
                position=position,
                prices=prices,
                trade_date=trade_date,
                stop_loss_pct=args.stop_loss_pct,
                take_profit_pct=args.take_profit_pct,
                trailing_stop_pct=args.trailing_stop_pct,
                min_event_holding_days=args.min_event_holding_days,
                same_day_hit_priority=args.same_day_hit_priority,
            )
            if event is not None:
                trade, proceeds = run_portfolio_replay.close_trade(
                    position,
                    trade_date,
                    float(event["exit_price"]),
                    str(event["exit_reason"]),
                    args.fee_rate,
                    args.tax_rate,
                    args.slippage_rate,
                    bool(event.get("ambiguous_intraday_order", False)),
                )
                cash += proceeds
                trades.append(trade)
                exit_count += 1
                stop_loss_count += 1 if trade["exit_reason"] == "stop_loss" else 0
                take_profit_count += 1 if trade["exit_reason"] == "take_profit" else 0
                trailing_stop_count += 1 if trade["exit_reason"] == "trailing_stop" else 0
                continue
            if position["exit_date"] != trade_date:
                remaining.append(position)
                continue
            close_price = prices.get((position["stock_id"], trade_date), {}).get("close")
            if close_price is None or pd.isna(close_price):
                skipped.append({"ranking_date": position["ranking_date"], "stock_id": position["stock_id"], "reason": "missing_exit_close"})
                remaining.append(position)
                continue
            trade, proceeds = run_portfolio_replay.close_trade(
                position,
                trade_date,
                float(close_price),
                "scheduled_horizon",
                args.fee_rate,
                args.tax_rate,
                args.slippage_rate,
            )
            cash += proceeds
            trades.append(trade)
            exit_count += 1
            scheduled_exit_count += 1
        positions = remaining

        close_exposure = position_value(positions, prices, trade_date, "close")
        equity = cash + close_exposure
        daily_return = equity / previous_equity - 1 if previous_equity else 0.0
        previous_equity = equity
        daily.append(
            {
                "date": trade_date.isoformat(),
                "equity": round(equity, 2),
                "daily_return": round(daily_return, 6),
                "cash": round(cash, 2),
                "gross_exposure": round(close_exposure / equity, 6) if equity else 0.0,
                "positions": len(positions),
                "entries": entry_count,
                "exits": exit_count,
                "scheduled_exits": scheduled_exit_count,
                "stop_loss_exits": stop_loss_count,
                "take_profit_exits": take_profit_count,
                "trailing_stop_exits": trailing_stop_count,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "signal_timing": "D close ranking artifact",
            "entry_timing": f"D+{args.entry_delay_trade_days} open",
            "odd_lot": True,
            "fractional_shares": False,
            "exposure_policy": "max_gross_exposure only constrains new entries; exposure can drift with price moves until exits",
            "production_changes": False,
            "model_changes": False,
            "promotion_ready": False,
        },
        "inputs": {
            "rankings_dir": repo_path(resolve_path(args.rankings_dir)),
            "features": repo_path(resolve_path(args.features)),
            "horizon": args.horizon,
            "top_n": args.top_n,
            "entry_delay_trade_days": args.entry_delay_trade_days,
            "initial_cash": args.initial_cash,
            "max_gross_exposure": args.max_gross_exposure,
            "max_position_weight": args.max_position_weight,
            "min_shares": args.min_shares,
            "lot_size": args.lot_size,
            "stop_loss_pct": args.stop_loss_pct,
            "take_profit_pct": args.take_profit_pct,
            "trailing_stop_pct": args.trailing_stop_pct,
            "min_event_holding_days": args.min_event_holding_days,
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
            },
        },
        "summary": summarize(daily, trades, skipped, args.initial_cash),
        "daily": daily,
        "trades": trades,
        "skipped": skipped,
    }


def summarize(daily: list[dict[str, Any]], trades: list[dict[str, Any]], skipped: list[dict[str, Any]], initial_cash: float) -> dict[str, Any]:
    if not daily:
        return {
            "initial_cash": round(float(initial_cash), 2),
            "final_equity": round(float(initial_cash), 2),
            "total_return": 0.0,
            "trade_count": 0,
            "skipped_count": len(skipped),
        }
    equity_values = [float(row["equity"]) for row in daily]
    peak = equity_values[0]
    worst_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        worst_drawdown = min(worst_drawdown, value / peak - 1)
    trade_returns = [float(row["net_return"]) for row in trades]
    below_minimum = sum(1 for row in skipped if row.get("reason") == "below_minimum_odd_lot_size")
    return {
        "initial_cash": round(float(initial_cash), 2),
        "final_equity": round(equity_values[-1], 2),
        "total_pnl": round(equity_values[-1] - float(initial_cash), 2),
        "total_return": round(equity_values[-1] / float(initial_cash) - 1, 6),
        "max_drawdown": round(worst_drawdown, 6),
        "daily_count": len(daily),
        "trade_count": len(trades),
        "skipped_count": len(skipped),
        "below_minimum_odd_lot_count": below_minimum,
        "win_rate": round(sum(value > 0 for value in trade_returns) / len(trade_returns), 6) if trade_returns else None,
        "avg_trade_return": round(sum(trade_returns) / len(trade_returns), 6) if trade_returns else None,
        "max_gross_exposure": round(max(float(row["gross_exposure"]) for row in daily), 6),
        "avg_gross_exposure": round(sum(float(row["gross_exposure"]) for row in daily) / len(daily), 6),
        "min_cash": round(min(float(row["cash"]) for row in daily), 2),
        "avg_cash_weight": round(sum(float(row["cash"]) / float(row["equity"]) for row in daily if float(row["equity"])) / len(daily), 6),
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# Odd-Lot Portfolio Replay",
            "",
            f"- initial_cash: {summary.get('initial_cash')}",
            f"- final_equity: {summary.get('final_equity')}",
            f"- total_return: {pct(summary.get('total_return'))}",
            f"- max_drawdown: {pct(summary.get('max_drawdown'))}",
            f"- trade_count: {summary.get('trade_count')}",
            f"- avg_cash_weight: {pct(summary.get('avg_cash_weight'))}",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_portfolio_replay_{datetime.now().date().isoformat()}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), "markdown": repo_path(output.with_suffix(".md"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
