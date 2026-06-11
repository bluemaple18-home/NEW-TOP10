#!/usr/bin/env python3
"""建立研究 campaign 的 backlog / progress / insight 報告。

這個腳本只盤點研究進度，不執行回測、不改模型、不改正式 ranking。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
SCHEMA_VERSION = "research-campaign-progress.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build autonomous research campaign progress")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--max-topics", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--min-ranking-files", type=int, default=3)
    parser.add_argument("--max-ranking-files", type=int, default=8)
    parser.add_argument("--baseline-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_autonomous_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "run_autonomous_research.py"
    spec = importlib.util.spec_from_file_location("run_autonomous_research", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("無法載入 run_autonomous_research.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def topic_family(candidate_dir: str) -> str:
    text = candidate_dir.lower()
    if "feature_group_sector" in text:
        return "feature_group_sector"
    if "sector_context" in text:
        return "sector_context"
    if "liquidity_quality" in text:
        return "liquidity_quality"
    if "candidate_subset" in text:
        return "candidate_subset"
    if "regime_guard" in text:
        return "regime_guard"
    if "big_bull" in text:
        return "big_bull"
    return Path(candidate_dir).name.split("_")[0] or "other"


def progress_bar(done: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "." * width
    filled = round(width * done / total)
    return "#" * filled + "." * (width - filled)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    module = load_autonomous_module()
    topic_args = SimpleNamespace(
        candidate_dir=None,
        baseline_dir=args.baseline_dir,
        min_ranking_files=args.min_ranking_files,
        max_topics=args.max_topics,
    )
    topics = module.generate_topics(topic_args)
    registry = {
        row.get("topic_id"): row
        for row in read_json(OUTPUT_DIR / "topic_registry.json").get("topics", [])
        if row.get("topic_id")
    }
    history = read_json(OUTPUT_DIR / "run_history.json").get("runs", [])

    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    followup: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for topic in topics:
        topic_json = module.topic_to_json(topic)
        current = registry.get(topic.topic_id, {})
        status = str(current.get("manager_status") or "candidate")
        run_count = int(current.get("run_count") or 0)
        last_decision = current.get("last_decision")
        family = topic_family(topic.candidate_dir)
        processed = run_count > 0 or status in {"rejected", "partial_needs_followup", "confirmed_for_next_replay", "blocked_missing_evidence"}
        row = {
            **topic_json,
            "family": family,
            "manager_status": status,
            "run_count": run_count,
            "last_decision": last_decision,
            "next_action": current.get("next_action"),
            "processed": processed,
        }
        rows.append(row)
        status_counts[status] += 1
        family_counts[family][status] += 1
        if status in {"partial_needs_followup", "confirmed_for_next_replay"}:
            followup.append(row)
        elif status == "rejected":
            rejected.append(row)
        elif not processed:
            pending.append(row)

    total = len(rows)
    processed_count = sum(1 for row in rows if row["processed"])
    pending = sorted(pending, key=lambda item: (-float(item.get("score") or 0), item["topic_id"]))
    followup = sorted(followup, key=lambda item: (-float(item.get("score") or 0), item["topic_id"]))
    rejected = sorted(rejected, key=lambda item: (-float(item.get("score") or 0), item["topic_id"]))
    next_batch = pending[: args.batch_size]

    if next_batch:
        next_action = "RUN_NEXT_BATCH"
    elif followup:
        next_action = "FOLLOWUP_EXISTING_SIGNALS"
    else:
        next_action = "GENERATE_MORE_TOPIC_UNIVERSE"

    family_summary = [
        {"family": family, "total": sum(counts.values()), "statuses": dict(sorted(counts.items()))}
        for family, counts in sorted(family_counts.items(), key=lambda item: (-sum(item[1].values()), item[0]))
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "does_not_execute_backtests": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "max_topics": args.max_topics,
            "batch_size": args.batch_size,
            "min_ranking_files": args.min_ranking_files,
            "max_ranking_files": args.max_ranking_files,
            "baseline_dir": args.baseline_dir,
        },
        "summary": {
            "total_topics": total,
            "processed_topics": processed_count,
            "pending_topics": len(pending),
            "followup_signal_topics": len(followup),
            "rejected_topics": len(rejected),
            "progress_pct": round(processed_count / total, 4) if total else 0.0,
            "progress_bar": progress_bar(processed_count, total),
            "status_counts": dict(sorted(status_counts.items())),
            "next_action": next_action,
            "next_batch_size": len(next_batch),
            "history_runs": len(history),
        },
        "insights": {
            "followup_signals": [
                {
                    "topic_id": item["topic_id"],
                    "family": item["family"],
                    "last_decision": item["last_decision"],
                    "next_action": item["next_action"],
                    "candidate_dir": item["candidate_dir"],
                }
                for item in followup[:20]
            ],
            "largest_families": family_summary[:20],
            "recent_rejections": [
                {
                    "topic_id": item["topic_id"],
                    "family": item["family"],
                    "last_decision": item["last_decision"],
                    "candidate_dir": item["candidate_dir"],
                }
                for item in rejected[:20]
            ],
        },
        "next_batch": [
            {
                "topic_id": item["topic_id"],
                "family": item["family"],
                "score": item["score"],
                "candidate_dir": item["candidate_dir"],
                "ranking_file_count": item["ranking_file_count"],
            }
            for item in next_batch
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Research Campaign Progress",
        "",
        f"- status: `{payload['status']}`",
        f"- progress: `{summary['progress_bar']}` `{summary['processed_topics']}/{summary['total_topics']}` ({summary['progress_pct']:.1%})",
        f"- pending: `{summary['pending_topics']}`",
        f"- followup signals: `{summary['followup_signal_topics']}`",
        f"- rejected: `{summary['rejected_topics']}`",
        f"- next action: `{summary['next_action']}`",
        f"- next batch size: `{summary['next_batch_size']}`",
        "",
        "## Follow-up Signals",
    ]
    for item in payload["insights"]["followup_signals"][:10]:
        lines.append(f"- `{item['topic_id']}` / `{item['family']}` / `{item['last_decision']}`")
    if not payload["insights"]["followup_signals"]:
        lines.append("- none")
    lines.extend(["", "## Next Batch"])
    for item in payload["next_batch"][:20]:
        lines.append(f"- `{item['topic_id']}` / `{item['family']}` / score `{item['score']}`")
    if not payload["next_batch"]:
        lines.append("- none")
    lines.extend(["", "## Family Summary"])
    for item in payload["insights"]["largest_families"][:12]:
        lines.append(f"- `{item['family']}` total `{item['total']}` statuses `{item['statuses']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = Path(args.output) if args.output else OUTPUT_DIR / f"research_campaign_progress_{args.date}.json"
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    payload = build_payload(args)
    write_text(output, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    write_text(output.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "progress": payload["summary"]["progress_bar"],
                "processed": payload["summary"]["processed_topics"],
                "total": payload["summary"]["total_topics"],
                "next_action": payload["summary"]["next_action"],
                "next_batch_size": payload["summary"]["next_batch_size"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
