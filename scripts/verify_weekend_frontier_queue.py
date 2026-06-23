#!/usr/bin/env python3
"""驗證 weekend frontier queue artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from weekend_training_common import inventory_paths, queue_paths, repo_path, resolve_path, write_json


SCHEMA_VERSION = "weekend-frontier-queue-verification.v1"
VALID_QUEUE_TYPES = {"REPRESENTATIVE_REPLAY", "EQUIVALENCE_INHERIT", "RULE_PRUNE", "UNSUPPORTED", "DEFERRED_LOW_PRIORITY"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify weekend frontier queue")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--inventory", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/weekend_frontier_queue_verification_latest.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(date: str, artifact: Path, inventory_path: Path) -> dict[str, Any]:
    queue = read_json(artifact)
    inventory = read_json(inventory_path)
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    missing_representatives = [
        row.get("combo_id")
        for row in items
        if row.get("queue_type") == "EQUIVALENCE_INHERIT" and not row.get("representative_combo_id")
    ]
    missing_rule_ids = [row.get("combo_id") for row in items if row.get("queue_type") == "RULE_PRUNE" and not row.get("rule_id")]
    unexecuted_marked_executed = [row.get("combo_id") for row in items if row.get("queue_type") == "EXECUTED_REPLAY"]
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": queue.get("schema_version") == "weekend-frontier-queue.v1", "value": queue.get("schema_version")},
        {"name": "queue_count_matches_inventory", "ok": len(items) == len(records), "value": {"queue": len(items), "inventory": len(records)}},
        {"name": "valid_queue_types", "ok": all(row.get("queue_type") in VALID_QUEUE_TYPES for row in items), "value": sorted({str(row.get("queue_type")) for row in items})},
        {"name": "representative_batch_bounded", "ok": sum(row.get("queue_type") == "REPRESENTATIVE_REPLAY" for row in items) <= int((queue.get("policy") or {}).get("max_representatives") or 0), "value": (queue.get("summary") or {}).get("representative_replay_count")},
        {"name": "inherit_points_to_representative", "ok": not missing_representatives, "value": missing_representatives[:20]},
        {"name": "rule_prune_has_rule_id", "ok": not missing_rule_ids, "value": missing_rule_ids[:20]},
        {"name": "no_unexecuted_marked_executed", "ok": not unexecuted_marked_executed, "value": unexecuted_marked_executed[:20]},
        {"name": "production_impact", "ok": queue.get("production_impact") == "NO_PRODUCTION_CHANGE", "value": queue.get("production_impact")},
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
    default_queue, _ = queue_paths(args.date)
    default_inventory, _ = inventory_paths(args.date)
    artifact = resolve_path(args.artifact) or default_queue
    inventory = resolve_path(args.inventory) or default_inventory
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact, inventory)
    write_json(output, payload)
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
