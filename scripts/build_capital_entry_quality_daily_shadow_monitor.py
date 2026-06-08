#!/usr/bin/env python3
"""產出入場品質每日 shadow monitor。

用途：每日正式 ranking 產生後，檢查 Top10 若套用入場品質 filter
會留下哪些股票。這是 shadow entry eligibility，不改正式 Top10、score 或推播。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import build_candidate_persistence  # noqa: E402


SCHEMA_VERSION = "capital-entry-quality-daily-shadow-monitor.v1"
FILTERS = ["all", "non_worsening", "improved_only"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build capital entry quality daily shadow monitor")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--ranking", default=None, help="指定 ranking CSV；未指定時先找 artifacts/ranking_<date>.csv，再取最新")
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--top-n", type=int, default=10)
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


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def latest_ranking(rankings_dir: Path) -> Path | None:
    files = sorted(
        [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)],
        key=ranking_date,
    )
    return files[-1] if files else None


def select_ranking(args: argparse.Namespace) -> Path | None:
    if args.ranking:
        path = resolve_path(args.ranking)
        return path if path.exists() else None
    rankings_dir = resolve_path(args.rankings_dir)
    dated = rankings_dir / f"ranking_{args.date}.csv"
    if dated.exists():
        return dated
    return latest_ranking(rankings_dir)


def filter_passes(item: dict[str, Any], filter_name: str) -> bool:
    rank_delta = item.get("rank_delta")
    if filter_name == "all":
        return True
    if filter_name == "non_worsening":
        return rank_delta is None or float(rank_delta) >= 0
    if filter_name == "improved_only":
        return rank_delta is not None and float(rank_delta) > 0
    raise ValueError(f"未知 filter：{filter_name}")


def compact_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": item.get("rank"),
        "stock_id": item.get("stock_id"),
        "stock_name": item.get("stock_name"),
        "consecutive_ranked_days": item.get("consecutive_ranked_days"),
        "ranked_history_count": item.get("ranked_history_count"),
        "previous_rank": item.get("previous_rank"),
        "rank_delta": item.get("rank_delta"),
        "rank_delta_meaning": item.get("rank_delta_meaning"),
        "first_seen_date": item.get("first_seen_date"),
    }


def build_filter_group(items: list[dict[str, Any]], filter_name: str) -> dict[str, Any]:
    passed = [compact_item(item) for item in items if filter_passes(item, filter_name)]
    blocked = [compact_item(item) for item in items if not filter_passes(item, filter_name)]
    return {
        "filter": filter_name,
        "eligible_count": len(passed),
        "blocked_count": len(blocked),
        "eligible_stock_ids": [item["stock_id"] for item in passed],
        "blocked_stock_ids": [item["stock_id"] for item in blocked],
        "eligible_items": passed,
        "blocked_items": blocked,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    ranking = select_ranking(args)
    if ranking is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date": args.date,
            "status": "BLOCKED",
            "monitor_status": "BLOCKED_MISSING_RANKING",
            "blocked_reasons": ["ranking file missing"],
            "contract": contract(),
            "inputs": {"ranking": None, "rankings_dir": repo_path(resolve_path(args.rankings_dir)), "top_n": args.top_n},
            "summary": {},
            "filters": {},
        }

    payload = build_candidate_persistence.build_payload(
        target_ranking=ranking,
        rankings_dir=resolve_path(args.rankings_dir),
        limit=args.top_n,
    )
    items = payload.get("items", [])
    filters = {name: build_filter_group(items, name) for name in FILTERS}
    balanced = filters["non_worsening"]
    conservative = filters["improved_only"]
    if conservative["eligible_count"] > 0:
        monitor_status = "MONITOR_ACTIVE_CONSERVATIVE_ELIGIBLE"
    elif balanced["eligible_count"] > 0:
        monitor_status = "MONITOR_ACTIVE_BALANCED_ONLY"
    else:
        monitor_status = "MONITOR_ACTIVE_NO_SHADOW_ELIGIBLE"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "monitor_status": monitor_status,
        "blocked_reasons": [],
        "contract": contract(),
        "inputs": {
            "ranking": repo_path(ranking),
            "rankings_dir": repo_path(resolve_path(args.rankings_dir)),
            "top_n": args.top_n,
            "filters": FILTERS,
            "uses_future_rankings_for_filters": False,
        },
        "summary": {
            "ranking_date": ranking_date(ranking),
            "production_top10_count": len(filters["all"]["eligible_items"]),
            "balanced_shadow_filter": "non_worsening",
            "balanced_eligible_count": balanced["eligible_count"],
            "balanced_blocked_count": balanced["blocked_count"],
            "conservative_shadow_filter": "improved_only",
            "conservative_eligible_count": conservative["eligible_count"],
            "conservative_blocked_count": conservative["blocked_count"],
            "operator_note": "只做入場資格 shadow；正式 Top10、ranking CSV、Clawd 訊息皆不變。",
        },
        "filters": filters,
    }


def contract() -> dict[str, Any]:
    return {
        "operational_shadow_only": True,
        "changes_production_top10_membership": False,
        "changes_risk_adjusted_score": False,
        "changes_production_ranking": False,
        "changes_clawd_message": False,
        "changes_model": False,
        "default_allowed": False,
        "shadow_filters_change_entry_eligibility": True,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    filters = payload.get("filters", {})
    lines = [
        "# Capital Entry Quality Daily Shadow Monitor",
        "",
        f"- status: `{payload.get('status')}`",
        f"- monitor_status: `{payload.get('monitor_status')}`",
        f"- ranking_date: `{summary.get('ranking_date')}`",
        f"- production_top10_count: `{summary.get('production_top10_count')}`",
        f"- balanced_eligible_count: `{summary.get('balanced_eligible_count')}`",
        f"- conservative_eligible_count: `{summary.get('conservative_eligible_count')}`",
        "",
        "## Shadow Filters",
        "",
    ]
    for name in FILTERS:
        group = filters.get(name, {})
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- eligible_count: `{group.get('eligible_count')}`")
        lines.append(f"- blocked_count: `{group.get('blocked_count')}`")
        lines.append(f"- eligible_stock_ids: `{', '.join(group.get('eligible_stock_ids') or [])}`")
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "- 不改正式 Top10。",
            "- 不改 ranking CSV。",
            "- 不改 Clawd 訊息。",
            "- 不改模型。",
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
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"capital_entry_quality_daily_shadow_monitor_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "monitor_status": payload["monitor_status"],
                "output": repo_path(output),
                "ranking_date": payload.get("summary", {}).get("ranking_date"),
                "balanced_eligible_count": payload.get("summary", {}).get("balanced_eligible_count"),
                "conservative_eligible_count": payload.get("summary", {}).get("conservative_eligible_count"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
