#!/usr/bin/env python3
"""驗證 canonical production baseline materialization smoke。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_production_baseline_materialization_smoke import (
    PROJECT_ROOT,
    SCHEMA_VERSION,
    TARGET_BASELINE_PATH,
    output_paths,
)
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json


VERIFY_SCHEMA_VERSION = "production-baseline-materialization-smoke-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production baseline materialization smoke")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/production_baseline_materialization_smoke_verification_latest.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def is_under(path_text: str | None, root: Path) -> bool:
    if not path_text:
        return False
    path = resolve_path(path_text)
    if path is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    checks_payload = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    staging = payload.get("staging") if isinstance(payload.get("staging"), dict) else {}
    text = json.dumps(payload, ensure_ascii=False)
    smoke_ok = payload.get("smoke_status") == "OK"
    staging_file = staging.get("staged_file")
    staging_output_dir = staging.get("staging_output_dir")
    blockers = payload.get("blocker_reasons") if isinstance(payload.get("blocker_reasons"), list) else []
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == SCHEMA_VERSION, "value": payload.get("schema_version")},
        {"name": "status_explicit", "ok": payload.get("smoke_status") in {"OK", "BLOCKED"}, "value": payload.get("smoke_status")},
        {"name": "production_impact", "ok": payload.get("production_impact") == PRODUCTION_IMPACT, "value": payload.get("production_impact")},
        {
            "name": "target_production_path_not_created",
            "ok": TARGET_BASELINE_PATH.exists() is False and checks_payload.get("production_baseline_path_created") is False,
            "value": {
                "path": repo_path(TARGET_BASELINE_PATH),
                "exists": TARGET_BASELINE_PATH.exists(),
                "payload": checks_payload.get("production_baseline_path_created"),
            },
        },
        {
            "name": "canonical_contract_defined",
            "ok": checks_payload.get("canonical_contract_defined") is True,
            "value": checks_payload.get("canonical_contract_defined"),
        },
        {
            "name": "ok_requires_source_provenance",
            "ok": (not smoke_ok) or checks_payload.get("source_provenance_ok") is True,
            "value": checks_payload.get("source_provenance_ok"),
        },
        {
            "name": "blocked_has_reason",
            "ok": smoke_ok or bool(blockers),
            "value": blockers,
        },
        {
            "name": "staging_only_when_ok",
            "ok": (not smoke_ok and not staging_file and not staging_output_dir)
            or (
                smoke_ok
                and is_under(staging_file, PROJECT_ROOT / "artifacts" / "weekend_training" / "staging" / "production_baseline_smoke")
                and is_under(staging_output_dir, PROJECT_ROOT / "artifacts" / "weekend_training" / "staging" / "production_baseline_smoke")
            ),
            "value": staging,
        },
        {
            "name": "blocked_does_not_claim_unlock",
            "ok": smoke_ok or int(summary.get("estimated_unlockable_combo_count") or 0) == 0,
            "value": summary.get("estimated_unlockable_combo_count"),
        },
        {"name": "no_promotion_ready", "ok": "PROMOTION_READY" not in text, "value": False},
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
    default_artifact, _ = output_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(
        json.dumps(
            {"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
