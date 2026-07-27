#!/usr/bin/env python3
"""逐 ID 驗證 research map 與 weekend inventory 的 processed authority。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_map_contract import (
    apply_run_history,
    build_combo_registry,
    is_completed_v2_expansion_record,
    latest_by_combo,
    read_jsonl,
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "processed-id-authority-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify processed combination ID authority")
    parser.add_argument(
        "--run-history",
        default="artifacts/autonomous_research/run_history.jsonl",
    )
    parser.add_argument(
        "--topic-registry",
        default="artifacts/autonomous_research/topic_registry.json",
    )
    parser.add_argument(
        "--research-map",
        default="artifacts/research_map/research_fog_map_latest.json",
    )
    parser.add_argument(
        "--weekend-inventory",
        default=None,
    )
    parser.add_argument("--output", required=True)
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
    return json.loads(path.read_text(encoding="utf-8"))


def processed_sets(
    topics: list[dict[str, Any]],
    history_records: list[dict[str, Any]],
) -> dict[str, Any]:
    latest = latest_by_combo(history_records)
    base_scenarios = apply_run_history(build_combo_registry(topics), history_records)
    base_ids = {
        str(row["v2_combo_id"])
        for row in base_scenarios
        if row.get("status") != "pending"
    }
    completed_expansion_ids = {
        combo_id
        for combo_id, record in latest.items()
        if is_completed_v2_expansion_record(record)
    }
    research_map_ids = base_ids | completed_expansion_ids
    weekend_inventory_ids = base_ids | {
        combo_id
        for combo_id, record in latest.items()
        if is_completed_v2_expansion_record(record)
    }
    previous_inventory_ids = base_ids | {
        combo_id
        for combo_id in latest
        if "|regime_gate_" in combo_id
        and "|risk_guard_" in combo_id
        and "|entry_filter_" in combo_id
    }
    return {
        "research_map_ids": research_map_ids,
        "weekend_inventory_ids": weekend_inventory_ids,
        "previous_inventory_ids": previous_inventory_ids,
        "latest": latest,
    }


def build_payload(
    topics: list[dict[str, Any]],
    history_records: list[dict[str, Any]],
    map_payload: dict[str, Any],
    inventory_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    sets = processed_sets(topics, history_records)
    map_ids = sets["research_map_ids"]
    inventory_ids = sets["weekend_inventory_ids"]
    previous_ids = sets["previous_inventory_ids"]
    map_only = sorted(map_ids - inventory_ids)
    inventory_only = sorted(inventory_ids - map_ids)
    previous_only = sorted(previous_ids - map_ids)
    latest = sets["latest"]
    source_rows = [
        {
            "combo_id": combo_id,
            "status": latest[combo_id].get("status"),
            "artifact_path": latest[combo_id].get("artifact_path"),
            "source": latest[combo_id].get("source"),
            "dimensions": latest[combo_id].get("dimensions"),
        }
        for combo_id in previous_only
    ]
    map_count = int((map_payload.get("summary") or {}).get("expanded_processed") or 0)
    inventory_count = (
        int((inventory_payload.get("summary") or {}).get("current_processed_count") or 0)
        if inventory_payload is not None
        else len(inventory_ids)
    )
    checks = [
        {
            "name": "processed_id_symmetric_difference_empty",
            "ok": not map_only and not inventory_only,
            "value": {"map_only": map_only, "inventory_only": inventory_only},
        },
        {
            "name": "research_map_count_matches_authority",
            "ok": map_count == len(map_ids),
            "value": {"artifact": map_count, "authority": len(map_ids)},
        },
        {
            "name": "weekend_inventory_count_matches_authority",
            "ok": inventory_count == len(inventory_ids),
            "value": {"artifact": inventory_count, "authority": len(inventory_ids)},
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "OK" if all(check["ok"] for check in checks) else "FAILED",
        "summary": {
            "research_map_processed": len(map_ids),
            "weekend_inventory_processed": len(inventory_ids),
            "symmetric_difference": sorted(set(map_only) | set(inventory_only)),
            "pre_fix_inventory_minus_map": previous_only,
        },
        "pre_fix_source_rows": source_rows,
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    history_path = resolve_path(args.run_history)
    topic_registry_path = resolve_path(args.topic_registry)
    map_path = resolve_path(args.research_map)
    inventory_path = resolve_path(args.weekend_inventory) if args.weekend_inventory else None
    topic_payload = read_json(topic_registry_path)
    topics = (
        topic_payload.get("topics")
        if isinstance(topic_payload.get("topics"), list)
        else []
    )
    payload = build_payload(
        topics,
        read_jsonl(history_path),
        read_json(map_path),
        read_json(inventory_path) if inventory_path else None,
    )
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "summary": payload["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
