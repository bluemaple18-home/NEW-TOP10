#!/usr/bin/env python3
"""建立 weekend full-universe inventory 與 equivalence map。"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from typing import Any

from research_map_contract import expanded_universe_total, v2_combo_id
from weekend_training_common import (
    MAP_PATH,
    PRODUCTION_IMPACT,
    REPLAY_READY_STATUSES,
    base_scenarios_by_v2_combo,
    count_by,
    current_status_from_base_scenario,
    current_status_from_record,
    equivalence_key,
    inventory_paths,
    is_default_coordinate,
    load_history,
    load_map,
    load_topics,
    now_utc,
    repo_path,
    rule_prune_reason,
    stage2_combo_ids,
    unsupported_detail,
    unsupported_reason,
    all_v2_dimensions,
    latest_by_combo,
    priority_score,
    write_json,
    write_text,
)


SCHEMA_VERSION = "weekend-universe-inventory.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build weekend universe inventory")
    parser.add_argument("--date", required=True)
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="輸出完整 records 陣列；大型 v2 universe 會產生數 GB JSON，預設關閉。",
    )
    return parser.parse_args()


def build_initial_rows(date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    topics = load_topics()
    fog_map = load_map()
    history = load_history()
    latest_records = latest_by_combo(history)
    base_by_v2 = base_scenarios_by_v2_combo(topics, history)
    stage2_ids = stage2_combo_ids(date)
    rows: list[dict[str, Any]] = []
    for topic in topics:
        for base_dimensions in __import__("research_map_contract").SCENARIO_DIMENSION_GRID:
            for dimensions in all_v2_dimensions(base_dimensions):
                combo_id = v2_combo_id(topic, dimensions)
                record = latest_records.get(combo_id)
                if record:
                    current_status = current_status_from_record(record)
                    source_artifact = record.get("artifact_path")
                elif is_default_coordinate(dimensions):
                    base_scenario = base_by_v2.get(combo_id)
                    current_status = current_status_from_base_scenario(base_scenario)
                    source_artifact = (base_scenario or {}).get("artifact_path") or repo_path(MAP_PATH)
                else:
                    current_status = "PENDING"
                    source_artifact = None

                unsupported = None if current_status != "PENDING" else unsupported_reason(topic, dimensions)
                unsupported_info = unsupported_detail(unsupported) if unsupported else None
                prune = None if current_status != "PENDING" or unsupported else rule_prune_reason(dimensions)
                eligible = current_status == "PENDING" and unsupported is None and prune is None
                row = {
                    "combo_id": combo_id,
                    "topic_id": topic.get("topic_id"),
                    "candidate_dir": topic.get("candidate_dir"),
                    "dimensions": dimensions,
                    "current_status": current_status,
                    "burn_down_status": current_status if current_status != "PENDING" else "PENDING_ASSIGNMENT",
                    "equivalence_key": equivalence_key(topic, dimensions),
                    "equivalence_group_size": 0,
                    "representative_combo_id": None,
                    "eligible_for_replay": eligible,
                    "prune_reason": prune,
                    "unsupported_reason": unsupported,
                    "unsupported_category": (unsupported_info or {}).get("unsupported_category"),
                    "can_be_unblocked": bool((unsupported_info or {}).get("can_be_unblocked", False)),
                    "unblock_requirement": (unsupported_info or {}).get("unblock_requirement"),
                    "source_artifact": source_artifact,
                    "priority_score": 0,
                    "production_impact": PRODUCTION_IMPACT,
                }
                row["priority_score"] = priority_score(row, stage2_ids)
                rows.append(row)
    return rows, fog_map


def assign_equivalence(rows: list[dict[str, Any]]) -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["equivalence_key"])].append(row)

    for group_rows in groups.values():
        group_rows.sort(key=lambda item: (item["current_status"] not in REPLAY_READY_STATUSES, -int(item.get("priority_score") or 0), item["combo_id"]))
        processed = next((row for row in group_rows if row["current_status"] in REPLAY_READY_STATUSES), None)
        eligible = [row for row in group_rows if row.get("eligible_for_replay")]
        representative = processed or (sorted(eligible, key=lambda item: (-int(item.get("priority_score") or 0), item["combo_id"]))[0] if eligible else None)
        representative_id = representative.get("combo_id") if representative else None
        for row in group_rows:
            row["equivalence_group_size"] = len(group_rows)
            row["representative_combo_id"] = representative_id
            if row["current_status"] != "PENDING":
                row["burn_down_status"] = row["current_status"]
            elif row.get("unsupported_reason"):
                row["burn_down_status"] = "UNSUPPORTED_INPUT"
            elif row.get("prune_reason"):
                row["burn_down_status"] = "RULE_PRUNED"
            elif representative_id and row["combo_id"] != representative_id:
                row["burn_down_status"] = "EQUIVALENCE_INHERITED"
            elif representative_id == row["combo_id"]:
                row["burn_down_status"] = "REPRESENTATIVE_REPLAY_REQUIRED"
            else:
                row["burn_down_status"] = "UNSUPPORTED_INPUT"
                row["unsupported_reason"] = "NO_SUPPORTED_REPRESENTATIVE"
                info = unsupported_detail(row["unsupported_reason"])
                row["unsupported_category"] = info["unsupported_category"]
                row["can_be_unblocked"] = info["can_be_unblocked"]
                row["unblock_requirement"] = info["unblock_requirement"]


def normalize_unsupported_details(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row.get("burn_down_status") != "UNSUPPORTED_INPUT":
            row["unsupported_category"] = None
            row["can_be_unblocked"] = False
            row["unblock_requirement"] = None
            continue
        info = unsupported_detail(str(row.get("unsupported_reason") or "UNSUPPORTED_OTHER"))
        row["unsupported_reason"] = info["unsupported_reason"]
        row["unsupported_category"] = info["unsupported_category"]
        row["can_be_unblocked"] = info["can_be_unblocked"]
        row["unblock_requirement"] = info["unblock_requirement"]


def build_payload(date: str, include_records: bool = False) -> dict[str, Any]:
    rows, fog_map = build_initial_rows(date)
    assign_equivalence(rows)
    normalize_unsupported_details(rows)
    current_counts = count_by(rows, "current_status")
    burn_counts = count_by(rows, "burn_down_status")
    unsupported_rows = [row for row in rows if row.get("burn_down_status") == "UNSUPPORTED_INPUT"]
    unsupported_category_counts = dict(sorted(Counter(str(row.get("unsupported_category") or "UNSUPPORTED_OTHER") for row in unsupported_rows).items()))
    unsupported_reason_counts = dict(sorted(Counter(str(row.get("unsupported_reason") or "UNSUPPORTED_OTHER") for row in unsupported_rows).items()))
    topics = load_topics()
    expected_total = expanded_universe_total(len(topics))
    processed_current = sum(count for status, count in current_counts.items() if status != "PENDING")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "source": {
            "research_map": repo_path(MAP_PATH),
            "run_history": "artifacts/autonomous_research/run_history.jsonl",
            "topic_registry": "artifacts/autonomous_research/topic_registry.json",
        },
        "summary": {
            "topic_count": len(topics),
            "full_universe_total": len(rows),
            "expected_full_universe_total": expected_total,
            "map_expanded_processed": (fog_map.get("summary") or {}).get("expanded_processed"),
            "map_expanded_pending": (fog_map.get("summary") or {}).get("expanded_pending"),
            "current_processed_count": processed_current,
            "current_remaining_count": len(rows) - processed_current,
            "current_status_counts": current_counts,
            "burn_down_status_counts": burn_counts,
            "unsupported_category_counts": unsupported_category_counts,
            "unsupported_reason_top_counts": dict(Counter(unsupported_reason_counts).most_common(20)),
            "unsupported_unblockable_count": sum(1 for row in unsupported_rows if row.get("can_be_unblocked") is True),
            "unsupported_non_unblockable_count": sum(1 for row in unsupported_rows if row.get("can_be_unblocked") is not True),
            "equivalence_group_count": len({row["equivalence_key"] for row in rows}),
            "representative_required_count": burn_counts.get("REPRESENTATIVE_REPLAY_REQUIRED", 0),
        },
        "contract": {
            "research_only": True,
            "does_not_execute_backtests": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "manual_progress_fill_allowed": False,
            "records_inline": include_records,
        },
    }
    if include_records:
        payload["records"] = rows
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Universe Inventory",
        "",
        f"- status: `{payload['status']}`",
        f"- full_universe_total: `{summary['full_universe_total']}`",
        f"- current_processed_count: `{summary['current_processed_count']}`",
        f"- current_remaining_count: `{summary['current_remaining_count']}`",
        f"- equivalence_group_count: `{summary['equivalence_group_count']}`",
        f"- representative_required_count: `{summary['representative_required_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Current Status Counts",
        "",
    ]
    for key, value in summary["current_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Burn-Down Assignment Counts", ""])
    for key, value in summary["burn_down_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Unsupported Category Counts", ""])
    for key, value in summary["unsupported_category_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Top Unsupported Reasons", ""])
    for key, value in list(summary["unsupported_reason_top_counts"].items())[:20]:
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "No production ranking, model, or Clawd live push changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args.date, include_records=args.include_records)
    json_path, md_path = inventory_paths(args.date)
    write_json(json_path, payload, compact=True)
    write_text(md_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "output": repo_path(json_path), "total": payload["summary"]["full_universe_total"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
