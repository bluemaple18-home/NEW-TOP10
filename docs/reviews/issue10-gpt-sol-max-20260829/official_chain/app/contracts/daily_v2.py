"""每日報牌 v2 的 shadow 執行契約。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
import re
from typing import Any


MANIFEST_SCHEMA_VERSION = "top10.daily-workflow-v2.run-manifest.v1"


class DailyStep(str, Enum):
    """每日報牌 v2 的固定步驟順序。"""

    ETL = "etl"
    VALIDATE = "validate"
    RANK = "rank"
    REPORT = "report"
    PUBLISH_READY = "publish-ready"


REQUIRED_DAILY_STEPS = tuple(DailyStep)


@dataclass(frozen=True)
class StepSpec:
    """單一步驟固定的子程序、輸入、輸出與逾時契約。"""

    name: DailyStep
    command: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    timeout_seconds: float

    def __post_init__(self) -> None:
        if not self.command or any(not value for value in self.command):
            raise ValueError(f"{self.name.value} command must not be empty")
        if not self.outputs or any(not value for value in self.outputs):
            raise ValueError(f"{self.name.value} outputs must not be empty")
        if any(not value for value in self.inputs):
            raise ValueError(f"{self.name.value} inputs must not contain empty paths")
        if self.timeout_seconds <= 0:
            raise ValueError(f"{self.name.value} timeout_seconds must be positive")

    def as_contract_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "command": list(self.command),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "timeout_seconds": self.timeout_seconds,
        }


def validate_run_identity(run_id: str, run_date: str) -> None:
    """阻擋路徑穿越與非 ISO 日期，確保 run 目錄可安全隔離。"""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise ValueError("run_id must use 1-128 ASCII letters, digits, dot, underscore or dash")
    try:
        date.fromisoformat(run_date)
    except ValueError as exc:
        raise ValueError(f"run_date must be ISO YYYY-MM-DD: {run_date}") from exc


def validate_step_order(steps: tuple[StepSpec, ...]) -> None:
    actual = tuple(step.name for step in steps)
    if actual != REQUIRED_DAILY_STEPS:
        expected = [step.value for step in REQUIRED_DAILY_STEPS]
        received = [step.value for step in actual]
        raise ValueError(f"daily v2 steps must be ordered {expected}, got {received}")
