"""個股詳情頁 API contract。

這裡只定義前端可依賴的四區形狀，不暴露 DataFrame 或 artifact 內部格式。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .backtest import BacktestArtifact, BacktestReportSummary
from .fundamental import StockFundamentalsResponse
from .market import StockBar
from .reference import StockReferenceResponse


class StockPatternSignal(BaseModel):
    date: str
    signal_id: str
    label: str
    category: str
    polarity: str
    price: float | None = None
    beginner_note: str | None = None
    action_hint: str | None = None


class StockPatternOverlayLine(BaseModel):
    signal_id: str
    label: str
    points: list[dict[str, float | str]]
    notes: str | None = None


class StockDetailPriceSection(BaseModel):
    available: bool
    stock_id: str
    stock_name: str | None = None
    items: list[StockBar] = Field(default_factory=list)
    signals: list[StockPatternSignal] = Field(default_factory=list)
    overlays: list[StockPatternOverlayLine] = Field(default_factory=list)
    notes: str | None = None


class StockDetailFundamentalSection(BaseModel):
    available: bool
    data: StockFundamentalsResponse | None = None
    notes: str | None = None


class StockDetailTradePlanSection(BaseModel):
    available: bool
    horizon_days: int | None = None
    entry_low: float | None = None
    entry_high: float | None = None
    stop_loss: float | None = None
    target_price: float | None = None
    risk_reward: float | None = None
    position_hint: str | None = None
    suggested_weight: float | None = None
    max_position_weight: float | None = None
    gross_exposure: float | None = None
    allocated_exposure: float | None = None
    cash_weight: float | None = None
    exposure_note: str | None = None
    notes: str | None = None


class StockDetailBacktestSection(BaseModel):
    available: bool
    scope: str = "system"
    reports: list[BacktestReportSummary] = Field(default_factory=list)
    curves: list[BacktestArtifact] = Field(default_factory=list)
    notes: str | None = None


class StockDetailReferenceSection(BaseModel):
    available: bool
    data: StockReferenceResponse | None = None
    notes: str | None = None


class StockDetailResponse(BaseModel):
    stock_id: str
    price: StockDetailPriceSection
    reference: StockDetailReferenceSection
    fundamentals: StockDetailFundamentalSection
    trade_plan: StockDetailTradePlanSection
    backtest: StockDetailBacktestSection
