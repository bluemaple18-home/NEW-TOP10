#!/usr/bin/env python3
"""批次彙整入場品質每日 shadow monitor。"""

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


SCHEMA_VERSION = "capital-entry-quality-daily-shadow-monitor-batch.v1"
FILTERS = ["all", "non_worsening", "improved_only"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build capital entry quality daily shadow monitor batch")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-ranking-files", type=int, default=40)
    parser.add_argument("--entry-quality-report", default="artifacts/model_experiments/capital_entry_quality_report_2026-06-03.json")
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def ranking_files(rankings_dir: Path, max_files: int | None) -> list[Path]:
    files = sorted(
        [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)],
        key=ranking_date,
    )
    return files[-max_files:] if max_files else files


def filter_passes(item: dict[str, Any], filter_name: str) -> bool:
    rank_delta = item.get("rank_delta")
    if filter_name == "all":
        return True
    if filter_name == "non_worsening":
        return rank_delta is None or float(rank_delta) >= 0
    if filter_name == "improved_only":
        return rank_delta is not None and float(rank_delta) > 0
    raise ValueError(f"未知 filter：{filter_name}")


def monitor_row(path: Path, rankings_dir: Path, top_n: int) -> dict[str, Any]:
    payload = build_candidate_persistence.build_payload(target_ranking=path, rankings_dir=rankings_dir, limit=top_n)
    items = payload.get("items", [])
    counts = {name: sum(1 for item in items if filter_passes(item, name)) for name in FILTERS}
    blocked = {name: len(items) - counts[name] for name in FILTERS}
    return {
        "ranking_date": ranking_date(path),
        "ranking_path": repo_path(path),
        "production_top10_count": len(items),
        "eligible_counts": counts,
        "blocked_counts": blocked,
        "balanced_eligible_stock_ids": [str(item.get("stock_id")).zfill(4) for item in items if filter_passes(item, "non_worsening")],
        "conservative_eligible_stock_ids": [str(item.get("stock_id")).zfill(4) for item in items if filter_passes(item, "improved_only")],
    }


def avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    production_counts = [float(row["production_top10_count"]) for row in rows]
    balanced_counts = [float(row["eligible_counts"]["non_worsening"]) for row in rows]
    conservative_counts = [float(row["eligible_counts"]["improved_only"]) for row in rows]
    return {
        "ranking_days": len(rows),
        "avg_production_top10_count": avg(production_counts),
        "avg_balanced_eligible_count": avg(balanced_counts),
        "avg_conservative_eligible_count": avg(conservative_counts),
        "balanced_has_any_days": sum(1 for value in balanced_counts if value > 0),
        "conservative_has_any_days": sum(1 for value in conservative_counts if value > 0),
        "balanced_empty_days": sum(1 for value in balanced_counts if value <= 0),
        "conservative_empty_days": sum(1 for value in conservative_counts if value <= 0),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rankings_dir = resolve_path(args.rankings_dir)
    report_path = resolve_path(args.entry_quality_report)
    entry_quality_report = read_json(report_path)
    rows = [monitor_row(path, rankings_dir, args.top_n) for path in ranking_files(rankings_dir, args.max_ranking_files)]
    summary = summarize(rows)
    if not rows:
        monitor_status = "BLOCKED_NO_RANKING_ROWS"
        status = "BLOCKED"
        blocked_reasons = ["no ranking rows"]
    elif int(summary["balanced_has_any_days"]) <= 0:
        monitor_status = "MONITOR_ACTIVE_NO_BALANCED_ELIGIBLE"
        status = "OK"
        blocked_reasons = []
    else:
        monitor_status = "MONITOR_ACTIVE_ENTRY_FILTER_DISTRIBUTION"
        status = "OK"
        blocked_reasons = []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "monitor_status": monitor_status,
        "blocked_reasons": blocked_reasons,
        "contract": {
            "operational_shadow_only": True,
            "changes_production_top10_membership": False,
            "changes_risk_adjusted_score": False,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "default_allowed": False,
            "uses_future_rankings_for_filters": False,
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "top_n": args.top_n,
            "max_ranking_files": args.max_ranking_files,
            "entry_quality_report": repo_path(report_path),
            "entry_quality_report_status": entry_quality_report.get("status"),
            "entry_quality_decision": entry_quality_report.get("decision"),
        },
        "summary": {
            **summary,
            "sample_policy": {
                "min_ranking_days": 20,
                "sample_ready_for_default_review": False,
                "reason": "CAPITAL-04 僅允許 shadow monitor；production change 需另走長期 replay / promotion review。",
            },
            "next_gate": "CONTINUE_DAILY_SHADOW_MONITOR",
        },
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Capital Entry Quality Daily Shadow Monitor Batch",
        "",
        f"- status: `{payload.get('status')}`",
        f"- monitor_status: `{payload.get('monitor_status')}`",
        f"- ranking_days: `{summary.get('ranking_days')}`",
        f"- avg_balanced_eligible_count: `{summary.get('avg_balanced_eligible_count')}`",
        f"- avg_conservative_eligible_count: `{summary.get('avg_conservative_eligible_count')}`",
        f"- next_gate: `{summary.get('next_gate')}`",
        "",
        "## Boundary",
        "",
        "- 只統計 entry eligibility shadow。",
        "- 不改正式 Top10 / ranking / Clawd / model。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"capital_entry_quality_daily_shadow_monitor_batch_{args.date}.json"
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
                "ranking_days": payload.get("summary", {}).get("ranking_days"),
                "avg_balanced_eligible_count": payload.get("summary", {}).get("avg_balanced_eligible_count"),
                "avg_conservative_eligible_count": payload.get("summary", {}).get("avg_conservative_eligible_count"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
