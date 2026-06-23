#!/usr/bin/env python3
"""驗證 weekend representative replay artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_map_contract import read_jsonl
from weekend_training_common import RUN_HISTORY_PATH, representative_paths, repo_path, resolve_path, write_json


SCHEMA_VERSION = "weekend-representative-replay-verification.v1"
REQUIRED_METRICS = {
    "return_delta",
    "drawdown_delta",
    "turnover_delta",
    "concentration_delta",
    "decision",
    "failure_reasons",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify weekend representative replay")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/weekend_representative_replay_verification_latest.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def history_alignment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    history = read_jsonl(RUN_HISTORY_PATH)
    by_combo = {str(row.get("combo_id") or ""): row for row in history if row.get("source") == "weekend_representative_replay"}
    missing = [
        row.get("combo_id")
        for row in rows
        if row.get("status") == "completed" and str(row.get("combo_id") or "") not in by_combo
    ]
    return {"history_count": len(by_combo), "missing": missing}


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    completed = [row for row in rows if row.get("status") == "completed"]
    missing_metrics = [
        row.get("combo_id")
        for row in completed
        if not REQUIRED_METRICS.issubset(set(row))
    ]
    alignment = history_alignment(completed)
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == "weekend-representative-replay.v1", "value": payload.get("schema_version")},
        {"name": "selected_lte_batch_size", "ok": len(rows) <= int((payload.get("summary") or {}).get("batch_size") or 0), "value": {"rows": len(rows), "batch_size": (payload.get("summary") or {}).get("batch_size")}},
        {"name": "completed_have_metrics", "ok": not missing_metrics, "value": missing_metrics[:20]},
        {"name": "run_history_alignment", "ok": not alignment["missing"], "value": alignment},
        {"name": "production_impact", "ok": payload.get("production_impact") == "NO_PRODUCTION_CHANGE", "value": payload.get("production_impact")},
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
    default_artifact, _ = representative_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
