#!/usr/bin/env python3
"""驗證 weekend full-universe inventory artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from weekend_training_common import (
    UNSUPPORTED_CATEGORIES,
    inventory_paths,
    load_map,
    load_topics,
    repo_path,
    resolve_path,
    write_json,
)
from research_map_contract import expanded_universe_total


SCHEMA_VERSION = "weekend-universe-inventory-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify weekend universe inventory")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/weekend_universe_inventory_verification_latest.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    inventory = read_json(artifact)
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    fog_map = load_map()
    summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
    map_summary = fog_map.get("summary") if isinstance(fog_map.get("summary"), dict) else {}
    expected_total = expanded_universe_total(len(load_topics()))
    current_processed = sum(1 for row in records if row.get("current_status") != "PENDING")
    source_processed = summary.get("map_expanded_processed")
    source_pending = summary.get("map_expanded_pending")
    combo_ids = [str(row.get("combo_id") or "") for row in records]
    non_replay_without_reason = [
        row.get("combo_id")
        for row in records
        if row.get("burn_down_status") in {"EQUIVALENCE_INHERITED", "RULE_PRUNED", "UNSUPPORTED_INPUT"}
        and not (row.get("representative_combo_id") or row.get("prune_reason") or row.get("unsupported_reason"))
    ]
    unsupported_rows = [row for row in records if row.get("burn_down_status") == "UNSUPPORTED_INPUT"]
    category_counts = summary.get("unsupported_category_counts") if isinstance(summary.get("unsupported_category_counts"), dict) else {}
    burn_counts = summary.get("burn_down_status_counts") if isinstance(summary.get("burn_down_status_counts"), dict) else {}
    unsupported_missing_breakdown = [
        row.get("combo_id")
        for row in unsupported_rows
        if not row.get("unsupported_reason")
        or row.get("unsupported_category") not in UNSUPPORTED_CATEGORIES
        or not isinstance(row.get("can_be_unblocked"), bool)
        or not row.get("unblock_requirement")
    ]
    unsupported_category_sum = sum(int(value or 0) for value in category_counts.values())
    unknown_categories = sorted(str(key) for key in category_counts if str(key) not in UNSUPPORTED_CATEGORIES)
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": inventory.get("schema_version") == "weekend-universe-inventory.v1", "value": inventory.get("schema_version")},
        {"name": "inventory_count", "ok": len(records) == expected_total, "value": {"records": len(records), "expected": expected_total}},
        {"name": "summary_count_matches_records", "ok": summary.get("full_universe_total") == len(records), "value": summary.get("full_universe_total")},
        {"name": "current_processed_matches_source_snapshot", "ok": current_processed == source_processed, "value": {"inventory": current_processed, "source_snapshot": source_processed}},
        {"name": "remaining_matches_source_snapshot", "ok": len(records) - current_processed == source_pending, "value": {"inventory": len(records) - current_processed, "source_snapshot": source_pending}},
        {"name": "latest_map_not_behind_inventory_snapshot", "ok": int(map_summary.get("expanded_processed") or 0) >= current_processed, "value": {"inventory_snapshot": current_processed, "latest_map": map_summary.get("expanded_processed")}},
        {"name": "combo_ids_unique", "ok": len(combo_ids) == len(set(combo_ids)), "value": len(combo_ids) - len(set(combo_ids))},
        {"name": "all_have_equivalence_key", "ok": all(row.get("equivalence_key") for row in records), "value": len(records)},
        {"name": "non_replay_have_reason", "ok": not non_replay_without_reason, "value": non_replay_without_reason[:20]},
        {
            "name": "unsupported_breakdown_fields_present",
            "ok": not unsupported_missing_breakdown,
            "value": unsupported_missing_breakdown[:20],
        },
        {
            "name": "unsupported_category_counts_sum",
            "ok": unsupported_category_sum == len(unsupported_rows) == int(burn_counts.get("UNSUPPORTED_INPUT") or 0),
            "value": {
                "category_sum": unsupported_category_sum,
                "unsupported_rows": len(unsupported_rows),
                "burn_down_count": burn_counts.get("UNSUPPORTED_INPUT"),
            },
        },
        {
            "name": "unsupported_categories_known",
            "ok": not unknown_categories,
            "value": unknown_categories,
        },
        {"name": "production_impact", "ok": inventory.get("production_impact") == "NO_PRODUCTION_CHANGE", "value": inventory.get("production_impact")},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date,
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    default_artifact, _ = inventory_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
