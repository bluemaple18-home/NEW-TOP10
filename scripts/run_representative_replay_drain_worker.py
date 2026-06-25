#!/usr/bin/env python3
"""受控執行 representative replay drain。

這支 worker 只消費 weekend frontier queue 的 REPRESENTATIVE_REPLAY，
每批都 append run_history，接著重建 controlled-grid linkage 與 fog map。
它不改 production ranking、不訓練模型、不推 Discord。
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from top10_agent_status import build_event, write_agent_event
from weekend_training_common import PRODUCTION_IMPACT, queue_paths, representative_paths, repo_path, resolve_path, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "representative-replay-drain.v1"
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "docs" / "architecture" / "top10_harness_team.dashboard.json"


@dataclass
class CommandResult:
    name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="drain weekend representative replay queue")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifacts-dir", default=Path("artifacts"), type=Path)
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("TOP10_REPLAY_DRAIN_BATCH_SIZE", "24")))
    parser.add_argument("--max-batches", type=int, default=int(os.environ.get("TOP10_REPLAY_DRAIN_MAX_BATCHES", "6")))
    parser.add_argument("--max-seconds", type=int, default=int(os.environ.get("TOP10_REPLAY_DRAIN_MAX_SECONDS", "7200")))
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--force-append", action="store_true")
    parser.add_argument("--skip-initial-linkage", action="store_true")
    parser.add_argument("--lock-dir", default=Path("logs/representative_replay_drain.lock"), type=Path)
    parser.add_argument("--no-lock", action="store_true")
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(name: str, command: list[str]) -> CommandResult:
    started_at = now_utc()
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    return CommandResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout[-6000:],
        stderr=completed.stderr[-6000:],
        started_at=started_at,
        finished_at=now_utc(),
    )


def acquire_lock(lock_dir: Path) -> bool:
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    pid_path = lock_dir / "pid"
    try:
        lock_dir.mkdir()
    except FileExistsError:
        existing_pid = read_pid(pid_path)
        if existing_pid and process_alive(existing_pid):
            return False
        try:
            pid_path.unlink(missing_ok=True)
            lock_dir.rmdir()
            lock_dir.mkdir()
        except OSError:
            return False
    pid_path.write_text(str(os.getpid()) + "\n", encoding="utf-8")
    atexit.register(release_lock, lock_dir)
    return True


def release_lock(lock_dir: Path) -> None:
    pid_path = lock_dir / "pid"
    try:
        if read_pid(pid_path) == os.getpid():
            pid_path.unlink(missing_ok=True)
            lock_dir.rmdir()
    except OSError:
        pass


def read_pid(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, TypeError, ValueError):
        return None


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def queue_summary(date: str) -> dict[str, Any]:
    queue_path, _ = queue_paths(date)
    payload = read_json(queue_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    representative_count = int(summary.get("representative_replay_count") or 0)
    if representative_count == 0 and items:
        representative_count = sum(
            1
            for row in items
            if row.get("queue_type") == "REPRESENTATIVE_REPLAY" and row.get("current_status") == "PENDING"
        )
    return {
        "queue_path": repo_path(queue_path),
        "status": payload.get("status"),
        "representative_replay_count": representative_count,
        "deferred_low_priority_count": int(summary.get("deferred_low_priority_count") or 0),
        "queue_count": int(summary.get("queue_count") or len(items)),
    }


def command_payload(result: CommandResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "command": portable_command(result.command),
        "returncode": result.returncode,
        "status": "OK" if result.ok else "FAILED",
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "stdout_tail": result.stdout,
        "stderr_tail": result.stderr,
    }


def refresh_map_commands(run_date: str) -> list[CommandResult]:
    return [
        run_command("build_research_progress_after_replay", [python_bin(), "scripts/build_research_campaign_progress.py", "--date", run_date]),
        run_command("build_fog_map_after_replay", [python_bin(), "scripts/build_research_fog_map.py", "--date", run_date]),
    ]


def portable_command(command: list[str]) -> list[str]:
    portable: list[str] = []
    for part in command:
        path = Path(part)
        if path.is_absolute():
            portable.append(repo_path(path) or part)
        else:
            portable.append(part)
    return portable


def progress_path(artifacts_dir: Path, date: str) -> Path:
    return artifacts_dir / "weekend_training" / f"representative_replay_drain_{date}.json"


def build_progress(
    *,
    date: str,
    run_id: str,
    started_at: str,
    status: str,
    stop_reason: str,
    initial_queue: dict[str, Any],
    latest_queue: dict[str, Any],
    batches: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": now_utc(),
        "status": status,
        "stop_reason": stop_reason,
        "production_impact": PRODUCTION_IMPACT,
        "summary": {
            "initial_representative_replay_count": initial_queue.get("representative_replay_count"),
            "latest_representative_replay_count": latest_queue.get("representative_replay_count"),
            "batch_count": len(batches),
            "completed_replay_count": sum(int((batch.get("representative_summary") or {}).get("completed_count") or 0) for batch in batches),
            "appended_run_history_count": sum(int((batch.get("representative_summary") or {}).get("appended_run_history_count") or 0) for batch in batches),
            "failed_batch_count": sum(1 for batch in batches if batch.get("status") != "OK"),
        },
        "initial_queue": initial_queue,
        "latest_queue": latest_queue,
        "batches": batches,
        "errors": errors,
    }


def idle_stop_reason(latest_queue: dict[str, Any]) -> str:
    return "queue_empty" if int(latest_queue.get("representative_replay_count") or 0) <= 0 else "max_batches_reached"


def write_progress(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def write_research_worker_event(
    *,
    artifacts_dir: Path,
    run_id: str,
    run_date: str,
    status: str,
    decision: str,
    started_at: str,
    artifact_paths: list[Path],
    metrics: dict[str, Any],
    failure_reason: str | None = None,
    next_action: str | None = None,
) -> None:
    event = build_event(
        run_id=run_id,
        run_date=run_date,
        agent_id="research_worker",
        status=status,
        decision=decision,
        started_at=started_at,
        input_refs=[
            "artifacts/weekend_training/weekend_frontier_queue_%s.json" % run_date,
            "artifacts/autonomous_research/run_history.jsonl",
        ],
        artifact_paths=[repo_path(path) or str(path) for path in artifact_paths],
        failure_reason=failure_reason,
        next_action=next_action,
        metrics=metrics,
    )
    write_agent_event(event, artifacts_dir=artifacts_dir, manifest_path=DEFAULT_MANIFEST_PATH)


def main() -> int:
    args = parse_args()
    run_date = args.date
    run_id = args.run_id or f"replay-drain-{run_date}-{datetime.now().strftime('%H%M%S')}"
    artifacts_dir = resolve_path(args.artifacts_dir) or PROJECT_ROOT / "artifacts"
    lock_dir = resolve_path(args.lock_dir) or PROJECT_ROOT / "logs" / "representative_replay_drain.lock"
    if not args.no_lock and not acquire_lock(lock_dir):
        print(
            json.dumps(
                {
                    "status": "SKIPPED",
                    "output": None,
                    "stop_reason": "lock_held",
                    "lock_dir": repo_path(lock_dir),
                },
                ensure_ascii=False,
            )
        )
        return 0
    started_at = now_utc()
    deadline = time.monotonic() + max(0, args.max_seconds)
    progress = progress_path(artifacts_dir, run_date)
    batches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if not args.skip_initial_linkage:
        initial_refresh = refresh_map_commands(run_date)
        failed_initial_refresh = [result for result in initial_refresh if not result.ok]
        if failed_initial_refresh:
            initial_queue = queue_summary(run_date)
            payload = build_progress(
                date=run_date,
                run_id=run_id,
                started_at=started_at,
                status="FAILED",
                stop_reason="initial_map_refresh_failed",
                initial_queue=initial_queue,
                latest_queue=initial_queue,
                batches=[],
                errors=[command_payload(result) for result in failed_initial_refresh],
            )
            write_progress(progress, payload)
            write_research_worker_event(
                artifacts_dir=artifacts_dir,
                run_id=run_id,
                run_date=run_date,
                status="failed",
                decision="stop",
                started_at=started_at,
                artifact_paths=[progress],
                metrics=payload["summary"],
                failure_reason="initial fog map refresh failed",
                next_action="inspect research campaign progress / fog map build before replay drain",
            )
            print(json.dumps({"status": "FAILED", "output": repo_path(progress), "stop_reason": "initial_map_refresh_failed"}, ensure_ascii=False))
            return 1
        linkage = run_command("initial_controlled_grid_linkage", [python_bin(), "scripts/run_controlled_grid_drain_host_runner.py", "--date", run_date])
        if not linkage.ok:
            initial_queue = queue_summary(run_date)
            payload = build_progress(
                date=run_date,
                run_id=run_id,
                started_at=started_at,
                status="FAILED",
                stop_reason="initial_linkage_failed",
                initial_queue=initial_queue,
                latest_queue=initial_queue,
                batches=[],
                errors=[command_payload(linkage)],
            )
            write_progress(progress, payload)
            write_research_worker_event(
                artifacts_dir=artifacts_dir,
                run_id=run_id,
                run_date=run_date,
                status="failed",
                decision="stop",
                started_at=started_at,
                artifact_paths=[progress],
                metrics=payload["summary"],
                failure_reason="initial controlled-grid linkage failed",
                next_action="inspect controlled_grid_drain_host_runner status before replay drain",
            )
            print(json.dumps({"status": "FAILED", "output": repo_path(progress), "stop_reason": "initial_linkage_failed"}, ensure_ascii=False))
            return 1

    initial_queue = queue_summary(run_date)
    latest_queue = initial_queue
    stop_reason = "not_started"
    status = "OK"

    for batch_number in range(1, max(0, args.max_batches) + 1):
        if time.monotonic() >= deadline:
            stop_reason = "max_seconds_reached"
            break
        latest_queue = queue_summary(run_date)
        if latest_queue["representative_replay_count"] <= 0:
            stop_reason = "queue_empty"
            break

        replay_command = [
            python_bin(),
            "scripts/run_weekend_representative_replay.py",
            "--date",
            run_date,
            "--batch-size",
            str(args.batch_size),
            "--start-index",
            "0",
            "--append-run-history",
        ]
        if args.rerun:
            replay_command.append("--rerun")
        if args.force_append:
            replay_command.append("--force-append")
        replay = run_command(f"representative_replay_batch_{batch_number}", replay_command)
        map_refresh = refresh_map_commands(run_date)
        verify = run_command("verify_representative_replay", [python_bin(), "scripts/verify_weekend_representative_replay.py", "--date", run_date])
        linkage = run_command("controlled_grid_linkage_after_replay", [python_bin(), "scripts/run_controlled_grid_drain_host_runner.py", "--date", run_date])
        representative_json, _ = representative_paths(run_date)
        representative_payload = read_json(representative_json)
        batch_status = "OK" if replay.ok and all(result.ok for result in map_refresh) and verify.ok and linkage.ok else "FAILED"
        batch = {
            "batch": batch_number,
            "status": batch_status,
            "queue_before": latest_queue,
            "representative_artifact": repo_path(representative_json),
            "representative_summary": representative_payload.get("summary") if isinstance(representative_payload.get("summary"), dict) else {},
            "commands": [command_payload(replay), *[command_payload(result) for result in map_refresh], command_payload(verify), command_payload(linkage)],
            "queue_after": queue_summary(run_date),
        }
        batches.append(batch)
        latest_queue = batch["queue_after"]
        payload = build_progress(
            date=run_date,
            run_id=run_id,
            started_at=started_at,
            status="RUNNING" if batch_status == "OK" else "FAILED",
            stop_reason="running" if batch_status == "OK" else "batch_failed",
            initial_queue=initial_queue,
            latest_queue=latest_queue,
            batches=batches,
            errors=errors,
        )
        write_progress(progress, payload)
        if batch_status != "OK":
            status = "FAILED"
            stop_reason = "batch_failed"
            errors.append(batch)
            break

    if status == "OK" and stop_reason == "not_started":
        latest_queue = queue_summary(run_date)
        stop_reason = idle_stop_reason(latest_queue)

    final_payload = build_progress(
        date=run_date,
        run_id=run_id,
        started_at=started_at,
        status=status,
        stop_reason=stop_reason,
        initial_queue=initial_queue,
        latest_queue=latest_queue,
        batches=batches,
        errors=errors,
    )
    write_progress(progress, final_payload)
    event_status = "ok" if status == "OK" else "failed"
    write_research_worker_event(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        run_date=run_date,
        status=event_status,
        decision="pass" if status == "OK" else "stop",
        started_at=started_at,
        artifact_paths=[
            progress,
            PROJECT_ROOT / "artifacts" / "weekend_training" / f"weekend_representative_replay_{run_date}.json",
            PROJECT_ROOT / "artifacts" / "weekend_training" / "weekend_representative_replay_verification_latest.json",
            PROJECT_ROOT / "artifacts" / "research_map" / "research_fog_map_verification_latest.json",
        ],
        metrics=final_payload["summary"],
        failure_reason=None if status == "OK" else stop_reason,
        next_action=None if status == "OK" else "inspect representative replay batch errors before continuing drain",
    )
    print(json.dumps({"status": status, "output": repo_path(progress), "stop_reason": stop_reason, **final_payload["summary"]}, ensure_ascii=False))
    return 0 if status == "OK" else 1


def python_bin() -> str:
    configured = os.environ.get("TOP10_DAILY_PYTHON")
    if configured:
        return configured
    local = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(local) if local.exists() else "python3"


if __name__ == "__main__":
    raise SystemExit(main())
