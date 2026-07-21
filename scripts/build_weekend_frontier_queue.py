#!/usr/bin/env python3
"""把 weekend inventory 轉成 frontier queue。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from weekend_training_common import (
    PRODUCTION_IMPACT,
    inventory_paths,
    now_utc,
    queue_paths,
    repo_path,
    resolve_path,
    write_json,
    write_text,
)


SCHEMA_VERSION = "weekend-frontier-queue.v1"
DEFAULT_MAX_REPRESENTATIVES = 144


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build weekend frontier queue")
    parser.add_argument("--date", required=True)
    parser.add_argument("--inventory", default=None)
    parser.add_argument("--max-representatives", type=int, default=DEFAULT_MAX_REPRESENTATIVES)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def queue_type(row: dict[str, Any], selected_representatives: set[str]) -> str:
    status = str(row.get("burn_down_status") or "")
    current = str(row.get("current_status") or "")
    if current != "PENDING":
        return "EQUIVALENCE_INHERIT"
    if status == "UNSUPPORTED_INPUT":
        return "UNSUPPORTED"
    if status == "RULE_PRUNED":
        return "RULE_PRUNE"
    if status == "EQUIVALENCE_INHERITED":
        return "EQUIVALENCE_INHERIT"
    if status == "REPRESENTATIVE_REPLAY_REQUIRED":
        return "REPRESENTATIVE_REPLAY" if row.get("combo_id") in selected_representatives else "DEFERRED_LOW_PRIORITY"
    return "UNSUPPORTED"


def queue_item(row: dict[str, Any], item_type: str) -> dict[str, Any]:
    item = {
        "combo_id": row.get("combo_id"),
        "topic_id": row.get("topic_id"),
        "candidate_dir": row.get("candidate_dir"),
        "dimensions": row.get("dimensions"),
        "queue_type": item_type,
        "current_status": row.get("current_status"),
        "burn_down_status": row.get("burn_down_status"),
        "equivalence_key": row.get("equivalence_key"),
        "representative_combo_id": row.get("representative_combo_id") or row.get("combo_id"),
        "priority_score": row.get("priority_score"),
        "rule_id": row.get("prune_reason") if item_type == "RULE_PRUNE" else None,
        "unsupported_reason": row.get("unsupported_reason") if item_type == "UNSUPPORTED" else None,
        "source_artifact": row.get("source_artifact"),
        "production_impact": PRODUCTION_IMPACT,
    }
    if item_type == "EQUIVALENCE_INHERIT" and not item.get("source_artifact"):
        item["inherit_reason"] = "same_equivalence_key_as_representative"
    elif item_type == "EQUIVALENCE_INHERIT":
        item["inherit_reason"] = "already_has_verifiable_status_or_same_equivalence_key"
    if item_type == "DEFERRED_LOW_PRIORITY":
        item["defer_reason"] = "bounded_representative_batch"
    return item


def build_bounded_payload(
    date: str,
    rows: list[dict[str, Any]],
    *,
    inventory_count: int,
    representative_required_count: int,
    max_representatives: int = DEFAULT_MAX_REPRESENTATIVES,
) -> dict[str, Any]:
    required = [row for row in rows if row.get("burn_down_status") == "REPRESENTATIVE_REPLAY_REQUIRED"]
    required.sort(key=lambda row: (-int(row.get("priority_score") or 0), str(row.get("combo_id") or "")))
    selected = required[: max(0, max_representatives)]
    items = [queue_item(row, "REPRESENTATIVE_REPLAY") for row in selected]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "contract": {
            "materialization_mode": "BOUNDED_REPRESENTATIVES",
            "full_records_written": False,
        },
        "policy": {
            "max_representatives": max_representatives,
            "representative_sort": "priority_score desc, combo_id asc",
            "no_unexecuted_combo_marked_executed": True,
        },
        "summary": {
            "inventory_count": inventory_count,
            "queue_count": len(items),
            "representative_required_count": representative_required_count,
            "representative_replay_count": len(items),
            "deferred_low_priority_count": max(0, representative_required_count - len(items)),
            "queue_type_counts": {"REPRESENTATIVE_REPLAY": len(items)} if items else {},
        },
        "items": items,
    }


def build_payload(date: str, inventory_path: Path, max_representatives: int) -> dict[str, Any]:
    inventory = read_json(inventory_path)
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    required = [row for row in records if row.get("burn_down_status") == "REPRESENTATIVE_REPLAY_REQUIRED"]
    required = sorted(required, key=lambda row: (-int(row.get("priority_score") or 0), str(row.get("combo_id") or "")))
    selected = {str(row.get("combo_id") or "") for row in required[: max(0, max_representatives)]}
    items: list[dict[str, Any]] = []
    for row in records:
        item_type = queue_type(row, selected)
        items.append(queue_item(row, item_type))

    counts = dict(sorted(Counter(str(row["queue_type"]) for row in items).items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "source": {"inventory": repo_path(inventory_path)},
        "contract": {
            "materialization_mode": "FULL_RECORDS",
            "full_records_written": True,
        },
        "policy": {
            "max_representatives": max_representatives,
            "representative_sort": "priority_score desc, combo_id asc",
            "no_unexecuted_combo_marked_executed": True,
        },
        "summary": {
            "inventory_count": len(records),
            "queue_count": len(items),
            "representative_replay_count": counts.get("REPRESENTATIVE_REPLAY", 0),
            "deferred_low_priority_count": counts.get("DEFERRED_LOW_PRIORITY", 0),
            "queue_type_counts": counts,
        },
        "items": items,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Frontier Queue",
        "",
        f"- status: `{payload['status']}`",
        f"- queue_count: `{summary['queue_count']}`",
        f"- representative_replay_count: `{summary['representative_replay_count']}`",
        f"- deferred_low_priority_count: `{summary['deferred_low_priority_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Queue Type Counts",
        "",
    ]
    for key, value in summary["queue_type_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## First Representatives", "", "| priority | combo_id |", "| ---: | --- |"])
    for item in [row for row in payload["items"] if row["queue_type"] == "REPRESENTATIVE_REPLAY"][:30]:
        lines.append(f"| {item.get('priority_score')} | `{item.get('combo_id')}` |")
    lines.extend(["", "No production ranking, model, or Clawd live push changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    default_inventory, _ = inventory_paths(args.date)
    inventory_path = resolve_path(args.inventory) or default_inventory
    payload = build_payload(args.date, inventory_path, args.max_representatives)
    json_path, md_path = queue_paths(args.date)
    write_json(json_path, payload, compact=True)
    write_text(md_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "output": repo_path(json_path), "representatives": payload["summary"]["representative_replay_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
