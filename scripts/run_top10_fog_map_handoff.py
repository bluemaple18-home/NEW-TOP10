#!/usr/bin/env python3
"""TOP10 harness 迷霧地圖交接節點。

這支腳本只負責把既有研究地圖刷新流程包成 harness agent event。
排程入口仍由 daily/external-review harness 接手，不在這裡新增第二套排程。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from top10_agent_status import build_event, write_agent_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TOP10 fog map harness handoff.")
    parser.add_argument("--run-date", "--date", dest="run_date", default=datetime.now().date().isoformat())
    parser.add_argument("--run-id", default=None, help="harness status run_id；預設 daily-YYYY-MM-DD")
    parser.add_argument("--artifacts-dir", default=Path("artifacts"), type=Path)
    parser.add_argument("--skip-refresh", action="store_true", help="只寫 skipped event，不刷新迷霧地圖")
    parser.add_argument("--skip-reason", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_date = args.run_date
    run_id = args.run_id or f"daily-{run_date}"
    artifacts_dir = resolve_project_path(args.artifacts_dir)
    started_at = datetime.now(timezone.utc).isoformat()

    if args.skip_refresh:
        write_fog_event(
            artifacts_dir=artifacts_dir,
            run_id=run_id,
            run_date=run_date,
            status="skipped",
            decision="not_applicable",
            started_at=started_at,
            failure_reason=args.skip_reason or "upstream harness did not produce a refreshable daily handoff",
            next_action="wait for daily/external-review harness before refreshing fog map",
            metrics={"refresh_attempted": False, "command_count": 0, "map_verified": False},
        )
        print(f"TOP10_FOG_MAP_HANDOFF_SKIPPED run_date={run_date}")
        return 0

    commands = [
        [python_bin(), "scripts/build_research_campaign_progress.py", "--date", run_date],
        [python_bin(), "scripts/build_research_fog_map.py", "--date", run_date],
        [python_bin(), "scripts/verify_research_fog_map.py", "--date", run_date],
    ]
    input_refs = [
        artifacts_dir / "external_review" / run_date / f"external_review_summary_{run_date}.json",
        artifacts_dir / "autonomous_research" / "run_history.jsonl",
    ]
    artifact_paths = fog_artifacts(artifacts_dir, run_date)

    try:
        results = [run_checked(command) for command in commands]
    except Exception as exc:
        write_fog_event(
            artifacts_dir=artifacts_dir,
            run_id=run_id,
            run_date=run_date,
            status="failed",
            decision="stop",
            started_at=started_at,
            input_refs=input_refs,
            artifact_paths=artifact_paths,
            failure_reason=str(exc),
            next_action="inspect research map refresh logs, repair blocker, then rerun harness handoff",
            metrics={"refresh_attempted": True, "command_count": len(commands), "map_verified": False},
        )
        print(f"TOP10_FOG_MAP_HANDOFF_FAILED run_date={run_date} error={exc}", file=sys.stderr)
        return 1

    write_fog_event(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        run_date=run_date,
        status="ok",
        decision="pass",
        started_at=started_at,
        input_refs=input_refs,
        artifact_paths=artifact_paths,
        next_action=None,
        metrics={
            "refresh_attempted": True,
            "command_count": len(results),
            "map_verified": True,
            "commands": [mask_command(result.command) for result in results],
        },
    )
    print(f"TOP10_FOG_MAP_HANDOFF_OK run_date={run_date}")
    return 0


def fog_artifacts(artifacts_dir: Path, run_date: str) -> list[Path]:
    return [
        artifacts_dir / "autonomous_research" / f"research_campaign_progress_{run_date}.json",
        artifacts_dir / "research_map" / f"research_fog_map_{run_date}.json",
        artifacts_dir / "research_map" / "research_fog_map_latest.json",
        artifacts_dir / "research_map" / "research_fog_map_verification_latest.json",
        artifacts_dir / "research_map" / "index.html",
    ]


def run_checked(command: list[str]) -> CommandResult:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    result = CommandResult(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )
    if result.exit_code != 0:
        raise RuntimeError(
            f"command failed exit_code={result.exit_code} command={mask_command(command)} "
            f"stdout={result.stdout[-1000:]} stderr={result.stderr[-1000:]}"
        )
    return result


def write_fog_event(
    *,
    artifacts_dir: Path,
    run_id: str,
    run_date: str,
    status: str,
    decision: str,
    started_at: str,
    input_refs: list[str | Path] | None = None,
    artifact_paths: list[str | Path] | None = None,
    failure_reason: str | None = None,
    next_action: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> Path:
    event = build_event(
        run_id=run_id,
        run_date=run_date,
        agent_id="fog_map",
        status=status,
        decision=decision,
        started_at=started_at,
        input_refs=[event_path_ref(item, artifacts_dir) for item in input_refs or []],
        artifact_paths=[event_path_ref(item, artifacts_dir) for item in artifact_paths or []],
        failure_reason=failure_reason,
        next_action=next_action,
        metrics=metrics,
    )
    return write_agent_event(
        event,
        artifacts_dir=artifacts_dir,
        manifest_path=PROJECT_ROOT / "docs" / "architecture" / "top10_harness_team.dashboard.json",
    )


def event_path_ref(path: str | Path, artifacts_dir: Path) -> str:
    value = Path(path)
    try:
        return str(value.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        pass
    try:
        return str(value.resolve().relative_to(artifacts_dir.resolve()))
    except ValueError:
        return str(value)


def resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def python_bin() -> str:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def mask_command(command: list[str]) -> list[str]:
    masked = []
    for part in command:
        if part == str(PROJECT_ROOT / ".venv" / "bin" / "python") or part.endswith("/.venv/bin/python"):
            masked.append(".venv/bin/python")
        elif part == sys.executable:
            masked.append("python")
        else:
            masked.append(part)
    return masked


if __name__ == "__main__":
    raise SystemExit(main())
