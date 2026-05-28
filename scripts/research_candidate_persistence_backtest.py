#!/usr/bin/env python3
"""研究入榜天數對 production replay 結果的影響。

此腳本只讀 ranking artifacts 與 features parquet，不訓練模型、不重跑 ranking。
它把 `candidate_persistence` 的 consecutive_ranked_days 合併到 replay trades，
用來判斷入榜天數是否值得進一步成為 shadow feature。
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

from scripts import build_candidate_persistence, run_backtest_replay  # noqa: E402


SCHEMA_VERSION = "candidate-persistence-backtest.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="study candidate persistence against replay returns")
    parser.add_argument("--rankings-dir", default="artifacts", help="ranking_*.csv 所在目錄")
    parser.add_argument("--features", default="data/clean/features.parquet", help="features parquet，需含 OHLC")
    parser.add_argument("--horizons", default="1,3,5,10", help="持有期交易日數，例如 1,3,5,10")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-ranking-files", type=int, default=None)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--max-position-weight", type=float, default=0.2)
    parser.add_argument("--default-gross-exposure", type=float, default=0.65)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def replay_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        rankings_dir=args.rankings_dir,
        features=args.features,
        horizons=args.horizons,
        top_n=args.top_n,
        max_ranking_files=args.max_ranking_files,
        fee_rate=args.fee_rate,
        tax_rate=args.tax_rate,
        slippage_rate=args.slippage_rate,
        max_position_weight=args.max_position_weight,
        default_gross_exposure=args.default_gross_exposure,
        output=None,
    )


def persistence_index(ranking_files: list[str], rankings_dir: Path, limit: int) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for ranking_file in ranking_files:
        path = Path(ranking_file)
        payload = build_candidate_persistence.build_payload(target_ranking=path, rankings_dir=rankings_dir, limit=limit)
        date_text = str(payload["ranking_date"])
        for item in payload.get("items", []):
            stock_id = str(item.get("stock_id", "")).zfill(4)
            index[(date_text, stock_id)] = item
    return index


def streak_bucket(days: int | None) -> str:
    if days is None or days <= 0:
        return "unknown"
    if days == 1:
        return "1"
    if days <= 3:
        return "2-3"
    if days <= 5:
        return "4-5"
    return "6+"


def enrich_trades(trades: list[dict[str, Any]], persistence: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for trade in trades:
        key = (str(trade.get("ranking_date")), str(trade.get("stock_id", "")).zfill(4))
        item = persistence.get(key, {})
        days = int(item["consecutive_ranked_days"]) if item.get("consecutive_ranked_days") is not None else None
        rank_delta = item.get("rank_delta")
        enriched.append(
            {
                **trade,
                "consecutive_ranked_days": days,
                "streak_bucket": streak_bucket(days),
                "first_seen_date": item.get("first_seen_date"),
                "rank_delta": rank_delta,
            }
        )
    return enriched


def summarize(enriched_trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not enriched_trades:
        return {"trade_count": 0, "by_horizon_and_streak": {}, "by_rank_delta_direction": {}}
    frame = pd.DataFrame(enriched_trades)
    by_horizon_and_streak: dict[str, dict[str, Any]] = {}
    for (horizon, bucket), group in frame.groupby(["horizon", "streak_bucket"], dropna=False):
        returns = pd.to_numeric(group["net_return"], errors="coerce")
        key = f"{int(horizon)}D::{bucket}"
        by_horizon_and_streak[key] = metric_summary(group, returns)

    by_rank_delta_direction: dict[str, Any] = {}
    frame["rank_delta_direction"] = frame["rank_delta"].map(rank_delta_direction)
    for (horizon, direction), group in frame.groupby(["horizon", "rank_delta_direction"], dropna=False):
        returns = pd.to_numeric(group["net_return"], errors="coerce")
        key = f"{int(horizon)}D::{direction}"
        by_rank_delta_direction[key] = metric_summary(group, returns)

    return {
        "trade_count": int(len(frame)),
        "by_horizon_and_streak": by_horizon_and_streak,
        "by_rank_delta_direction": by_rank_delta_direction,
    }


def metric_summary(group: pd.DataFrame, returns: pd.Series) -> dict[str, Any]:
    return {
        "trade_count": int(len(group)),
        "avg_net_return": round(float(returns.mean()), 6),
        "median_net_return": round(float(returns.median()), 6),
        "hit_rate": round(float((returns > 0).mean()), 6),
        "avg_mae": round(float(pd.to_numeric(group["mae"], errors="coerce").mean()), 6),
        "avg_mfe": round(float(pd.to_numeric(group["mfe"], errors="coerce").mean()), 6),
    }


def rank_delta_direction(value: Any) -> str:
    if value is None or pd.isna(value):
        return "new_or_unknown"
    parsed = float(value)
    if parsed > 0:
        return "improved"
    if parsed < 0:
        return "worsened"
    return "unchanged"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    replay = run_backtest_replay.run_replay(replay_args(args))
    rankings_dir = resolve_path(args.rankings_dir)
    persistence = persistence_index(replay["inputs"]["ranking_files"], rankings_dir=rankings_dir, limit=args.top_n)
    enriched = enrich_trades(replay["trades"], persistence)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "source": "production_replay_trades + candidate_persistence",
            "uses_future_rankings": False,
            "model_feature": False,
            "decision": "research_only",
        },
        "inputs": {
            "rankings_dir": str(rankings_dir),
            "features": str(resolve_path(args.features)),
            "ranking_files": replay["inputs"]["ranking_files"],
            "top_n": args.top_n,
            "horizons": replay["inputs"]["horizons"],
        },
        "summary": summarize(enriched),
        "trades": enriched,
        "skipped": replay.get("skipped", []),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Candidate Persistence Backtest Study",
        "",
        f"- generated_at：{payload['generated_at']}",
        f"- ranking files：{len(payload['inputs']['ranking_files'])}",
        f"- trade_count：{payload['summary']['trade_count']}",
        "",
        "## Streak Buckets",
        "",
        "| Group | Trades | Avg Return | Median | Hit Rate | Avg MAE | Avg MFE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, item in sorted(payload["summary"]["by_horizon_and_streak"].items()):
        lines.append(summary_row(key, item))
    lines.extend(["", "## Rank Delta Direction", "", "| Group | Trades | Avg Return | Median | Hit Rate | Avg MAE | Avg MFE |", "|---|---:|---:|---:|---:|---:|---:|"])
    for key, item in sorted(payload["summary"]["by_rank_delta_direction"].items()):
        lines.append(summary_row(key, item))
    lines.append("")
    return "\n".join(lines)


def summary_row(key: str, item: dict[str, Any]) -> str:
    return "| {key} | {n} | {avg:.2%} | {med:.2%} | {hit:.2%} | {mae:.2%} | {mfe:.2%} |".format(
        key=key,
        n=item["trade_count"],
        avg=item["avg_net_return"],
        med=item["median_net_return"],
        hit=item["hit_rate"],
        mae=item["avg_mae"],
        mfe=item["avg_mfe"],
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    run_date = datetime.now().strftime("%Y-%m-%d")
    output_path = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "backtest" / f"persistence_study_{run_date}.json"
    md_path = output_path.with_suffix(".md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
