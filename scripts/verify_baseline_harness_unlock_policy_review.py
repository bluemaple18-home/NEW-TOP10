#!/usr/bin/env python3
"""驗證 baseline harness 自跑 unlock policy review。"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from weekend_training_common import PRODUCTION_IMPACT, now_utc, repo_path, resolve_path, write_json


SCHEMA_VERSION = "baseline-harness-unlock-policy-review-verification.v1"
POLICY_SCHEMA_VERSION = "baseline-harness-unlock-policy-review.v1"
ACTION_ID = "baseline_harness_medium_window_replay_100D"
TARGET_BASELINE_PATH = "artifacts/backtest/production_baseline_harness_medium_window"
FORBIDDEN_PRODUCTION_PATH = "artifacts/backtest/production"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify baseline harness unlock policy review")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/baseline_harness_unlock_policy_review_verification_latest.json")
    return parser.parse_args()


def artifact_path(run_date: str, override: str | None) -> Path:
    if override:
        path = resolve_path(override)
        assert path is not None
        return path
    path = resolve_path(f"artifacts/weekend_training/baseline_harness_unlock_policy_review_{run_date}.json")
    assert path is not None
    return path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def contains_forbidden_text(payload: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payload, ensure_ascii=False)


def build_payload(run_date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    allowlist = payload.get("allowlist") if isinstance(payload.get("allowlist"), list) else []
    allowed = allowlist[0] if allowlist and isinstance(allowlist[0], dict) else {}
    host_policy = payload.get("host_runner_policy") if isinstance(payload.get("host_runner_policy"), dict) else {}
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    production_path = resolve_path(FORBIDDEN_PRODUCTION_PATH)
    assert production_path is not None
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == POLICY_SCHEMA_VERSION, "value": payload.get("schema_version")},
        {"name": "policy_review_status_ok", "ok": payload.get("policy_review_status") == "OK", "value": payload.get("policy_review_status")},
        {"name": "controlled_self_run_enabled", "ok": payload.get("controlled_self_run_enabled") is True, "value": payload.get("controlled_self_run_enabled")},
        {"name": "single_allowlist_action", "ok": len(allowlist) == 1, "value": len(allowlist)},
        {"name": "action_id", "ok": allowed.get("action_id") == ACTION_ID, "value": allowed.get("action_id")},
        {"name": "target_path_exact", "ok": allowed.get("target_baseline_path") == TARGET_BASELINE_PATH, "value": allowed.get("target_baseline_path")},
        {"name": "window_exact", "ok": allowed.get("start_date") == "2025-12-24" and allowed.get("end_date") == "2026-05-15", "value": allowed},
        {"name": "bounded_counts", "ok": allowed.get("min_ranking_file_count") == 60 and allowed.get("max_ranking_file_count") == 120, "value": allowed},
        {"name": "no_grid_unlock", "ok": allowed.get("max_replay_grid_count") == 1 and allowed.get("estimated_unlockable_combo_count") == 0, "value": allowed},
        {
            "name": "host_runner_policy_present",
            "ok": host_policy.get("require_policy_ok") is True
            and host_policy.get("require_verifier_after_runner") is True
            and host_policy.get("write_status_and_summary") is True
            and host_policy.get("production_guard_path") == FORBIDDEN_PRODUCTION_PATH,
            "value": host_policy,
        },
        {
            "name": "production_guard",
            "ok": production_path.exists() is False and safety.get("target_production_path_created") is False,
            "value": {"path": repo_path(production_path), "exists": production_path.exists(), "payload": safety.get("target_production_path_created")},
        },
        {"name": "production_impact_no_change", "ok": safety.get("production_impact") == PRODUCTION_IMPACT, "value": safety.get("production_impact")},
        {"name": "no_promotion_ready", "ok": not contains_forbidden_text(payload), "value": False},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "verification_summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "controlled_self_run_enabled": payload.get("controlled_self_run_enabled"),
            "allowed_action_id": allowed.get("action_id"),
            "target_production_path_created": production_path.exists(),
            "production_impact": safety.get("production_impact"),
        },
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    artifact = artifact_path(str(args.date), args.artifact)
    output = resolve_path(args.output)
    assert output is not None
    payload = build_payload(str(args.date), artifact)
    write_json(output, payload)
    print(f"BASELINE_HARNESS_UNLOCK_POLICY_REVIEW_VERIFICATION_{payload['status']} output={repo_path(output)}")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
