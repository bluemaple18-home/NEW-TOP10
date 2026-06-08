#!/usr/bin/env python3
"""固定股數回測的入榜持續性分析。

此腳本只讀歷史 ranking 與 fixed-share backtest artifact，不重跑模型、不修改
production ranking。績效分桶只使用 ranking 當天可知道的 consecutive streak，
完整 episode length 只作描述性統計，不能作交易決策特徵。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import build_candidate_persistence, run_backtest_replay  # noqa: E402


SCHEMA_VERSION = "fixed-share-persistence-analysis.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="analyze fixed-share Top10 persistence")
    parser.add_argument("--fixed-share", required=True)
    parser.add_argument("--rankings-dir", required=True)
    parser.add_argument("--variant", default="production")
    parser.add_argument("--top-n", type=int, default=10)
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


def streak_bucket(days: int | None) -> str:
    if days is None or days <= 0:
        return "unknown"
    if days == 1:
        return "1"
    if days <= 3:
        return "2-3"
    if days <= 5:
        return "4-5"
    if days <= 10:
        return "6-10"
    if days <= 20:
        return "11-20"
    return "21+"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def topn_by_date(rankings_dir: Path, top_n: int) -> list[tuple[str, list[dict[str, Any]]]]:
    rows = []
    for path in run_backtest_replay.ranking_files(rankings_dir, None):
        date_text = run_backtest_replay.ranking_date(path)
        rows.append((date_text, build_candidate_persistence.read_ranking(path, limit=top_n)))
    return rows


def episode_lengths(rows_by_date: list[tuple[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    active: dict[str, dict[str, Any]] = {}
    episodes: list[dict[str, Any]] = []
    for date_text, rows in rows_by_date:
        current_ids = {str(row["stock_id"]).zfill(4) for row in rows}
        for stock_id in list(active):
            if stock_id not in current_ids:
                item = active.pop(stock_id)
                episodes.append({**item, "end_date": item["last_date"], "censored_right": False})
        for row in rows:
            stock_id = str(row["stock_id"]).zfill(4)
            if stock_id not in active:
                active[stock_id] = {
                    "stock_id": stock_id,
                    "stock_name": row.get("stock_name"),
                    "start_date": date_text,
                    "last_date": date_text,
                    "length": 1,
                }
            else:
                active[stock_id]["last_date"] = date_text
                active[stock_id]["length"] += 1
    for item in active.values():
        episodes.append({**item, "end_date": item["last_date"], "censored_right": True})

    lengths = [int(item["length"]) for item in episodes]
    counter = Counter(streak_bucket(length) for length in lengths)
    return {
        "episode_count": len(episodes),
        "censored_right_count": sum(1 for item in episodes if item.get("censored_right")),
        "median_episode_days": float(pd.Series(lengths).median()) if lengths else None,
        "avg_episode_days": round(float(pd.Series(lengths).mean()), 4) if lengths else None,
        "max_episode_days": max(lengths) if lengths else None,
        "bucket_counts": dict(sorted(counter.items())),
        "top_longest": sorted(episodes, key=lambda item: int(item["length"]), reverse=True)[:15],
    }


def persistence_index(rows_by_date: list[tuple[str, list[dict[str, Any]]]], rankings_dir: Path, top_n: int) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for date_text, _ in rows_by_date:
        path = rankings_dir / f"ranking_{date_text}.csv"
        payload = build_candidate_persistence.build_payload(target_ranking=path, rankings_dir=rankings_dir, limit=top_n)
        for item in payload.get("items", []):
            index[(date_text, str(item.get("stock_id", "")).zfill(4))] = item
    return index


def enriched_trades(fixed_share: dict[str, Any], variant_label: str, persistence: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    trades = []
    for variant in fixed_share.get("variants", []):
        if variant.get("label") != variant_label:
            continue
        horizon = int(variant.get("horizon"))
        for trade in variant.get("trades", []):
            key = (str(trade.get("ranking_date")), str(trade.get("stock_id", "")).zfill(4))
            item = persistence.get(key, {})
            days = int(item["consecutive_ranked_days"]) if item.get("consecutive_ranked_days") is not None else None
            trades.append(
                {
                    **trade,
                    "horizon": horizon,
                    "consecutive_ranked_days": days,
                    "streak_bucket": streak_bucket(days),
                    "rank_delta": item.get("rank_delta"),
                    "ranked_history_count": item.get("ranked_history_count"),
                }
            )
    return trades


def metric_summary(group: pd.DataFrame) -> dict[str, Any]:
    pnl = pd.to_numeric(group["net_pnl"], errors="coerce")
    buy = pd.to_numeric(group["buy_cash"], errors="coerce")
    returns = pd.to_numeric(group["net_return"], errors="coerce")
    total_pnl = float(pnl.sum())
    total_buy = float(buy.sum())
    return {
        "trade_count": int(len(group)),
        "ranking_day_count": int(group["ranking_date"].nunique()),
        "total_buy_cash": round(total_buy, 2),
        "total_net_pnl": round(total_pnl, 2),
        "return_on_buy_cash": round(total_pnl / total_buy, 6) if total_buy else None,
        "avg_trade_net_return": round(float(returns.mean()), 6),
        "median_trade_net_return": round(float(returns.median()), 6),
        "win_rate": round(float((returns > 0).mean()), 6),
    }


def summarize_trade_persistence(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trade_count": 0, "by_horizon_and_streak": {}, "asof_streak_distribution": {}}
    frame = pd.DataFrame(trades)
    by_horizon_and_streak = {}
    for (horizon, bucket), group in frame.groupby(["horizon", "streak_bucket"], dropna=False):
        by_horizon_and_streak[f"{int(horizon)}D::{bucket}"] = metric_summary(group)
    distribution = {}
    current = frame.drop_duplicates(["ranking_date", "stock_id"])
    for bucket, group in current.groupby("streak_bucket", dropna=False):
        distribution[str(bucket)] = {
            "row_count": int(len(group)),
            "share": round(float(len(group) / len(current)), 6),
        }
    return {
        "trade_count": int(len(frame)),
        "ranking_row_count": int(len(current)),
        "by_horizon_and_streak": by_horizon_and_streak,
        "asof_streak_distribution": distribution,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    fixed_path = resolve_path(args.fixed_share)
    rankings_dir = resolve_path(args.rankings_dir)
    fixed_share = load_json(fixed_path)
    rows_by_date = topn_by_date(rankings_dir, args.top_n)
    persistence = persistence_index(rows_by_date, rankings_dir, args.top_n)
    trades = enriched_trades(fixed_share, args.variant, persistence)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "episode_length_is_descriptive_only": True,
            "performance_uses_asof_consecutive_ranked_days": True,
            "uses_future_rankings_for_performance_buckets": False,
            "model_changes": False,
            "production_changes": False,
        },
        "inputs": {
            "fixed_share": repo_path(fixed_path),
            "rankings_dir": repo_path(rankings_dir),
            "variant": args.variant,
            "top_n": args.top_n,
            "ranking_file_count": len(rows_by_date),
        },
        "episode_summary": episode_lengths(rows_by_date),
        "trade_summary": summarize_trade_persistence(trades),
        "trades": trades,
    }


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


def money(value: Any) -> str:
    return f"{float(value):,.0f}"


def render_markdown(payload: dict[str, Any]) -> str:
    episode = payload["episode_summary"]
    lines = [
        "# Fixed Share Persistence Analysis",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- variant: {payload['inputs']['variant']}",
        f"- ranking files: {payload['inputs']['ranking_file_count']}",
        f"- model_changes: {payload['contract']['model_changes']}",
        f"- production_changes: {payload['contract']['production_changes']}",
        "",
        "## 入榜通常待幾天？",
        "",
        f"- episodes: {episode['episode_count']}",
        f"- median episode days: {episode['median_episode_days']}",
        f"- avg episode days: {episode['avg_episode_days']}",
        f"- max episode days: {episode['max_episode_days']}",
        f"- right-censored episodes: {episode['censored_right_count']}",
        "",
        "| Episode Bucket | Count |",
        "|---|---:|",
    ]
    for bucket, count in episode["bucket_counts"].items():
        lines.append(f"| {bucket} | {count} |")

    lines.extend(
        [
            "",
            "## 當天可知道的連續入榜分布",
            "",
            "| As-of Streak | Rows | Share |",
            "|---|---:|---:|",
        ]
    )
    for bucket, item in payload["trade_summary"]["asof_streak_distribution"].items():
        lines.append(f"| {bucket} | {item['row_count']} | {pct(item['share'])} |")

    lines.extend(
        [
            "",
            "## 固定 100 股獲利：依當天連續入榜天數",
            "",
            "| Group | Trades | Ranking Days | Buy Cash | Net PnL | Return On Buy Cash | Win Rate |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for key, item in sorted(payload["trade_summary"]["by_horizon_and_streak"].items()):
        lines.append(
            "| {key} | {trades} | {days} | {buy} | {pnl} | {ret} | {win} |".format(
                key=key,
                trades=item["trade_count"],
                days=item["ranking_day_count"],
                buy=money(item["total_buy_cash"]),
                pnl=money(item["total_net_pnl"]),
                ret=pct(item["return_on_buy_cash"]),
                win=pct(item["win_rate"]),
            )
        )
    lines.extend(
        [
            "",
            "## Longest Episodes",
            "",
            "| Stock | Name | Days | Start | End | Censored |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for item in episode["top_longest"]:
        lines.append(
            "| {stock} | {name} | {days} | {start} | {end} | {censored} |".format(
                stock=item["stock_id"],
                name=item.get("stock_name") or "",
                days=item["length"],
                start=item["start_date"],
                end=item["end_date"],
                censored=item["censored_right"],
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- episode length 是回頭描述一波完整連續入榜，不可拿來當當天交易特徵。",
            "- 獲利分桶只用 ranking 當天已知的 consecutive_ranked_days，避免後照鏡。",
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
        else PROJECT_ROOT / "artifacts" / "backtest" / f"fixed_share_persistence_analysis_{datetime.now().strftime('%Y-%m-%d')}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
