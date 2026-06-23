#!/usr/bin/env python3
"""驗證 weekend survivor deep replay artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from weekend_training_common import repo_path, resolve_path, rollup_paths, survivor_paths, write_json


SCHEMA_VERSION = "weekend-survivor-deep-replay-verification.v1"
REQUIRED_CHECKS = {
    "recent_100",
    "recent_6m",
    "available_long_window",
    "BIG_BULL_slice",
    "HIGH_CHOPPY_CONTEXT_slice",
    "RISK_OFF_PANIC_slice",
    "same_exit_ranking_isolation",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify weekend survivor deep replay")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/weekend_survivor_deep_replay_verification_latest.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    rollup_path, _ = rollup_paths(date)
    rollup = read_json(rollup_path)
    rollup_summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    missing_checks = [
        row.get("combo_id")
        for row in rows
        if not REQUIRED_CHECKS.issubset(set((row.get("checks") or {}).keys()))
    ]
    promotion_tokens = [
        row.get("combo_id")
        for row in rows
        if row.get("decision") == "PROMOTION_READY"
    ]
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == "weekend-survivor-deep-replay.v1", "value": payload.get("schema_version")},
        {"name": "rows_have_required_checks", "ok": not missing_checks, "value": missing_checks[:20]},
        {
            "name": "source_survivor_count_matches_rollup_next_stage",
            "ok": len(rows) == int(rollup_summary.get("next_stage_count") or 0),
            "value": {"rows": len(rows), "rollup_next_stage_count": rollup_summary.get("next_stage_count")},
        },
        {"name": "no_promotion_ready", "ok": not promotion_tokens, "value": promotion_tokens[:20]},
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
    default_artifact, _ = survivor_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
