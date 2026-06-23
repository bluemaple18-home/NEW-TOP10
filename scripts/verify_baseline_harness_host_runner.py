#!/usr/bin/env python3
"""驗證 baseline harness host runner 證據。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_SCHEMA_VERSION = "baseline-harness-host-runner-status.v1"
SUMMARY_SCHEMA_VERSION = "baseline-harness-host-runner-summary.v1"
STATUS_VALUES = {"OK", "FAILED", "SKIPPED", "RUNNING"}
ACTION_ID = "baseline_harness_medium_window_replay_100D"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify baseline harness host runner artifacts")
    parser.add_argument("--status", required=True, type=Path)
    parser.add_argument("--summary", default=None, type=Path)
    parser.add_argument("--require-success", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status_path = resolve_path(args.status)
    payload = read_json(status_path)
    errors = validate_status(payload, status_path, require_success=args.require_success)
    summary_path = resolve_path(args.summary) if args.summary else resolve_optional_path(payload.get("host_runner_summary_path"))
    if summary_path:
        if not summary_path.exists():
            errors.append(f"summary missing: {repo_relative(summary_path)}")
        else:
            errors.extend(validate_summary(read_json(summary_path), payload))
    if errors:
        print("BASELINE_HARNESS_HOST_RUNNER_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("BASELINE_HARNESS_HOST_RUNNER_OK")
    return 0


def validate_status(payload: Any, status_path: Path, *, require_success: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["root: must be object"]
    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        errors.append(f"schema_version: must be {STATUS_SCHEMA_VERSION}")
    check_enum(payload.get("status"), "status", STATUS_VALUES, errors)
    if require_success and payload.get("status") != "OK":
        errors.append(f"status: must be OK when --require-success is used, got {payload.get('status')}")
    if payload.get("action_id") != ACTION_ID:
        errors.append(f"action_id: expected {ACTION_ID}, got {payload.get('action_id')}")
    check_bool(payload.get("policy_verified"), "policy_verified", errors)
    check_bool(payload.get("target_production_path_created"), "target_production_path_created", errors)
    check_list(payload.get("notes"), "notes", errors)
    expected_status = repo_relative(status_path)
    if payload.get("host_runner_status_path") != expected_status:
        errors.append(f"host_runner_status_path: expected {expected_status}, got {payload.get('host_runner_status_path')}")
    if payload.get("status") == "OK":
        if payload.get("policy_verified") is not True:
            errors.append("policy_verified: must be true for OK")
        if payload.get("target_production_path_created") is not False:
            errors.append("target_production_path_created: must be false for OK")
        if payload.get("production_impact") != "NO_PRODUCTION_CHANGE":
            errors.append(f"production_impact: expected NO_PRODUCTION_CHANGE, got {payload.get('production_impact')}")
        check_existing_path(payload.get("replay_artifact"), "replay_artifact", errors)
        check_existing_path(payload.get("replay_verification"), "replay_verification", errors)
        runner = payload.get("runner_result") if isinstance(payload.get("runner_result"), dict) else {}
        verifier = payload.get("verifier_result") if isinstance(payload.get("verifier_result"), dict) else {}
        if runner.get("exit_code") != 0:
            errors.append(f"runner_result.exit_code: expected 0, got {runner.get('exit_code')}")
        if verifier.get("exit_code") != 0:
            errors.append(f"verifier_result.exit_code: expected 0, got {verifier.get('exit_code')}")
    return errors


def validate_summary(payload: Any, status: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["summary root: must be object"]
    if payload.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append(f"summary.schema_version: must be {SUMMARY_SCHEMA_VERSION}")
    for key in ("run_date", "status", "action_id", "policy_path", "policy_verified", "target_production_path_created", "production_impact"):
        if payload.get(key) != status.get(key):
            errors.append(f"summary.{key}: mismatch {payload.get(key)} != {status.get(key)}")
    return errors


def check_bool(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path}: must be boolean")


def check_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: must be list")


def check_enum(value: Any, path: str, allowed: set[str], errors: list[str]) -> None:
    if value not in allowed:
        errors.append(f"{path}: must be one of {sorted(allowed)}, got {value}")


def check_existing_path(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: must be non-empty path")
        return
    target = resolve_path(Path(value))
    if not target.exists():
        errors.append(f"{path}: missing on disk: {value}")


def resolve_optional_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return resolve_path(Path(value))


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
