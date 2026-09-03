from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
VERIFIER = PROJECT_ROOT / "scripts" / "fog_runtime_health.py"


def _run_verifier(tmp_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), str(VERIFIER), "--root", str(tmp_path), *extra_args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_receipt(tmp_path: Path, payload: dict) -> None:
    receipt = tmp_path / "logs" / "storage_safety" / "fog-research-worker_latest.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(payload), encoding="utf-8")


def _write_active_lock(tmp_path: Path) -> Path:
    lock_dir = tmp_path / "logs" / "fog_research_worker.lock"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_dir.joinpath("pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    lock_dir.joinpath("start_token").write_text(f"token-{os.getpid()}\n", encoding="utf-8")
    fake_ps = tmp_path / "fake-ps"
    fake_ps.write_text(
        '#!/usr/bin/env bash\npid="${@: -1}"\nprintf "token-%s\\n" "$pid"\n',
        encoding="utf-8",
    )
    fake_ps.chmod(0o755)
    return fake_ps


def test_supervisor_alive_with_restart_denied_is_terminal_failure(tmp_path: Path) -> None:
    _write_receipt(
        tmp_path,
        {
            "status": "RESTART_DENIED",
            "child_exit_code": None,
            "process_group_identity": None,
            "final_process_group_quiescent": None,
            "reasons": ["PERSISTENT_RESTART_DENIED_MARKER"],
        },
    )

    completed = _run_verifier(tmp_path, "--supervisor-pid", str(os.getpid()))

    assert completed.returncode == 1, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["health_state"] == "TERMINAL_FAILURE"
    assert payload["healthy"] is False
    assert payload["supervisor_alive"] is True
    assert payload["child_running"] is False
    assert payload["child_terminal_status"] == "RESTART_DENIED"


def test_terminal_success_requires_exit_zero_and_quiescent_group(tmp_path: Path) -> None:
    _write_receipt(
        tmp_path,
        {
            "status": "OK",
            "child_exit_code": 0,
            "process_group_identity": {"leader_pid": 123},
            "final_process_group_quiescent": True,
            "reasons": [],
        },
    )

    completed = _run_verifier(tmp_path)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["health_state"] == "TERMINAL_SUCCESS"
    assert payload["healthy"] is True


def test_supervisor_only_is_not_healthy(tmp_path: Path) -> None:
    completed = _run_verifier(tmp_path, "--supervisor-pid", str(os.getpid()))

    assert completed.returncode == 1, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["health_state"] == "SUPERVISOR_ALIVE"
    assert payload["healthy"] is False


def test_active_child_without_recent_progress_is_child_running(tmp_path: Path) -> None:
    fake_ps = _write_active_lock(tmp_path)
    progress = tmp_path / "logs" / "fog_research_worker_20990103.log"
    progress.write_text("started\n", encoding="utf-8")
    old = time.time() - 600
    os.utime(progress, (old, old))

    completed = _run_verifier(
        tmp_path,
        "--ps-bin",
        str(fake_ps),
        "--progress-max-age-seconds",
        "60",
    )

    assert completed.returncode == 1, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["health_state"] == "CHILD_RUNNING"
    assert payload["child_running"] is True
    assert payload["healthy"] is False


def test_active_child_with_recent_progress_is_workflow_progressing(tmp_path: Path) -> None:
    fake_ps = _write_active_lock(tmp_path)
    progress = tmp_path / "logs" / "fog_research_worker_20990103.log"
    progress.write_text("batch progress\n", encoding="utf-8")

    completed = _run_verifier(
        tmp_path,
        "--ps-bin",
        str(fake_ps),
        "--progress-max-age-seconds",
        "60",
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["health_state"] == "WORKFLOW_PROGRESSING"
    assert payload["child_running"] is True
    assert payload["last_progress_at"] is not None
    assert payload["healthy"] is True
