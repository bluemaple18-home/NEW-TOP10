#!/usr/bin/env python3
"""唯讀分類 Fog runtime health；不得把 supervisor 存活直接視為健康。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_FAILURE_STATUSES = {
    "RESTART_DENIED",
    "STOPPED",
    "CHILD_FAILED",
    "NO-GO",
    "OVERLAP_BLOCKED",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_start_token(ps_bin: str, pid: int) -> str | None:
    try:
        completed = subprocess.run(
            [ps_bin, "-o", "lstart=", "-p", str(pid)],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    token = completed.stdout.strip()
    return token if completed.returncode == 0 and token else None


def _active_child_identity(root: Path, ps_bin: str) -> tuple[int | None, str]:
    lock_dir = root / "logs" / "fog_research_worker.lock"
    pid_path = lock_dir / "pid"
    start_token_path = lock_dir / "start_token"
    if not lock_dir.is_dir():
        return None, "ABSENT"
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None, "STALE"
    if not _pid_alive(pid):
        return pid, "STALE"
    try:
        stored_token = start_token_path.read_text(encoding="utf-8").strip()
    except OSError:
        return pid, "UNKNOWN"
    actual_token = _process_start_token(ps_bin, pid)
    if not stored_token or actual_token is None:
        return pid, "UNKNOWN"
    if stored_token != actual_token:
        return pid, "STALE"
    return pid, "ACTIVE"


def _latest_progress(root: Path) -> tuple[str | None, float | None]:
    candidates = [
        path
        for path in (root / "logs").glob("fog_research_worker_*.log")
        if path.name != "fog_research_worker_bootstrap.log"
    ]
    if not candidates:
        return None, None
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    timestamp = latest.stat().st_mtime
    return (
        datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
        timestamp,
    )


def classify(
    root: Path,
    *,
    supervisor_pid: int | None,
    progress_max_age_seconds: float,
    ps_bin: str,
    now: float | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    receipt_path = root / "logs" / "storage_safety" / "fog-research-worker_latest.json"
    receipt = _read_json(receipt_path)
    receipt_status = str(receipt.get("status") or "").upper() or None
    child_pid, child_identity_state = _active_child_identity(root, ps_bin)
    child_running = child_identity_state == "ACTIVE"
    last_progress_at, last_progress_epoch = _latest_progress(root)
    reference_now = time.time() if now is None else now
    progress_recent = (
        child_running
        and last_progress_epoch is not None
        and reference_now - last_progress_epoch <= progress_max_age_seconds
    )
    supervisor_alive = _pid_alive(supervisor_pid)

    child_terminal_status: str | None = None
    if child_running and progress_recent:
        health_state = "WORKFLOW_PROGRESSING"
    elif child_running:
        health_state = "CHILD_RUNNING"
    elif (
        receipt_status == "OK"
        and receipt.get("child_exit_code") == 0
        and receipt.get("final_process_group_quiescent") is True
    ):
        health_state = "TERMINAL_SUCCESS"
        child_terminal_status = receipt_status
    elif receipt_status in TERMINAL_FAILURE_STATUSES:
        health_state = "TERMINAL_FAILURE"
        child_terminal_status = receipt_status
    elif supervisor_alive:
        health_state = "SUPERVISOR_ALIVE"
    else:
        health_state = "UNKNOWN"

    healthy = health_state in {"WORKFLOW_PROGRESSING", "TERMINAL_SUCCESS"}
    return {
        "schema_version": "top10-fog-runtime-health.v1",
        "health_state": health_state,
        "healthy": healthy,
        "supervisor_pid": supervisor_pid,
        "supervisor_alive": supervisor_alive,
        "child_pid": child_pid,
        "child_running": child_running,
        "child_identity_state": child_identity_state,
        "child_spawned": child_running or receipt.get("process_group_identity") is not None,
        "child_terminal_status": child_terminal_status,
        "last_progress_at": last_progress_at,
        "progress_max_age_seconds": progress_max_age_seconds,
        "receipt_status": receipt_status,
        "receipt_path": receipt_path.relative_to(root).as_posix(),
        "reasons": receipt.get("reasons") if isinstance(receipt.get("reasons"), list) else [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--supervisor-pid", type=int, default=None)
    parser.add_argument("--progress-max-age-seconds", type=float, default=300.0)
    parser.add_argument("--ps-bin", default=os.environ.get("TOP10_PROCESS_IDENTITY_PS_BIN", "/bin/ps"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = classify(
        args.root,
        supervisor_pid=args.supervisor_pid,
        progress_max_age_seconds=args.progress_max_age_seconds,
        ps_bin=args.ps_bin,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
