"""監控報告 API contract。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
