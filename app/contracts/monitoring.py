"""監控報告 API contract。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FactorMetricContract(BaseModel):
    factor: str
    coverage: float
    latest_coverage: float
    ic: float | None = None
    ic_median: float | None = None
    ic_tstat: float | None = None
    ic_days: int = 0
    recent_ic: float | None = None
    turnover: float | None = None
    observations: int
    status: str
    notes: str


class FactorMonitorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    available: bool
    status: str | None = None
    generated_at: str | None = None
    horizon_days: int | None = None
    summary: dict = {}
    factors: list[FactorMetricContract] = []
    notes: str | None = None


class Top10HarnessAgentStatusContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent_id: str
    label: str | None = None
    index: int | None = None
    lane: str | None = None
    status: str | None = None
    decision: str | None = None
    duration_seconds: float | None = None
    failure_reason: str | None = None
    next_action: str | None = None
    artifact_paths: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    missing: bool = False


class Top10HarnessStatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    available: bool
    status: str | None = None
    generated_at: str | None = None
    run_date: str | None = None
    run_id: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    agents: list[Top10HarnessAgentStatusContract] = Field(default_factory=list)
    channels: list[dict[str, Any]] = Field(default_factory=list)
    flows: list[dict[str, Any]] = Field(default_factory=list)
    validation_errors: dict[str, list[str]] = Field(default_factory=dict)
    artifact_path: str | None = None
    notes: str | None = None
