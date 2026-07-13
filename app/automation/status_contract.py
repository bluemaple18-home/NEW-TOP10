"""Automation status 的 deterministic 純契約。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


STATUS_SCHEMA_VERSION = "daily-run-status.v1"


@dataclass
class StepResult:
    name: str
    status: str
    command: list[str] | None = None
    message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None


@dataclass
class AutomationStatus:
    schema_version: str
    mode: str
    status: str
    dry_run: bool
    started_at: str
    run_date: str
    finished_at: str | None = None
    skip_reason: str | None = None
    steps: list[StepResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def status_output_path(canonical_path: Path, *, mode: str, dry_run: bool) -> Path:
    """依 mode 與 dry-run 契約回傳 status 輸出路徑。"""
    if mode == "daily":
        status_path = canonical_path
    else:
        status_path = canonical_path.with_name(f"{mode}_automation_status{canonical_path.suffix}")
    if dry_run:
        status_path = canonical_path.with_name(f"{canonical_path.stem}_dry_run{canonical_path.suffix}")
    return status_path


def daily_status_snapshot_path(canonical_path: Path, *, run_date: str, dry_run: bool) -> Path:
    """回傳指定日期的 daily status snapshot 路徑。"""
    dry_run_suffix = "_dry_run" if dry_run else ""
    return canonical_path.with_name(f"{canonical_path.stem}_{run_date}{dry_run_suffix}{canonical_path.suffix}")


def automation_summary_payload(
    status_payload: Mapping[str, Any],
    *,
    run_date: str,
    mode: str,
    dry_run: bool,
) -> dict[str, Any]:
    """投影固定欄位與順序的 automation summary payload。"""
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "run_date": run_date,
        "mode": mode,
        "status": status_payload["status"],
        "dry_run": dry_run,
        "skip_reason": status_payload.get("skip_reason"),
        "started_at": status_payload["started_at"],
        "finished_at": status_payload.get("finished_at"),
        "errors": status_payload.get("errors", []),
        "step_summary": [
            {
                "name": step["name"],
                "status": step["status"],
                "message": step.get("message"),
                "exit_code": step.get("exit_code"),
            }
            for step in status_payload.get("steps", [])
        ],
        "metadata": status_payload.get("metadata", {}),
    }
