#!/usr/bin/env python3
"""建立 autonomous research 的遊戲化戰爭迷霧靜態地圖。

這個腳本只負責 CLI 與檔案 I/O；資料轉換與 HTML 呈現分別由獨立模組處理。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.research.fog_map_domain import (  # noqa: E402
    DEFAULT_SCENARIO_COUNT,
    FAMILY_CENTERS,
    FAMILY_GROUPS,
    SCHEMA_VERSION,
    STATUS_LEGEND,
    STATUS_PRIORITY,
    aggregate_nodes_from_scenarios,
    build_active_expansion_queue as build_active_expansion_queue_from_inputs,
    build_burn_down_progress as build_burn_down_progress_from_rollup,
    build_family_summary,
    build_mission_queue,
    build_nodes,
    build_payload as build_payload_from_inputs,
    build_unlit_representative_queue,
    classify_family,
    classify_status,
    clean_repoish_path,
    delta_summary,
    fixture_topics,
    node_position,
    outcome_by_topic_id,
    progress_bar,
    safe_number,
    safe_text,
    sanitize_action,
    scenario_summary,
    summary_from_nodes,
)
from app.research.fog_map_render import render_html, render_metric_card  # noqa: E402
from scripts.research_map_contract import (  # noqa: E402, F401
    apply_run_history,
    build_combo_registry,
    completed_v2_expansion_count,
    dimension_schema_payload,
    expanded_universe_total,
    infer_insight_level,
    latest_by_combo,
    progress_summary,
    read_jsonl,
    status_from_insight,
    v2_combo_id,
)


SOURCE_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_map"
WEEKEND_DIR = PROJECT_ROOT / "artifacts" / "weekend_training"
ACTIVE_EXPANSION_PARENT_PATH = (
    PROJECT_ROOT / "artifacts" / "research_reviews" / "liquidity_quality_strict_replay_2026-06-12.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build autonomous research fog-of-war dashboard")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
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
        return None


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_weekend_rollup_path(date: str) -> Path | None:
    dated = WEEKEND_DIR / f"weekend_training_rollup_{date}.json"
    if dated.exists():
        return dated
    pattern = re.compile(r"weekend_training_rollup_\d{4}-\d{2}-\d{2}\.json$")
    candidates = sorted(path for path in WEEKEND_DIR.glob("weekend_training_rollup_*.json") if pattern.match(path.name))
    return candidates[-1] if candidates else None


def build_burn_down_progress(date: str, expanded_total: int, executed_processed: int) -> dict[str, Any] | None:
    rollup_path = latest_weekend_rollup_path(date)
    if rollup_path is None:
        return None
    return build_burn_down_progress_from_rollup(
        read_json(rollup_path),
        source=repo_path(rollup_path),
        expanded_total=expanded_total,
        executed_processed=executed_processed,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def build_active_expansion_queue(
    topics: list[dict[str, Any]], records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return build_active_expansion_queue_from_inputs(
        topics,
        records,
        parent=read_json(ACTIVE_EXPANSION_PARENT_PATH),
        parent_evidence=repo_path(ACTIVE_EXPANSION_PARENT_PATH),
    )


def build_payload(date: str) -> dict[str, Any]:
    progress_path = SOURCE_DIR / f"research_campaign_progress_{date}.json"
    registry_path = SOURCE_DIR / "topic_registry.json"
    queue_path = SOURCE_DIR / "next_action_queue.json"
    history_path = SOURCE_DIR / "run_history.json"
    history_jsonl_path = SOURCE_DIR / "run_history.jsonl"
    rollup_path = latest_weekend_rollup_path(date)
    return build_payload_from_inputs(
        date,
        progress=read_json(progress_path),
        registry=read_json(registry_path),
        queue=read_json(queue_path),
        history=read_json(history_path),
        history_records=read_jsonl(history_jsonl_path),
        weekend_rollup=read_json(rollup_path) if rollup_path is not None else None,
        weekend_rollup_source=repo_path(rollup_path),
        active_expansion_parent=read_json(ACTIVE_EXPANSION_PARENT_PATH),
        active_expansion_parent_evidence=repo_path(ACTIVE_EXPANSION_PARENT_PATH),
        source_paths={
            "progress": repo_path(progress_path) if progress_path.exists() else None,
            "topic_registry": repo_path(registry_path) if registry_path.exists() else None,
            "run_history": repo_path(history_path) if history_path.exists() else None,
            "run_history_jsonl": repo_path(history_jsonl_path) if history_jsonl_path.exists() else None,
            "next_action_queue": repo_path(queue_path) if queue_path.exists() else None,
        },
    )


def main() -> int:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    if output_dir is None:
        raise RuntimeError("output directory resolution failed")
    payload = build_payload(args.date)
    json_path = output_dir / f"research_fog_map_{args.date}.json"
    latest_json_path = output_dir / "research_fog_map_latest.json"
    html_path = output_dir / "index.html"
    write_json(json_path, payload)
    write_json(latest_json_path, payload)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "source_mode": payload["source_mode"],
                "html": repo_path(html_path),
                "payload": repo_path(json_path),
                "latest": repo_path(latest_json_path),
                "total_topics": payload["summary"]["total_topics"],
                "processed_combos": payload["summary"]["processed_combos"],
                "expanded_universe_total": payload["summary"]["expanded_universe_total"],
                "expanded_processed": payload["summary"]["expanded_processed"],
                "expanded_progress_pct": payload["summary"]["expanded_progress_pct"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
