"""子程序執行的 deterministic 結果契約。"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class CommandOutcome:
    command: list[str]
    status: str
    started_at: str
    finished_at: str
    exit_code: int | None


def normalize_command(command: Sequence[str], *, python_executable: str) -> list[str]:
    normalized = list(command)
    if normalized and normalized[0] == "python":
        return [python_executable, *normalized[1:]]
    return normalized


def execute_command(
    command: Sequence[str],
    *,
    python_executable: str,
    dry_run: bool,
    cwd: Path,
    env: Mapping[str, str],
    now: Callable[[], str],
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> CommandOutcome:
    """執行單一命令並回傳資料，不在此層決定是否中止 workflow。"""

    started_at = now()
    normalized = normalize_command(command, python_executable=python_executable)
    if dry_run:
        return CommandOutcome(normalized, "DRY_RUN", started_at, now(), None)
    completed = runner(normalized, cwd=cwd, env=dict(env))
    return CommandOutcome(
        normalized,
        "OK" if completed.returncode == 0 else "FAILED",
        started_at,
        now(),
        completed.returncode,
    )
