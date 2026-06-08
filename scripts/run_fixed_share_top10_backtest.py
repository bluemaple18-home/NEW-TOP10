#!/usr/bin/env python3
"""固定股數 Top10 歷史回測。

此腳本只讀既有 ranking artifacts 與 features parquet，不訓練模型、不重跑
ranking、不修改 production score。用途是回答一個直觀問題：如果每天照 Top10
每檔買固定股數，半年下來實際損益是多少。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay  # noqa: E402


SCHEMA_VERSION = "fixed-share-top10-backtest.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run fixed-share Top10 historical backtest")
    parser.add_argument(
        "--variant",
        action="append",
        required=True,
        help="格式 label=path/to/rankings_dir；可重複指定，第一個當 baseline",
    )
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--shares", type=int, default=100)
    parser.add_argument("--horizons", default="5,7,10,15,20", help="持有期交易日數；5 是最短觀察門檻，不代表固定賣點")
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--max-ranking-files", type=int, default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def parse_variant(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"--variant 需使用 label=path 格式：{value}")
    label, path_text = value.split("=", 1)
    label = label.strip()
    if not label:
        raise ValueError(f"--variant label 不可空白：{value}")
    return label, resolve_path(path_text.strip())


def parse_horizons(value: str) -> list[int]:
    horizons = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not horizons:
        raise ValueError("--horizons 不可空白")
    if any(horizon < 5 for horizon in horizons):
        raise ValueError("固定股數回測的持有期至少 5 個交易日")
    return horizons


def price_lookup(price_frame: pd.DataFrame) -> dict[tuple[str, Any], dict[str, float]]:
    lookup: dict[tuple[str, Any], dict[str, float]] = {}
    for row in price_frame.itertuples(index=False):
        lookup[(str(row.stock_id).zfill(4), row.trade_date)] = {
            "open": float(row.open),
            "close": float(row.close),
        }
    return lookup


def trade_dates_for_ranking(
    trade_dates: list[Any],
    ranking_date: str,
    entry_delay_trade_days: int,
    horizon: int,
) -> tuple[Any | None, Any | None]:
    entry_date = run_backtest_replay.next_market_trade_date(trade_dates, ranking_date, entry_delay_trade_days)
    if entry_date is None:
        return None, None
    holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, horizon)
    if holding_dates is None:
        return entry_date, None
    return entry_date, holding_dates[-1]


def buy_cash(entry_open: float, shares: int, fee_rate: float, slippage_rate: float) -> float:
    return entry_open * shares * (1 + slippage_rate) * (1 + fee_rate)


def sell_cash(exit_close: float, shares: int, fee_rate: float, tax_rate: float, slippage_rate: float) -> float:
    return exit_close * shares * (1 - slippage_rate) * (1 - fee_rate - tax_rate)


def run_variant(
    label: str,
    rankings_dir: Path,
    price_frame: pd.DataFrame,
    args: argparse.Namespace,
) -> dict[str, Any]:
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    lookup = price_lookup(price_frame)
    files = run_backtest_replay.ranking_files(rankings_dir, args.max_ranking_files)

    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for ranking_path in files:
        ranking_date = run_backtest_replay.ranking_date(ranking_path)
        entry_date, exit_date = trade_dates_for_ranking(
            trade_dates,
            ranking_date,
            args.entry_delay_trade_days,
            args.horizon,
        )
        ranking_items = run_backtest_replay.read_ranking(ranking_path, args.top_n)
        if entry_date is None:
            skipped.append({"ranking_date": ranking_date, "reason": "missing_next_market_trade_day"})
            continue
        if exit_date is None:
            skipped.append(
                {
                    "ranking_date": ranking_date,
                    "entry_date": entry_date.isoformat(),
                    "reason": "insufficient_future_market_bars",
                }
            )
            continue

        for item in ranking_items:
            stock_id = item["stock_id"]
            entry_bar = lookup.get((stock_id, entry_date))
            exit_bar = lookup.get((stock_id, exit_date))
            if entry_bar is None or pd.isna(entry_bar.get("open")):
                skipped.append(
                    {
                        "ranking_date": ranking_date,
                        "stock_id": stock_id,
                        "expected_entry_date": entry_date.isoformat(),
                        "reason": "missing_entry_open",
                    }
                )
                continue
            if exit_bar is None or pd.isna(exit_bar.get("close")):
                skipped.append(
                    {
                        "ranking_date": ranking_date,
                        "stock_id": stock_id,
                        "expected_exit_date": exit_date.isoformat(),
                        "reason": "missing_exit_close",
                    }
                )
                continue

            entry_open = float(entry_bar["open"])
            exit_close = float(exit_bar["close"])
            cost = buy_cash(entry_open, args.shares, args.fee_rate, args.slippage_rate)
            proceeds = sell_cash(exit_close, args.shares, args.fee_rate, args.tax_rate, args.slippage_rate)
            gross_pnl = exit_close * args.shares - entry_open * args.shares
            net_pnl = proceeds - cost
            trades.append(
                {
                    "variant": label,
                    "ranking_date": ranking_date,
                    "rank": item["rank"],
                    "stock_id": stock_id,
                    "stock_name": item.get("stock_name"),
                    "industry_name": item.get("industry_name"),
                    "sector_name": item.get("sector_name"),
                    "entry_date": entry_date.isoformat(),
                    "exit_date": exit_date.isoformat(),
                    "entry_open": round(entry_open, 4),
                    "exit_close": round(exit_close, 4),
                    "shares": int(args.shares),
                    "buy_cash": round(cost, 2),
                    "sell_cash": round(proceeds, 2),
                    "gross_pnl": round(gross_pnl, 2),
                    "net_pnl": round(net_pnl, 2),
                    "net_return": round(net_pnl / cost, 6) if cost else None,
                }
            )

    return {
        "label": label,
        "horizon": args.horizon,
        "rankings_dir": repo_path(rankings_dir),
        "ranking_file_count": len(files),
        "summary": summarize_trades(trades),
        "trades": trades,
        "realized_curve": realized_curve(trades),
        "skipped": skipped,
    }


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "trade_count": 0,
            "ranking_day_count": 0,
            "total_buy_cash": 0.0,
            "total_sell_cash": 0.0,
            "total_net_pnl": 0.0,
            "return_on_buy_cash": None,
            "win_rate": None,
        }
    frame = pd.DataFrame(trades)
    returns = pd.to_numeric(frame["net_return"], errors="coerce")
    total_buy = float(pd.to_numeric(frame["buy_cash"], errors="coerce").sum())
    total_sell = float(pd.to_numeric(frame["sell_cash"], errors="coerce").sum())
    total_pnl = float(pd.to_numeric(frame["net_pnl"], errors="coerce").sum())
    by_rank = {}
    for rank, group in frame.groupby("rank"):
        pnl = float(pd.to_numeric(group["net_pnl"], errors="coerce").sum())
        buy = float(pd.to_numeric(group["buy_cash"], errors="coerce").sum())
        by_rank[str(int(rank))] = {
            "trade_count": int(len(group)),
            "net_pnl": round(pnl, 2),
            "return_on_buy_cash": round(pnl / buy, 6) if buy else None,
        }
    by_month = {}
    frame["ranking_month"] = frame["ranking_date"].astype(str).str.slice(0, 7)
    for month, group in frame.groupby("ranking_month"):
        pnl = float(pd.to_numeric(group["net_pnl"], errors="coerce").sum())
        buy = float(pd.to_numeric(group["buy_cash"], errors="coerce").sum())
        by_month[str(month)] = {
            "trade_count": int(len(group)),
            "net_pnl": round(pnl, 2),
            "return_on_buy_cash": round(pnl / buy, 6) if buy else None,
        }
    return {
        "trade_count": int(len(frame)),
        "ranking_day_count": int(frame["ranking_date"].nunique()),
        "total_buy_cash": round(total_buy, 2),
        "total_sell_cash": round(total_sell, 2),
        "total_gross_pnl": round(float(pd.to_numeric(frame["gross_pnl"], errors="coerce").sum()), 2),
        "total_net_pnl": round(total_pnl, 2),
        "return_on_buy_cash": round(total_pnl / total_buy, 6) if total_buy else None,
        "avg_trade_net_return": round(float(returns.mean()), 6),
        "median_trade_net_return": round(float(returns.median()), 6),
        "win_rate": round(float((returns > 0).mean()), 6),
        "by_rank": by_rank,
        "by_month": by_month,
    }


def realized_curve(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pnl_by_exit: dict[str, float] = defaultdict(float)
    buy_by_exit: dict[str, float] = defaultdict(float)
    for trade in trades:
        exit_date = str(trade["exit_date"])
        pnl_by_exit[exit_date] += float(trade["net_pnl"])
        buy_by_exit[exit_date] += float(trade["buy_cash"])
    cumulative_pnl = 0.0
    cumulative_buy = 0.0
    curve = []
    for exit_date in sorted(pnl_by_exit):
        cumulative_pnl += pnl_by_exit[exit_date]
        cumulative_buy += buy_by_exit[exit_date]
        curve.append(
            {
                "exit_date": exit_date,
                "realized_net_pnl": round(pnl_by_exit[exit_date], 2),
                "realized_buy_cash": round(buy_by_exit[exit_date], 2),
                "cumulative_net_pnl": round(cumulative_pnl, 2),
                "cumulative_return_on_buy_cash": round(cumulative_pnl / cumulative_buy, 6) if cumulative_buy else None,
            }
        )
    return curve


def compare_variants(variants: list[dict[str, Any]]) -> dict[str, Any]:
    if not variants:
        return {}
    rows = []
    baseline_label = variants[0]["label"]
    for horizon in sorted({int(variant["horizon"]) for variant in variants}):
        horizon_variants = [variant for variant in variants if int(variant["horizon"]) == horizon]
        baseline = horizon_variants[0]
        base_summary = baseline["summary"]
        for variant in horizon_variants:
            summary = variant["summary"]
            rows.append(
                {
                    "horizon": horizon,
                    "label": variant["label"],
                    "trade_count": summary["trade_count"],
                    "ranking_day_count": summary["ranking_day_count"],
                    "total_buy_cash": summary["total_buy_cash"],
                    "total_net_pnl": summary["total_net_pnl"],
                    "return_on_buy_cash": summary["return_on_buy_cash"],
                    "win_rate": summary["win_rate"],
                    "net_pnl_delta_vs_baseline": round(summary["total_net_pnl"] - base_summary["total_net_pnl"], 2),
                    "return_delta_vs_baseline": round(
                        float(summary["return_on_buy_cash"] or 0) - float(base_summary["return_on_buy_cash"] or 0),
                        6,
                    ),
                }
            )
    return {"baseline_label": baseline_label, "rows": rows}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    price_frame = run_backtest_replay.load_price_frame(features_path)
    variant_specs = [parse_variant(value) for value in args.variant]
    variants = []
    for horizon in parse_horizons(args.horizons):
        scoped_args = argparse.Namespace(**{**vars(args), "horizon": horizon})
        for label, path in variant_specs:
            variants.append(run_variant(label, path, price_frame, scoped_args))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "signal_timing": "D close ranking artifact",
            "entry_timing": f"D+{args.entry_delay_trade_days} open",
            "exit_timing": f"tested horizons {args.horizons} market trading days after entry, close",
            "position_sizing": f"fixed {args.shares} shares per stock per ranking day",
            "cash_policy": "no cash constraint; report total buy cash and realized pnl",
            "lookahead_guard": "ranking artifacts are fixed historical outputs; future OHLC is used only for simulated execution",
            "production_changes": False,
            "model_changes": False,
        },
        "inputs": {
            "features": repo_path(features_path),
            "top_n": args.top_n,
            "shares": args.shares,
            "horizons": parse_horizons(args.horizons),
            "entry_delay_trade_days": args.entry_delay_trade_days,
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
            },
            "max_ranking_files": args.max_ranking_files,
        },
        "comparison": compare_variants(variants),
        "variants": variants,
    }


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


def money(value: Any) -> str:
    return f"{float(value):,.0f}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Fixed Share Top10 Backtest",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- rule: Top{payload['inputs']['top_n']} 每檔 {payload['inputs']['shares']} 股，{payload['contract']['entry_timing']}，{payload['contract']['exit_timing']}",
        f"- features: {payload['inputs']['features']}",
        f"- production_changes: {payload['contract']['production_changes']}",
        f"- model_changes: {payload['contract']['model_changes']}",
        "",
        "## Comparison",
        "",
        "| Horizon | Variant | Ranking Days | Trades | Buy Cash | Net PnL | Return On Buy Cash | Win Rate | PnL Delta | Return Delta |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["comparison"]["rows"]:
        lines.append(
            "| {horizon} | {label} | {days} | {trades} | {buy} | {pnl} | {ret} | {win} | {delta_pnl} | {delta_ret} |".format(
                horizon=row["horizon"],
                label=row["label"],
                days=row["ranking_day_count"],
                trades=row["trade_count"],
                buy=money(row["total_buy_cash"]),
                pnl=money(row["total_net_pnl"]),
                ret=pct(row["return_on_buy_cash"]),
                win=pct(row["win_rate"]),
                delta_pnl=money(row["net_pnl_delta_vs_baseline"]),
                delta_ret=pct(row["return_delta_vs_baseline"]),
            )
        )
    lines.append("")
    lines.append("## Monthly Net PnL")
    labels = [f"H{variant['horizon']} {variant['label']}" for variant in payload["variants"]]
    months = sorted({month for variant in payload["variants"] for month in variant["summary"].get("by_month", {})})
    lines.append("")
    lines.append("| Month | " + " | ".join(labels) + " |")
    lines.append("|---|" + "|".join("---:" for _ in labels) + "|")
    for month in months:
        values = []
        for variant in payload["variants"]:
            item = variant["summary"].get("by_month", {}).get(month)
            values.append(money(item["net_pnl"]) if item else "0")
        lines.append("| " + month + " | " + " | ".join(values) + " |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- 這是固定股數帳本，不是資金配置型 portfolio replay。")
    lines.append("- 同一天 Top10 每檔都買 100 股，沒有現金不足限制，所以重點看總買入金額、總損益、買入金額報酬率。")
    tested = "/".join(f"{horizon}D" for horizon in payload["inputs"]["horizons"])
    lines.append(f"- 5D 是最短持有檢查點；本次事前測試 {tested}，用來看系統偏短線還是波段，不是用後照鏡挑單一天。")
    lines.append("- 此 artifact 只作研究驗證，不能當模型升版或 production ranking 變更證據。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "backtest" / f"fixed_share_top10_backtest_{datetime.now().strftime('%Y-%m-%d')}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
