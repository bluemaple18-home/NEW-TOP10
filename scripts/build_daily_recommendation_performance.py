#!/usr/bin/env python3
"""建立每日報牌逐檔後驗績效 ledger。

本腳本只讀既有 ranking artifacts 與 features OHLC，計算已成熟的
D+1 / D+3 / D+5 / D+10 交易結果；不重跑 ranking、不訓練模型、不改推播。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay

SCHEMA_VERSION = "daily-recommendation-performance.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build daily recommendation performance ledger")
    parser.add_argument("--date", default=None, help="後驗截至日期 YYYY-MM-DD；未指定時使用 features 最新交易日")
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--horizons", default="1,3,5,10")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--max-ranking-days", type=int, default=80, help="只處理最近 N 個 ranking day，控制每日成本")
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
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def parse_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def latest_trade_date(frame: pd.DataFrame) -> date:
    values = sorted(frame["trade_date"].dropna().unique())
    if not values:
        raise RuntimeError("features 沒有可用 trade_date")
    return values[-1]


def ranking_files(rankings_dir: Path, as_of_date: date, max_days: int | None) -> list[Path]:
    files = [
        path
        for path in rankings_dir.glob("ranking_*.csv")
        if re.fullmatch(r"ranking_\d{4}-\d{2}-\d{2}\.csv", path.name)
        and parse_date(run_backtest_replay.ranking_date(path)) <= as_of_date
    ]
    files = sorted(files, key=run_backtest_replay.ranking_date)
    return files[-max_days:] if max_days else files


def horizon_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trade_count": 0}
    returns = [float(item["net_return"]) for item in trades]
    maes = [float(item["mae"]) for item in trades if item.get("mae") is not None]
    mfes = [float(item["mfe"]) for item in trades if item.get("mfe") is not None]
    return {
        "trade_count": len(trades),
        "avg_net_return": round(sum(returns) / len(returns), 6),
        "hit_rate": round(sum(value > 0 for value in returns) / len(returns), 6),
        "avg_mae": round(sum(maes) / len(maes), 6) if maes else None,
        "avg_mfe": round(sum(mfes) / len(mfes), 6) if mfes else None,
    }


def summarize_day(
    ranking_date_text: str,
    entry_date: date | None,
    trades_by_horizon: dict[int, list[dict[str, Any]]],
    pending: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    portfolio_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    horizons: dict[str, Any] = {}
    for horizon, trades in trades_by_horizon.items():
        observation = next(
            (
                item
                for item in portfolio_observations
                if item["ranking_date"] == ranking_date_text and int(item["horizon"]) == horizon
            ),
            None,
        )
        horizons[str(horizon)] = {
            **horizon_summary(trades),
            "pending_count": sum(
                1 for item in pending if item.get("ranking_date") == ranking_date_text and item.get("horizon") == horizon
            ),
            "skipped_count": sum(
                1 for item in skipped if item.get("ranking_date") == ranking_date_text and item.get("horizon") == horizon
            ),
            "portfolio_return": observation.get("portfolio_return") if observation else None,
        }
    return {
        "ranking_date": ranking_date_text,
        "entry_date": entry_date.isoformat() if entry_date else None,
        "horizons": horizons,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    horizons = [int(value.strip()) for value in args.horizons.split(",") if value.strip()]
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    price_frame = run_backtest_replay.load_price_frame(features_path)
    as_of_date = parse_date(args.date) if args.date else latest_trade_date(price_frame)
    price_frame = price_frame[price_frame["trade_date"] <= as_of_date].reset_index(drop=True)
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    files = ranking_files(rankings_dir, as_of_date, args.max_ranking_days)

    trades: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    portfolio_observations: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []

    for ranking_path in files:
        ranking_date_text = run_backtest_replay.ranking_date(ranking_path)
        ranking_items = run_backtest_replay.read_ranking(ranking_path, args.top_n)
        entry_date = run_backtest_replay.next_market_trade_date(
            trade_dates,
            ranking_date_text,
            args.entry_delay_trade_days,
        )
        weights = run_backtest_replay.portfolio_weights(
            ranking_items,
            default_gross_exposure=args.default_gross_exposure,
            max_position_weight=args.max_position_weight,
        )
        trades_by_horizon: dict[int, list[dict[str, Any]]] = {horizon: [] for horizon in horizons}

        if entry_date is None:
            for item in ranking_items:
                for horizon in horizons:
                    pending.append(
                        {
                            "ranking_date": ranking_date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "entry_not_matured",
                        }
                    )
            daily_rows.append(summarize_day(ranking_date_text, None, trades_by_horizon, pending, skipped, portfolio_observations))
            continue

        for item in ranking_items:
            stock_prices = price_index.get(item["stock_id"])
            if stock_prices is None:
                skipped.append({"ranking_date": ranking_date_text, "stock_id": item["stock_id"], "reason": "missing_price_history"})
                continue
            for horizon in horizons:
                holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, horizon)
                if holding_dates is None:
                    pending.append(
                        {
                            "ranking_date": ranking_date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "horizon_not_matured",
                            "entry_date": entry_date.isoformat(),
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
                            "entry_date": entry_date.isoformat(),
                            "expected_exit_date": holding_dates[-1].isoformat(),
                        }
                    )
                    continue
                outcome = run_backtest_replay.simulate_trade(
                    holding=holding,
                    fee_rate=args.fee_rate,
                    tax_rate=args.tax_rate,
                    slippage_rate=args.slippage_rate,
                )
                if outcome is None:
                    skipped.append(
                        {
                            "ranking_date": ranking_date_text,
                            "stock_id": item["stock_id"],
                            "horizon": horizon,
                            "reason": "invalid_ohlc_bar",
                        }
                    )
                    continue
                trade = {
                    "ranking_date": ranking_date_text,
                    "horizon": horizon,
                    **item,
                    "portfolio_weight": weights.get(item["stock_id"], 0.0),
                    **outcome,
                }
                trades.append(trade)
                trades_by_horizon[horizon].append(trade)

        for horizon, horizon_trades in trades_by_horizon.items():
            observation = run_backtest_replay.portfolio_observation(ranking_date_text, horizon, horizon_trades, weights)
            if observation is not None:
                portfolio_observations.append(observation)
        daily_rows.append(summarize_day(ranking_date_text, entry_date, trades_by_horizon, pending, skipped, portfolio_observations))

    summary = run_backtest_replay.summarize(trades, portfolio_observations)
    summary.update(
        {
            "ranking_day_count": len(files),
            "pending_count": len(pending),
            "skipped_count": len(skipped),
            "matured_ranking_day_count": len({item["ranking_date"] for item in trades}),
            "as_of_date": as_of_date.isoformat(),
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "OK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "contract": {
            "performance_review_only": True,
            "reads_existing_ranking_artifacts": True,
            "reads_existing_features_ohlc": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_model": False,
            "changes_clawd_message": False,
            "live_send": False,
            "promotion_ready": False,
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "ranking_files": [repo_path(path) for path in files],
            "top_n": args.top_n,
            "horizons": horizons,
            "entry_delay_trade_days": args.entry_delay_trade_days,
            "max_ranking_days": args.max_ranking_days,
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
                "max_position_weight": args.max_position_weight,
                "default_gross_exposure": args.default_gross_exposure,
            },
        },
        "summary": summary,
        "daily_rows": daily_rows,
        "trades": trades,
        "portfolio": {
            "observations": portfolio_observations,
            "equity_curve": run_backtest_replay.equity_curve(portfolio_observations),
        },
        "pending": pending,
        "skipped": skipped,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Daily Recommendation Performance - {payload['as_of_date']}",
        "",
        f"- ranking_days: `{payload['summary']['ranking_day_count']}`",
        f"- matured_ranking_days: `{payload['summary']['matured_ranking_day_count']}`",
        f"- trade_count: `{payload['summary']['trade_count']}`",
        f"- pending_count: `{payload['summary']['pending_count']}`",
        f"- skipped_count: `{payload['summary']['skipped_count']}`",
        "",
        "## Horizon Summary",
        "",
        "| Horizon | Trades | Avg Return | Hit Rate | Portfolio Buckets | Avg Portfolio Return |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    portfolio = payload["summary"].get("portfolio_by_horizon", {})
    for horizon, item in payload["summary"].get("by_horizon", {}).items():
        p_item = portfolio.get(horizon, {})
        lines.append(
            "| {h} | {n} | {avg:.2%} | {hit:.2%} | {pn} | {pavg:.2%} |".format(
                h=horizon,
                n=item["trade_count"],
                avg=item["avg_net_return"],
                hit=item["hit_rate"],
                pn=p_item.get("observation_count", 0),
                pavg=p_item.get("avg_portfolio_return", 0.0) or 0.0,
            )
        )
    lines.extend(
        [
            "",
            "## 邊界",
            "",
            "- 這是每日報牌後驗 ledger，不改 production ranking / model / Clawd message。",
            "- 未成熟 horizon 會列入 pending，不會用未來資料補值。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / f"daily_recommendation_performance_{payload['as_of_date']}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "as_of_date": payload["as_of_date"],
                "trade_count": payload["summary"]["trade_count"],
                "pending_count": payload["summary"]["pending_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
