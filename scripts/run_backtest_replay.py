#!/usr/bin/env python3
"""Production replay 回測第一版：ranking D 日，D+1 開盤進場。

此腳本只讀既有 ranking artifacts 與 features parquet，不訓練模型、不重跑 ranking。
第一版聚焦 1D / 3D / 5D / 10D horizon 統計，完整 portfolio equity curve
留給後續切片。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-replay-backtest.v1"
OHLC_COLUMNS = ["open", "high", "low", "close"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run production replay backtest from ranking artifacts")
    parser.add_argument("--rankings-dir", default="artifacts", help="ranking_*.csv 所在目錄")
    parser.add_argument("--features", default="data/clean/features.parquet", help="features parquet，需含 OHLC")
    parser.add_argument("--horizons", default="1,3,5,10", help="持有期交易日數，例如 1,3,5,10")
    parser.add_argument("--top-n", type=int, default=10, help="每份 ranking 取前 N 檔")
    parser.add_argument("--max-ranking-files", type=int, default=None, help="限制處理最近 N 份 ranking，用於本機輕量驗證")
    parser.add_argument("--fee-rate", type=float, default=0.001425, help="單邊手續費率")
    parser.add_argument("--tax-rate", type=float, default=0.003, help="賣出證交稅率")
    parser.add_argument("--slippage-rate", type=float, default=0.001, help="買賣各一側滑價率")
    parser.add_argument("--max-position-weight", type=float, default=0.2, help="單檔部位上限；會套用 ranking 內 max_position_weight 與此值的較小者")
    parser.add_argument("--default-gross-exposure", type=float, default=0.65, help="ranking 缺 gross_exposure 時的預設總曝險")
    parser.add_argument("--output", default=None, help="輸出 JSON；未指定時寫 artifacts/backtest/replay_YYYY-MM-DD.json")
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def ranking_files(rankings_dir: Path, max_files: int | None) -> list[Path]:
    files = sorted(
        [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)],
        key=lambda path: ranking_date(path),
    )
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{rankings_dir}")
    return files[-max_files:] if max_files else files


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for rank, row in enumerate(rows[:top_n], start=1):
        result.append(
            {
                "rank": rank,
                "stock_id": str(row.get("stock_id", "")).strip().zfill(4),
                "stock_name": row.get("stock_name"),
                "model_prob": parse_float(row.get("model_prob")),
                "risk_adjusted_score": parse_float(row.get("risk_adjusted_score")),
                "suggested_weight": parse_float(row.get("suggested_weight")),
                "max_position_weight": parse_float(row.get("max_position_weight")),
                "gross_exposure": parse_float(row.get("gross_exposure")),
                "industry_name": row.get("industry_name"),
                "sector_name": row.get("sector_name"),
            }
        )
    return result


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else parsed


def load_price_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{path}")
    price_columns = ["stock_id", *OHLC_COLUMNS]
    try:
        frame = pd.read_parquet(path, columns=[*price_columns, "trade_date"])
    except Exception as exc:
        if "trade_date" not in str(exc):
            raise
        frame = pd.read_parquet(path, columns=[*price_columns, "date"])
        frame = frame.rename(columns={"date": "trade_date"})
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame.sort_values(["stock_id", "trade_date"]).reset_index(drop=True)


def build_price_index(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {stock_id: group.reset_index(drop=True) for stock_id, group in frame.groupby("stock_id", sort=False)}


def market_trade_dates(frame: pd.DataFrame) -> list[Any]:
    return sorted(frame["trade_date"].dropna().unique())


def next_market_trade_date(trade_dates: list[Any], ranking_date_text: str) -> Any | None:
    ranking_date_value = datetime.fromisoformat(ranking_date_text).date()
    for trade_date in trade_dates:
        if trade_date > ranking_date_value:
            return trade_date
    return None


def market_holding_dates(trade_dates: list[Any], entry_date: Any, horizon: int) -> list[Any] | None:
    try:
        entry_index = trade_dates.index(entry_date)
    except ValueError:
        return None
    end_index = entry_index + horizon
    if end_index > len(trade_dates):
        return None
    return trade_dates[entry_index:end_index]


def stock_holding_bars(stock_prices: pd.DataFrame, holding_dates: list[Any]) -> pd.DataFrame | None:
    holding = stock_prices[stock_prices["trade_date"].isin(holding_dates)].reset_index(drop=True)
    if len(holding) != len(holding_dates):
        return None
    if list(holding["trade_date"]) != holding_dates:
        return None
    return holding


def has_missing_ohlc(holding: pd.DataFrame) -> bool:
    return bool(holding[OHLC_COLUMNS].isna().any().any())


def simulate_trade(
    holding: pd.DataFrame,
    fee_rate: float,
    tax_rate: float,
    slippage_rate: float,
) -> dict[str, Any] | None:
    entry_row = holding.iloc[0]
    exit_row = holding.iloc[-1]
    entry_open = float(entry_row["open"])
    exit_close = float(exit_row["close"])
    if pd.isna(entry_open) or pd.isna(exit_close) or has_missing_ohlc(holding):
        return None
    entry_cost = entry_open * (1 + slippage_rate) * (1 + fee_rate)
    exit_proceeds = exit_close * (1 - slippage_rate) * (1 - fee_rate - tax_rate)
    net_return = exit_proceeds / entry_cost - 1
    mae = float(holding["low"].min()) / entry_open - 1
    mfe = float(holding["high"].max()) / entry_open - 1
    return {
        "entry_date": entry_row["trade_date"].isoformat(),
        "exit_date": exit_row["trade_date"].isoformat(),
        "entry_open": round(entry_open, 4),
        "exit_close": round(exit_close, 4),
        "net_return": round(net_return, 6),
        "mae": round(mae, 6),
        "mfe": round(mfe, 6),
    }


def run_replay(args: argparse.Namespace) -> dict[str, Any]:
    horizons = [int(value.strip()) for value in args.horizons.split(",") if value.strip()]
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    price_frame = load_price_frame(features_path)
    trade_dates = market_trade_dates(price_frame)
    price_index = build_price_index(price_frame)
    files = ranking_files(rankings_dir, args.max_ranking_files)

    trades: list[dict[str, Any]] = []
    portfolio_observations: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for ranking_path in files:
        date_text = ranking_date(ranking_path)
        ranking_items = read_ranking(ranking_path, args.top_n)
        entry_date = next_market_trade_date(trade_dates, date_text)
        if entry_date is None:
            for item in ranking_items:
                skipped.append({"ranking_date": date_text, "stock_id": item["stock_id"], "reason": "missing_next_market_trade_day"})
            continue
        weights = portfolio_weights(
            ranking_items,
            default_gross_exposure=args.default_gross_exposure,
            max_position_weight=args.max_position_weight,
        )
        trades_by_horizon: dict[int, list[dict[str, Any]]] = {horizon: [] for horizon in horizons}
        for item in ranking_items:
            stock_prices = price_index.get(item["stock_id"])
            if stock_prices is None:
                skipped.append({"ranking_date": date_text, "stock_id": item["stock_id"], "reason": "missing_price_history"})
                continue
            entry_bar = stock_prices[stock_prices["trade_date"] == entry_date]
            if entry_bar.empty or pd.isna(entry_bar.iloc[0]["open"]):
                skipped.append(
                    {
                        "ranking_date": date_text,
                        "stock_id": item["stock_id"],
                        "reason": "missing_entry_bar",
                        "expected_entry_date": entry_date.isoformat(),
                    }
                )
                continue
            for horizon in horizons:
                holding_dates = market_holding_dates(trade_dates, entry_date, horizon)
                if holding_dates is None:
                    skipped.append(
                        {
                            "ranking_date": date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "insufficient_future_market_bars",
                        }
                    )
                    continue
                expected_exit_date = holding_dates[-1]
                holding = stock_holding_bars(stock_prices, holding_dates)
                if holding is None:
                    exit_bar = stock_prices[stock_prices["trade_date"] == expected_exit_date]
                    reason = "missing_exit_bar" if exit_bar.empty or pd.isna(exit_bar.iloc[0]["close"]) else "missing_ohlc_bar"
                    skipped.append(
                        {
                            "ranking_date": date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": reason,
                            "expected_entry_date": entry_date.isoformat(),
                            "expected_exit_date": expected_exit_date.isoformat(),
                        }
                    )
                    continue
                if has_missing_ohlc(holding):
                    skipped.append(
                        {
                            "ranking_date": date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "missing_ohlc_bar",
                            "expected_entry_date": entry_date.isoformat(),
                            "expected_exit_date": expected_exit_date.isoformat(),
                        }
                    )
                    continue
                outcome = simulate_trade(
                    holding=holding,
                    fee_rate=args.fee_rate,
                    tax_rate=args.tax_rate,
                    slippage_rate=args.slippage_rate,
                )
                if outcome is None:
                    skipped.append(
                        {
                            "ranking_date": date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "invalid_ohlc_bar",
                            "expected_entry_date": entry_date.isoformat(),
                            "expected_exit_date": expected_exit_date.isoformat(),
                        }
                    )
                    continue
                trade = {
                    "ranking_date": date_text,
                    "horizon": horizon,
                    **item,
                    "portfolio_weight": weights.get(item["stock_id"], 0.0),
                    **outcome,
                }
                trades.append(trade)
                trades_by_horizon[horizon].append(trade)
        for horizon, horizon_trades in trades_by_horizon.items():
            observation = portfolio_observation(date_text, horizon, horizon_trades, weights)
            if observation is not None:
                portfolio_observations.append(observation)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "signal_timing": "D close ranking artifact",
            "entry_timing": "D+1 open",
            "entry_bar_policy": "use next market trading day; skip stocks without OHLC/open on that date",
            "lookahead_guard": "ranking date only selects future OHLC for simulated execution",
            "portfolio_equity_curve": "bucket_only",
            "portfolio_policy": "per-ranking-date bucket; no overlapping-position rebalance in v1",
        },
        "inputs": {
            "rankings_dir": str(rankings_dir),
            "features": str(features_path),
            "ranking_files": [str(path) for path in files],
            "top_n": args.top_n,
            "horizons": horizons,
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
                "max_position_weight": args.max_position_weight,
                "default_gross_exposure": args.default_gross_exposure,
            },
        },
        "summary": summarize(trades, portfolio_observations),
        "trades": trades,
        "portfolio": {
            "observations": portfolio_observations,
            "equity_curve": equity_curve(portfolio_observations),
        },
        "skipped": skipped,
    }


def portfolio_weights(
    items: list[dict[str, Any]],
    default_gross_exposure: float,
    max_position_weight: float,
) -> dict[str, float]:
    raw_weights: dict[str, float] = {}
    for item in items:
        suggested = item.get("suggested_weight")
        weight = suggested if suggested is not None and suggested > 0 else 1 / len(items) if items else 0
        row_cap = item.get("max_position_weight")
        cap = min(value for value in [max_position_weight, row_cap] if value is not None and value > 0)
        raw_weights[item["stock_id"]] = min(float(weight), float(cap))

    total = sum(raw_weights.values())
    if total <= 0:
        return {stock_id: 0.0 for stock_id in raw_weights}
    row_gross = next((item.get("gross_exposure") for item in items if item.get("gross_exposure") is not None), None)
    gross_exposure = float(row_gross) if row_gross is not None and row_gross > 0 else default_gross_exposure
    target_total = min(gross_exposure, total)
    scale = target_total / total
    return {stock_id: round(weight * scale, 6) for stock_id, weight in raw_weights.items()}


def portfolio_observation(
    ranking_date_text: str,
    horizon: int,
    trades: list[dict[str, Any]],
    weights: dict[str, float],
) -> dict[str, Any] | None:
    valid = [trade for trade in trades if trade.get("portfolio_weight", 0) > 0]
    if not valid:
        return None
    invested_weight = sum(float(trade["portfolio_weight"]) for trade in valid)
    weighted_return = sum(float(trade["portfolio_weight"]) * float(trade["net_return"]) for trade in valid)
    return {
        "ranking_date": ranking_date_text,
        "horizon": horizon,
        "positions": len(valid),
        "invested_weight": round(invested_weight, 6),
        "cash_weight": round(max(0.0, 1 - invested_weight), 6),
        "portfolio_return": round(weighted_return, 6),
        "gross_target_weight": round(sum(weights.values()), 6),
    }


def equity_curve(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    equity_by_horizon: dict[int, float] = {}
    curve: list[dict[str, Any]] = []
    for item in sorted(observations, key=lambda row: (row["horizon"], row["ranking_date"])):
        horizon = int(item["horizon"])
        equity = equity_by_horizon.get(horizon, 1.0) * (1 + float(item["portfolio_return"]))
        equity_by_horizon[horizon] = equity
        curve.append(
            {
                "ranking_date": item["ranking_date"],
                "horizon": horizon,
                "portfolio_return": item["portfolio_return"],
                "equity": round(equity, 6),
            }
        )
    return curve


def summarize(trades: list[dict[str, Any]], portfolio_observations: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trade_count": 0, "by_horizon": {}, "portfolio_by_horizon": {}}
    frame = pd.DataFrame(trades)
    by_horizon = {}
    for horizon, group in frame.groupby("horizon"):
        returns = pd.to_numeric(group["net_return"], errors="coerce")
        by_horizon[str(int(horizon))] = {
            "trade_count": int(len(group)),
            "avg_net_return": round(float(returns.mean()), 6),
            "median_net_return": round(float(returns.median()), 6),
            "hit_rate": round(float((returns > 0).mean()), 6),
            "avg_mae": round(float(pd.to_numeric(group["mae"], errors="coerce").mean()), 6),
            "avg_mfe": round(float(pd.to_numeric(group["mfe"], errors="coerce").mean()), 6),
        }
    portfolio_by_horizon = {}
    if portfolio_observations:
        portfolio_frame = pd.DataFrame(portfolio_observations)
        for horizon, group in portfolio_frame.groupby("horizon"):
            returns = pd.to_numeric(group["portfolio_return"], errors="coerce")
            portfolio_by_horizon[str(int(horizon))] = {
                "observation_count": int(len(group)),
                "avg_portfolio_return": round(float(returns.mean()), 6),
                "hit_rate": round(float((returns > 0).mean()), 6),
                "total_compounded_return": round(float((1 + returns).prod() - 1), 6),
                "max_drawdown": round(max_drawdown(list(returns)), 6),
            }
    return {"trade_count": int(len(frame)), "by_horizon": by_horizon, "portfolio_by_horizon": portfolio_by_horizon}


def max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1 + float(value)
        peak = max(peak, equity)
        drawdown = equity / peak - 1
        worst = min(worst, drawdown)
    return worst


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production Replay Backtest",
        "",
        f"- generated_at：{payload['generated_at']}",
        f"- ranking files：{len(payload['inputs']['ranking_files'])}",
        f"- top_n：{payload['inputs']['top_n']}",
        f"- trade_count：{payload['summary']['trade_count']}",
        "",
        "## Horizon Summary",
        "",
        "| Horizon | Trades | Avg Return | Median | Hit Rate | Avg MAE | Avg MFE |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for horizon, item in payload["summary"]["by_horizon"].items():
        lines.append(
            "| {h} | {n} | {avg:.2%} | {med:.2%} | {hit:.2%} | {mae:.2%} | {mfe:.2%} |".format(
                h=horizon,
                n=item["trade_count"],
                avg=item["avg_net_return"],
                med=item["median_net_return"],
                hit=item["hit_rate"],
                mae=item["avg_mae"],
                mfe=item["avg_mfe"],
            )
        )
    lines.append("")
    if payload["summary"].get("portfolio_by_horizon"):
        lines.extend(
            [
                "## Portfolio Bucket Summary",
                "",
                "| Horizon | Buckets | Avg Return | Hit Rate | Compounded | Max DD |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for horizon, item in payload["summary"]["portfolio_by_horizon"].items():
            lines.append(
                "| {h} | {n} | {avg:.2%} | {hit:.2%} | {total:.2%} | {mdd:.2%} |".format(
                    h=horizon,
                    n=item["observation_count"],
                    avg=item["avg_portfolio_return"],
                    hit=item["hit_rate"],
                    total=item["total_compounded_return"],
                    mdd=item["max_drawdown"],
                )
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = run_replay(args)
    run_date = datetime.now().strftime("%Y-%m-%d")
    output_path = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "backtest" / f"replay_{run_date}.json"
    md_path = output_path.with_suffix(".md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": str(output_path),
                "markdown": str(md_path),
                "trade_count": payload["summary"]["trade_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
