#!/usr/bin/env python3
"""Baseline harness host runner。

這支才是「自己跑」入口：讀 unlock policy，只執行 allowlist action，
跑完立即驗證並留下 host runner status / summary。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_SCHEMA_VERSION = "baseline-harness-host-runner-status.v1"
SUMMARY_SCHEMA_VERSION = "baseline-harness-host-runner-summary.v1"
POLICY_SCHEMA_VERSION = "baseline-harness-unlock-policy-review.v1"
ACTION_ID = "baseline_harness_medium_window_replay_100D"
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run controlled baseline harness host runner")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--policy", default=None)
    parser.add_argument("--action-id", default=ACTION_ID)
    parser.add_argument("--artifacts-dir", default="artifacts", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    run_date = str(args.date)
    host_dir = artifacts_dir / "host_runner" / run_date
    host_dir.mkdir(parents=True, exist_ok=True)
    status_path = host_dir / f"baseline_harness_host_runner_status_{run_date}.json"
    summary_path = host_dir / f"baseline_harness_host_runner_summary_{run_date}.json"
    lock_path = artifacts_dir / "host_runner" / "baseline_harness.lock"
    status = initial_status(args, status_path, summary_path)
    write_json(status_path, status)

    try:
        acquire_lock(lock_path, run_date)
        if FORBIDDEN_PRODUCTION_PATH.exists():
            raise RuntimeError(f"forbidden production path exists before run: {repo_relative(FORBIDDEN_PRODUCTION_PATH)}")
        policy_path = resolve_policy_path(args.policy, run_date)
        policy = read_json(policy_path)
        status["policy_path"] = repo_relative(policy_path)
        action = validate_policy(policy, args.action_id)
        status["policy_verified"] = True
        status["action"] = {
            "action_id": action["action_id"],
            "runner": action["runner"],
            "verifier": action["verifier"],
            "target_baseline_path": action["target_baseline_path"],
            "start_date": action["start_date"],
            "end_date": action["end_date"],
        }
        write_json(status_path, status)

        timeout = int(args.timeout_seconds or (policy.get("host_runner_policy") or {}).get("timeout_seconds") or 1800)
        runner_command = render_command(action["command_template"], run_date)
        verifier_command = render_command(action["verify_command_template"], run_date)
        status["runner_command"] = mask_command(runner_command)
        status["verifier_command"] = mask_command(verifier_command)
        if args.dry_run:
            status["status"] = "SKIPPED"
            status["notes"].append("dry_run: command not executed")
            write_json(status_path, status)
            write_summary(summary_path, status)
            return 0

        runner_result = run_command(runner_command, timeout)
        status["runner_result"] = result_payload(runner_result)
        write_json(status_path, status)
        if runner_result.exit_code != 0:
            raise RuntimeError(f"runner failed exit_code={runner_result.exit_code}")
        if FORBIDDEN_PRODUCTION_PATH.exists():
            raise RuntimeError(f"forbidden production path exists after runner: {repo_relative(FORBIDDEN_PRODUCTION_PATH)}")

        verifier_result = run_command(verifier_command, timeout)
        status["verifier_result"] = result_payload(verifier_result)
        if verifier_result.exit_code != 0:
            raise RuntimeError(f"verifier failed exit_code={verifier_result.exit_code}")
        if FORBIDDEN_PRODUCTION_PATH.exists():
            raise RuntimeError(f"forbidden production path exists after verifier: {repo_relative(FORBIDDEN_PRODUCTION_PATH)}")

        replay_artifact = artifacts_dir / "weekend_training" / f"baseline_harness_medium_window_replay_{run_date}.json"
        replay_verification = artifacts_dir / "weekend_training" / "baseline_harness_medium_window_replay_verification_latest.json"
        status["status"] = "OK"
        status["target_production_path_created"] = False
        status["replay_artifact"] = repo_relative(replay_artifact)
        status["replay_verification"] = repo_relative(replay_verification)
        status["production_impact"] = "NO_PRODUCTION_CHANGE"
        write_json(status_path, status)
        write_summary(summary_path, status)
        return 0
    except Exception as exc:
        status["status"] = "FAILED"
        status["notes"].append(str(exc))
        status["target_production_path_created"] = FORBIDDEN_PRODUCTION_PATH.exists()
        write_json(status_path, status)
        write_summary(summary_path, status)
        print(f"BASELINE_HARNESS_HOST_RUNNER_FAILED output={repo_relative(status_path)}", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        release_lock(lock_path)
        print(f"BASELINE_HARNESS_HOST_RUNNER_{status['status']} output={repo_relative(status_path)} summary={repo_relative(summary_path)}")


def initial_status(args: argparse.Namespace, status_path: Path, summary_path: Path) -> dict[str, Any]:
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "run_date": str(args.date),
        "status": "RUNNING",
        "dry_run": bool(args.dry_run),
        "action_id": args.action_id,
        "policy_path": None,
        "policy_verified": False,
        "action": None,
        "runner_command": None,
        "verifier_command": None,
        "runner_result": None,
        "verifier_result": None,
        "replay_artifact": None,
        "replay_verification": None,
        "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
        "production_impact": None,
        "host_runner_status_path": repo_relative(status_path),
        "host_runner_summary_path": repo_relative(summary_path),
        "notes": [],
    }


def validate_policy(policy: dict[str, Any], action_id: str) -> dict[str, Any]:
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise RuntimeError("policy schema mismatch")
    if policy.get("policy_review_status") != "OK" or policy.get("controlled_self_run_enabled") is not True:
        raise RuntimeError("policy does not enable controlled self-run")
    actions = policy.get("allowlist") if isinstance(policy.get("allowlist"), list) else []
    matches = [action for action in actions if isinstance(action, dict) and action.get("action_id") == action_id]
    if len(matches) != 1:
        raise RuntimeError(f"action is not uniquely allowlisted: {action_id}")
    action = matches[0]
    required = {
        "runner": "scripts/run_baseline_harness_medium_window_replay.py",
        "verifier": "scripts/verify_baseline_harness_medium_window_replay.py",
        "target_baseline_path": "artifacts/backtest/production_baseline_harness_medium_window",
        "start_date": "2025-12-24",
        "end_date": "2026-05-15",
    }
    for key, expected in required.items():
        if action.get(key) != expected:
            raise RuntimeError(f"allowlist {key} mismatch: {action.get(key)} != {expected}")
    if action.get("max_replay_grid_count") != 1 or action.get("estimated_unlockable_combo_count") != 0:
        raise RuntimeError("allowlist must stay bounded to one replay action and zero unlockable combos")
    return action


def resolve_policy_path(value: str | None, run_date: str) -> Path:
    if value:
        return resolve_path(Path(value))
    today_policy = PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_unlock_policy_review_{run_date}.json"
    if today_policy.exists():
        return today_policy
    return PROJECT_ROOT / "artifacts" / "weekend_training" / "baseline_harness_unlock_policy_review_2026-06-21.json"


def render_command(template: list[Any], run_date: str) -> list[str]:
    command = [str(part).format(run_date=run_date) for part in template]
    if any("artifacts/backtest/production" == part for part in command):
        raise RuntimeError("command attempts to target forbidden production path")
    return command


def run_command(command: list[str], timeout_seconds: int) -> CommandResult:
    started_at = now_utc()
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=timeout_seconds, check=False)
    return CommandResult(command, completed.returncode, completed.stdout.strip(), completed.stderr.strip(), started_at, now_utc())


def result_payload(result: CommandResult) -> dict[str, Any]:
    return {
        "command": mask_command(result.command),
        "exit_code": result.exit_code,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def write_summary(path: Path, status: dict[str, Any]) -> None:
    payload = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "run_date": status.get("run_date"),
        "status": status.get("status"),
        "action_id": status.get("action_id"),
        "policy_path": status.get("policy_path"),
        "policy_verified": status.get("policy_verified"),
        "replay_artifact": status.get("replay_artifact"),
        "replay_verification": status.get("replay_verification"),
        "target_production_path_created": status.get("target_production_path_created"),
        "production_impact": status.get("production_impact"),
        "notes": status.get("notes", []),
    }
    write_json(path, payload)


def acquire_lock(path: Path, run_date: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps({"run_date": run_date, "created_at": now_utc()}, ensure_ascii=False) + "\n")
    except FileExistsError as exc:
        raise RuntimeError(f"lockfile exists: {repo_relative(path)}") from exc


def release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def mask_command(command: list[str]) -> list[str]:
    return list(command)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
