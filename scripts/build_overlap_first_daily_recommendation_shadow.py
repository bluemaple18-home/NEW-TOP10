#!/usr/bin/env python3
"""產出 overlap-first 每日推薦影子稿。

這份 artifact 只把 production Top10 與 candidate trail10 Top10 合併成
「重複者優先」的觀察排序，不改正式 ranking / Clawd payload。
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "overlap-first-daily-recommendation-shadow.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build overlap-first daily recommendation shadow")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--production-ranking", default=None)
    parser.add_argument("--candidate-monitor", default=None)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def normalize_stock_id(value: Any) -> str:
    return str(value or "").strip().replace(".0", "").zfill(4)


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def production_ranking_path(args: argparse.Namespace) -> Path:
    if args.production_ranking:
        path = resolve_path(args.production_ranking)
        if path is None or not path.exists():
            raise FileNotFoundError(f"找不到 production ranking：{args.production_ranking}")
        return path
    path = PROJECT_ROOT / "artifacts" / f"ranking_{args.date}.csv"
    if not path.exists():
        raise FileNotFoundError(f"找不到 production ranking：{repo_path(path)}")
    return path


def candidate_monitor_path(args: argparse.Namespace) -> Path:
    if args.candidate_monitor:
        path = resolve_path(args.candidate_monitor)
        if path is None or not path.exists():
            raise FileNotFoundError(f"找不到 candidate monitor：{args.candidate_monitor}")
        return path
    path = PROJECT_ROOT / "artifacts" / "model_experiments" / f"candidate_trail10_daily_shadow_monitor_{args.date}.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到 candidate monitor：{repo_path(path)}")
    return path


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for rank, row in enumerate(csv.DictReader(handle), start=1):
            if rank > top_n:
                break
            normalized = dict(row)
            normalized["rank"] = rank
            normalized["stock_id"] = normalize_stock_id(normalized.get("stock_id"))
            rows.append(normalized)
    return rows


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_production_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": row.get("rank"),
        "stock_id": row.get("stock_id"),
        "stock_name": row.get("stock_name"),
        "close": to_float(row.get("close")),
        "return_pct": to_float(row.get("return_pct")),
        "limit_state": row.get("limit_state"),
        "tape_guard_action": row.get("tape_guard_action"),
        "rr_guard_action": row.get("rr_guard_action"),
        "risk_reward_score": to_float(row.get("risk_reward_score")),
        "risk_adjusted_score": to_float(row.get("risk_adjusted_score")),
        "model_prob": to_float(row.get("model_prob")),
        "market_regime": row.get("market_regime"),
    }


def candidate_top10(monitor: dict[str, Any]) -> list[dict[str, Any]]:
    rows = monitor.get("candidate_top10")
    if not isinstance(rows, list):
        return []
    output = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["rank"] = int(item.get("rank") or index)
        item["stock_id"] = normalize_stock_id(item.get("stock_id"))
        output.append(item)
    return output


def trail_plan_map(monitor: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plans = monitor.get("trail10_trade_plans")
    if not isinstance(plans, list):
        return {}
    return {
        normalize_stock_id(row.get("stock_id")): row
        for row in plans
        if isinstance(row, dict) and row.get("stock_id")
    }


def stock_name(prod: dict[str, Any] | None, cand: dict[str, Any] | None) -> str | None:
    return (prod or {}).get("stock_name") or (cand or {}).get("stock_name")


def build_item(
    stock_id: str,
    bucket: str,
    prod: dict[str, Any] | None,
    cand: dict[str, Any] | None,
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    production_rank = int(prod["rank"]) if prod and prod.get("rank") else None
    candidate_rank = int(cand["rank"]) if cand and cand.get("rank") else None
    if bucket == "overlap_high_confidence":
        role = "priority_observation"
        rationale = "正式榜和 candidate 榜同時選到，優先放前面觀察。"
    elif bucket == "candidate_trail10_only":
        role = "candidate_observation"
        rationale = "candidate 榜選到且有 trail10 風控計畫，但正式榜未選到，先當候補觀察。"
    elif bucket == "production_baseline_only":
        role = "baseline_watch"
        rationale = "正式榜選到但 candidate 榜未選到，保留 baseline 觀察，信心低於重複股。"
    else:
        role = "candidate_watch_no_trail10"
        rationale = "candidate 榜選到但未進 Top7 trail10 計畫，排在 baseline 之後，只作補位觀察。"
    return {
        "stock_id": stock_id,
        "stock_name": stock_name(prod, cand),
        "selection_bucket": bucket,
        "recommendation_role": role,
        "rationale": rationale,
        "production_rank": production_rank,
        "candidate_rank": candidate_rank,
        "rank_blend_key": (
            (production_rank if production_rank is not None else 99)
            + (candidate_rank if candidate_rank is not None else 99)
        )
        / 2,
        "production": compact_production_row(prod) if prod else None,
        "candidate": cand,
        "trail10_plan": plan,
        "has_trail10_plan": plan is not None,
    }


def order_overlap_first(
    production_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    plans: dict[str, dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    production_by_id = {row["stock_id"]: row for row in production_rows}
    candidate_by_id = {row["stock_id"]: row for row in candidate_rows}
    production_ids = [row["stock_id"] for row in production_rows]
    candidate_ids = [row["stock_id"] for row in candidate_rows]
    overlap_ids = [stock_id for stock_id in candidate_ids if stock_id in production_by_id]
    candidate_only_ids = [stock_id for stock_id in candidate_ids if stock_id not in production_by_id]
    production_only_ids = [stock_id for stock_id in production_ids if stock_id not in candidate_by_id]

    overlap = [
        build_item(stock_id, "overlap_high_confidence", production_by_id[stock_id], candidate_by_id[stock_id], plans.get(stock_id))
        for stock_id in overlap_ids
    ]
    overlap.sort(key=lambda row: (row["rank_blend_key"], row["candidate_rank"] or 99, row["production_rank"] or 99))

    candidate_only_with_trail10 = [
        build_item(stock_id, "candidate_trail10_only", None, candidate_by_id[stock_id], plans.get(stock_id))
        for stock_id in candidate_only_ids
        if stock_id in plans
    ]
    candidate_only_with_trail10.sort(key=lambda row: row["candidate_rank"] or 99)

    production_only = [
        build_item(stock_id, "production_baseline_only", production_by_id[stock_id], None, None)
        for stock_id in production_only_ids
    ]
    production_only.sort(key=lambda row: row["production_rank"] or 99)

    candidate_only_without_trail10 = [
        build_item(stock_id, "candidate_no_trail10_only", None, candidate_by_id[stock_id], None)
        for stock_id in candidate_only_ids
        if stock_id not in plans
    ]
    candidate_only_without_trail10.sort(key=lambda row: row["candidate_rank"] or 99)

    merged = [*overlap, *candidate_only_with_trail10, *production_only, *candidate_only_without_trail10][:top_n]
    for rank, row in enumerate(merged, start=1):
        row["shadow_rank"] = rank
    return merged


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_path = production_ranking_path(args)
    monitor_path = candidate_monitor_path(args)
    monitor = read_json(monitor_path)
    production_rows = read_ranking(production_path, args.top_n)
    candidate_rows = candidate_top10(monitor)[: args.top_n]
    plans = trail_plan_map(monitor)
    merged = order_overlap_first(production_rows, candidate_rows, plans, args.top_n)
    bucket_counts: dict[str, int] = {}
    for row in merged:
        bucket_counts[row["selection_bucket"]] = bucket_counts.get(row["selection_bucket"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "shadow_status": "READY_FOR_SHADOW_RECOMMENDATION_REVIEW",
        "contract": {
            "shadow_only": True,
            "overlap_first": True,
            "changes_production_top10_membership": False,
            "changes_risk_adjusted_score": False,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "production_switch_ready": False,
            "promotion_ready": False,
            "default_allowed": False,
        },
        "inputs": {
            "production_ranking": repo_path(production_path),
            "candidate_monitor": repo_path(monitor_path),
            "candidate_ranking": (monitor.get("inputs") or {}).get("candidate_ranking"),
            "top_n": args.top_n,
        },
        "selection_policy": {
            "name": "production_candidate_overlap_first_shadow",
            "bucket_order": [
                "overlap_high_confidence",
                "candidate_trail10_only",
                "production_baseline_only",
                "candidate_no_trail10_only",
            ],
            "interpretation": "兩套方法都選到的股票先排；candidate-only 需有 trail10 計畫才優先候補；production-only 保留 baseline 觀察；candidate 無 trail10 只補位。",
        },
        "summary": {
            "production_count": len(production_rows),
            "candidate_count": len(candidate_rows),
            "merged_count": len(merged),
            "overlap_count": bucket_counts.get("overlap_high_confidence", 0),
            "candidate_only_count": bucket_counts.get("candidate_trail10_only", 0),
            "production_only_count": bucket_counts.get("production_baseline_only", 0),
            "candidate_no_trail10_count": bucket_counts.get("candidate_no_trail10_only", 0),
            "trail10_plan_count": sum(1 for row in merged if row.get("has_trail10_plan")),
            "operator_note": "影子推薦稿；今天不改正式榜、不改推播。",
        },
        "overlap_first_top10": merged,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Overlap-First Daily Recommendation Shadow",
        "",
        f"- status: `{payload['status']}`",
        f"- shadow_status: `{payload['shadow_status']}`",
        f"- overlap_count: `{summary['overlap_count']}`",
        f"- candidate_only_count: `{summary['candidate_only_count']}`",
        f"- production_only_count: `{summary['production_only_count']}`",
        "",
        "| Shadow Rank | Bucket | Stock | Production Rank | Candidate Rank | Trail10 |",
        "|---:|---|---|---:|---:|---|",
    ]
    for row in payload["overlap_first_top10"]:
        lines.append(
            "| {rank} | {bucket} | {stock_id} {stock_name} | {prod} | {cand} | {trail} |".format(
                rank=row["shadow_rank"],
                bucket=row["selection_bucket"],
                stock_id=row["stock_id"],
                stock_name=row.get("stock_name") or "",
                prod=row.get("production_rank") or "",
                cand=row.get("candidate_rank") or "",
                trail="yes" if row.get("has_trail10_plan") else "no",
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- 不改正式 Top10。",
            "- 不改正式 ranking CSV。",
            "- 不改 Clawd 訊息。",
            "- 不改模型。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"overlap_first_daily_recommendation_shadow_{args.date}.json"
    )
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "shadow_status": payload["shadow_status"],
                "output": repo_path(output),
                "overlap_count": payload["summary"]["overlap_count"],
                "merged_count": payload["summary"]["merged_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
