#!/usr/bin/env python3
"""逐 ID 驗證 research map 與 weekend inventory 的 processed authority。"""

from __future__ import annotations

import argparse
import hashlib
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
MAP_SCHEMA = "research-fog-map.v2"
INVENTORY_SCHEMA = "weekend-universe-inventory.v1"
DIFFERENCE_SAMPLE_LIMIT = 20


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_processed_ids(
    payload: dict[str, Any],
    *,
    artifact_kind: str,
) -> tuple[set[str], list[str], list[str]]:
    if artifact_kind == "research_map":
        records = payload.get("processed_records")
        if not isinstance(records, list):
            scenarios = payload.get("scenarios")
            scenarios = scenarios if isinstance(scenarios, list) else []
            records = [
                {
                    "combo_id": row.get("v2_combo_id"),
                    "completion_status": row.get("run_status"),
                    "artifact_path": row.get("artifact_path"),
                }
                for row in scenarios
                if isinstance(row, dict)
            ]
            sources = payload.get("sources")
            sources = sources if isinstance(sources, dict) else {}
            history_value = sources.get("run_history_jsonl")
            if history_value:
                history_path = resolve_path(str(history_value))
                if history_path.is_file():
                    records.extend(read_jsonl(history_path))

        def completed(row: dict[str, Any]) -> bool:
            return (
                row.get("completion_status") == "completed"
                and bool(row.get("artifact_path"))
            ) or is_completed_v2_expansion_record(row)

    else:
        records = payload.get("processed_records")
        if not isinstance(records, list):
            records = payload.get("records")
        records = records if isinstance(records, list) else []

        def completed(row: dict[str, Any]) -> bool:
            return bool(
                row.get("completion_status") == "completed"
                and row.get("artifact_path")
            ) or (
                row.get("current_status") not in {None, "", "PENDING"}
                and bool(row.get("source_artifact"))
            )

    claimed = [
        str(row.get("combo_id") or "")
        for row in records
        if isinstance(row, dict) and completed(row)
    ]
    missing_ids = [
        f"row-{index}"
        for index, row in enumerate(records)
        if isinstance(row, dict) and completed(row) and not row.get("combo_id")
    ]
    duplicates = sorted(
        {combo_id for combo_id in claimed if combo_id and claimed.count(combo_id) > 1}
    )
    return {combo_id for combo_id in claimed if combo_id}, duplicates, missing_ids


def _source_hashes(payload: dict[str, Any]) -> dict[str, str]:
    source_hashes = payload.get("source_hashes")
    if (
        isinstance(source_hashes, dict)
        and bool(source_hashes)
        and all(
            isinstance(path, str)
            and bool(path)
            and isinstance(digest, str)
            and len(digest) == 64
            for path, digest in source_hashes.items()
        )
    ):
        return {str(path): str(digest) for path, digest in source_hashes.items()}
    declared = payload.get("sources")
    if not isinstance(declared, dict):
        declared = payload.get("source")
    if not isinstance(declared, dict):
        return {}
    resolved: dict[str, str] = {}
    for value in declared.values():
        if not isinstance(value, str) or not value:
            continue
        path = resolve_path(value)
        if path.is_file():
            resolved[repo_path(path)] = sha256(path)
    return resolved


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
    *,
    map_path: Path | None = None,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    sets = processed_sets(topics, history_records)
    map_ids, map_duplicates, map_missing_ids = _artifact_processed_ids(
        map_payload,
        artifact_kind="research_map",
    )
    inventory_payload = inventory_payload or {}
    inventory_ids, inventory_duplicates, inventory_missing_ids = _artifact_processed_ids(
        inventory_payload,
        artifact_kind="weekend_inventory",
    )
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
    inventory_count = int(
        (inventory_payload.get("summary") or {}).get("current_processed_count") or 0
    )
    map_only_sample = map_only[:DIFFERENCE_SAMPLE_LIMIT]
    inventory_only_sample = inventory_only[:DIFFERENCE_SAMPLE_LIMIT]
    map_source_hashes = _source_hashes(map_payload)
    inventory_source_hashes = _source_hashes(inventory_payload)
    checks = [
        {
            "name": "artifact_schemas",
            "ok": map_payload.get("schema_version") == MAP_SCHEMA
            and inventory_payload.get("schema_version") == INVENTORY_SCHEMA,
            "value": {
                "research_map": map_payload.get("schema_version"),
                "weekend_inventory": inventory_payload.get("schema_version"),
            },
        },
        {
            "name": "artifact_contracts",
            "ok": isinstance(map_payload.get("contract"), dict)
            and map_payload["contract"].get("progress_from_run_history_jsonl") is True
            and isinstance(inventory_payload.get("contract"), dict)
            and inventory_payload["contract"].get("manual_progress_fill_allowed") is False,
            "value": {
                "research_map": map_payload.get("contract"),
                "weekend_inventory": inventory_payload.get("contract"),
            },
        },
        {
            "name": "artifact_dates_match",
            "ok": bool(map_payload.get("date"))
            and map_payload.get("date") == inventory_payload.get("date"),
            "value": {
                "research_map": map_payload.get("date"),
                "weekend_inventory": inventory_payload.get("date"),
            },
        },
        {
            "name": "source_hash_lineage",
            "ok": bool(map_source_hashes) and bool(inventory_source_hashes),
            "value": {
                "research_map": map_source_hashes,
                "weekend_inventory": inventory_source_hashes,
            },
        },
        {
            "name": "processed_ids_unique_and_present",
            "ok": not (
                map_duplicates
                or inventory_duplicates
                or map_missing_ids
                or inventory_missing_ids
            ),
            "value": {
                "research_map_duplicates": map_duplicates[:DIFFERENCE_SAMPLE_LIMIT],
                "inventory_duplicates": inventory_duplicates[:DIFFERENCE_SAMPLE_LIMIT],
                "research_map_missing": map_missing_ids[:DIFFERENCE_SAMPLE_LIMIT],
                "inventory_missing": inventory_missing_ids[:DIFFERENCE_SAMPLE_LIMIT],
            },
        },
        {
            "name": "processed_id_symmetric_difference_empty",
            "ok": not map_only and not inventory_only,
            "value": {
                "map_only": map_only_sample,
                "inventory_only": inventory_only_sample,
            },
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
            "symmetric_difference_count": len(map_only) + len(inventory_only),
            "symmetric_difference": sorted(
                set(map_only_sample) | set(inventory_only_sample)
            ),
            "pre_fix_inventory_minus_map": previous_only,
        },
        "artifacts": {
            "research_map": {
                "path": repo_path(map_path) if map_path else None,
                "sha256": sha256(map_path) if map_path and map_path.is_file() else None,
                "schema_version": map_payload.get("schema_version"),
                "source_hashes": map_source_hashes,
                "processed_count": len(map_ids),
            },
            "weekend_inventory": {
                "path": repo_path(inventory_path) if inventory_path else None,
                "sha256": (
                    sha256(inventory_path)
                    if inventory_path and inventory_path.is_file()
                    else None
                ),
                "schema_version": inventory_payload.get("schema_version"),
                "source_hashes": inventory_source_hashes,
                "processed_count": len(inventory_ids),
            },
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
        map_path=map_path,
        inventory_path=inventory_path,
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
