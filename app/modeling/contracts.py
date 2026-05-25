"""模型契約。

所有模型先用契約描述輸入與輸出，避免 UI、排名、回測各自猜欄位。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    name: str
    layer: str
    purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    owner_module: str
    training_required: bool = False
    backtest_required: bool = False
    freshness: str = "daily"
    status: str = "planned"
    notes: str = ""


@dataclass(frozen=True)
class ModelValidationIssue:
    severity: str
    model_id: str
    message: str
