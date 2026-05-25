"""回測資料契約。

這裡只描述既有回測 artifact 的只讀回應形狀，不承載回測執行邏輯。
"""

from __future__ import annotations

from pydantic import BaseModel


class BacktestArtifact(BaseModel):
    name: str
    path: str
    kind: str
    size_bytes: int
    modified_at: str


class BacktestReportSummary(BaseModel):
    name: str
    path: str
    title: str | None = None
    excerpt: str | None = None
    curve_path: str | None = None
    period: str | None = None
    threshold: float | None = None
    trades: int | None = None
    win_rate: float | None = None
    avg_return: float | None = None
    size_bytes: int
    modified_at: str


class BacktestSummaryResponse(BaseModel):
    reports: list[BacktestReportSummary]
    curves: list[BacktestArtifact]
