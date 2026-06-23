#!/usr/bin/env python3
"""驗證 ranking dir unlock smoke。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_weekend_ranking_dir_unlock_smoke import SCHEMA_VERSION, smoke_paths
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json


VERIFY_SCHEMA_VERSION = "weekend-ranking-dir-unlock-smoke-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify ranking dir unlock smoke")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/weekend_ranking_dir_unlock_smoke_verification_latest.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == SCHEMA_VERSION, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "has_missing_rows", "ok": int(summary.get("ranking_dir_missing_count") or 0) > 0, "value": summary.get("ranking_dir_missing_count")},
        {"name": "has_missing_paths", "ok": int(summary.get("unique_missing_paths") or 0) > 0, "value": summary.get("unique_missing_paths")},
        {
            "name": "does_not_expand_without_artifacts",
            "ok": summary.get("can_expand_without_new_artifacts") is False,
            "value": summary.get("can_expand_without_new_artifacts"),
        },
        {"name": "decision", "ok": summary.get("decision") == "SMOKE_DONE_ARTIFACT_REQUIRED", "value": summary.get("decision")},
        {"name": "production_impact", "ok": payload.get("production_impact") == PRODUCTION_IMPACT, "value": payload.get("production_impact")},
        {"name": "no_promotion_ready", "ok": "PROMOTION_READY" not in json.dumps(payload, ensure_ascii=False), "value": False},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
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
    default_artifact, _ = smoke_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
