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

from research_map_contract import (
    apply_run_history,
    build_combo_registry,
    dimension_schema_payload,
    expanded_universe_total,
    progress_summary,
    read_jsonl,
)


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
    registry_rows = {
        row.get("topic_id"): row
        for row in read_json(OUTPUT_DIR / "topic_registry.json").get("topics", [])
        if row.get("topic_id")
    }
    topics_json = []
    for topic in topics:
        topic_json = module.topic_to_json(topic)
        current = registry_rows.get(topic.topic_id, {})
        topics_json.append({**topic_json, **current})
    combos = build_combo_registry(topics_json)
    history_jsonl_path = OUTPUT_DIR / "run_history.jsonl"
    history_records = read_jsonl(history_jsonl_path)
    scenarios = apply_run_history(combos, history_records)
    combo_summary = progress_summary(scenarios)
    dimension_schema = dimension_schema_payload()
    expanded_total = expanded_universe_total(len(topics_json))
    expanded_processed = combo_summary["explored_combos"]
    expanded_progress_pct = round(expanded_processed / expanded_total, 6) if expanded_total else 0.0

    by_topic = {row.get("topic_id"): row for row in topics_json}
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for scenario in scenarios:
        topic = by_topic.get(scenario.get("topic_id"), {})
        family_counts[topic_family(str(topic.get("candidate_dir") or ""))][str(scenario.get("status") or "pending")] += 1

    pending = [scenario for scenario in scenarios if scenario.get("status") == "pending"]
    followup = [scenario for scenario in scenarios if scenario.get("status") == "follow_up_signal"]
    rejected = [scenario for scenario in scenarios if scenario.get("status") == "rejected"]
    effective = [scenario for scenario in scenarios if scenario.get("status") in {"effective_insight", "next_stage_candidate", "breakthrough_candidate"}]
    pending = sorted(pending, key=lambda item: (str(item.get("topic_id")), int(item.get("scenario_index") or 0)))
    followup = sorted(followup, key=lambda item: str(item.get("finished_at") or ""), reverse=True)
    rejected = sorted(rejected, key=lambda item: str(item.get("finished_at") or ""), reverse=True)
    effective = sorted(effective, key=lambda item: str(item.get("finished_at") or ""), reverse=True)
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
            "total_topics": len(topics_json),
            "processed_topics": sum(1 for topic in topics_json if any(s.get("topic_id") == topic.get("topic_id") and s.get("status") != "pending" for s in scenarios)),
            "pending_topics": sum(1 for topic in topics_json if not any(s.get("topic_id") == topic.get("topic_id") and s.get("status") != "pending" for s in scenarios)),
            "followup_signal_topics": len({s.get("topic_id") for s in followup}),
            "rejected_topics": len({s.get("topic_id") for s in rejected}),
            "total_combos": combo_summary["total_combos"],
            "processed_combos": combo_summary["explored_combos"],
            "pending_combos": combo_summary["pending_combos"],
            "followup_signal_combos": combo_summary["followup_signal_combos"],
            "rejected_combos": combo_summary["rejected_combos"],
            "effective_insight_combos": combo_summary["effective_insight_combos"],
            "next_stage_combos": combo_summary["next_stage_combos"],
            "breakthrough_combos": combo_summary["breakthrough_combos"],
            "progress_pct": combo_summary["progress_pct"],
            "progress_bar": progress_bar(combo_summary["explored_combos"], combo_summary["total_combos"]),
            "status_counts": combo_summary["status_counts"],
            "base_universe_total": combo_summary["total_combos"],
            "base_processed": combo_summary["explored_combos"],
            "base_progress_pct": combo_summary["progress_pct"],
            "expanded_universe_total": expanded_total,
            "expanded_processed": expanded_processed,
            "expanded_pending": max(0, expanded_total - expanded_processed),
            "expanded_progress_pct": expanded_progress_pct,
            "dimension_schema_version": dimension_schema["version"],
            "dimension_values": dimension_schema["dimension_values"],
            "dimension_defaults": dimension_schema["default_coordinates"],
            "expanded_scenarios_per_topic": dimension_schema["expanded_scenarios_per_topic"],
            "expansion_multiplier": dimension_schema["expansion_multiplier"],
            "next_action": next_action,
            "next_batch_size": len(next_batch),
            "history_runs": len(history_records),
        },
        "dimension_schema": dimension_schema,
        "insights": {
            "followup_signals": [
                {
                    "combo_id": item["combo_id"],
                    "topic_id": item["topic_id"],
                    "dimensions": item["dimensions"],
                    "decision": item["decision"],
                    "artifact_path": item["artifact_path"],
                }
                for item in followup[:20]
            ],
            "largest_families": family_summary[:20],
            "recent_rejections": [
                {
                    "combo_id": item["combo_id"],
                    "topic_id": item["topic_id"],
                    "dimensions": item["dimensions"],
                    "decision": item["decision"],
                    "artifact_path": item["artifact_path"],
                }
                for item in rejected[:20]
            ],
            "effective_signals": [
                {
                    "combo_id": item["combo_id"],
                    "topic_id": item["topic_id"],
                    "dimensions": item["dimensions"],
                    "insight_level": item["insight_level"],
                    "artifact_path": item["artifact_path"],
                }
                for item in effective[:20]
            ],
        },
        "next_batch": [
            {
                "combo_id": item["combo_id"],
                "topic_id": item["topic_id"],
                "dimensions": item["dimensions"],
                "candidate_dir": item["candidate_dir"],
            }
            for item in next_batch
        ],
        "sources": {
            "topic_registry": "artifacts/autonomous_research/topic_registry.json",
            "run_history_jsonl": "artifacts/autonomous_research/run_history.jsonl",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Research Campaign Progress",
        "",
        f"- status: `{payload['status']}`",
        f"- base scan: `{summary['processed_combos']}/{summary['total_combos']}` combos ({summary['progress_pct']:.1%})",
        f"- full universe: `{summary['expanded_processed']}/{summary['expanded_universe_total']}` combos ({summary['expanded_progress_pct']:.2%})",
        f"- topics: `{summary['processed_topics']}/{summary['total_topics']}`",
        f"- pending combos: `{summary['pending_combos']}`",
        f"- followup signal combos: `{summary['followup_signal_combos']}`",
        f"- rejected combos: `{summary['rejected_combos']}`",
        f"- next action: `{summary['next_action']}`",
        f"- next batch size: `{summary['next_batch_size']}`",
        "",
        "## Follow-up Signals",
    ]
    for item in payload["insights"]["followup_signals"][:10]:
        lines.append(f"- `{item['combo_id']}` / `{item['decision']}` / `{item['artifact_path']}`")
    if not payload["insights"]["followup_signals"]:
        lines.append("- none")
    lines.extend(["", "## Next Batch"])
    for item in payload["next_batch"][:20]:
        lines.append(f"- `{item['combo_id']}` / topic `{item['topic_id']}`")
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
                "processed": payload["summary"]["processed_combos"],
                "total": payload["summary"]["total_combos"],
                "expanded_processed": payload["summary"]["expanded_processed"],
                "expanded_total": payload["summary"]["expanded_universe_total"],
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
