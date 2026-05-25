"""基本面資料 API contract。"""

from __future__ import annotations

from pydantic import BaseModel


class FundamentalSourceLinks(BaseModel):
    income_statement: str | None = None
    balance_sheet: str | None = None
    cash_flow: str | None = None
    mops: str | None = None
    mops_otc: str | None = None


class FundamentalMetricItem(BaseModel):
    year: str
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    current_ratio: float | None = None
    debt_ratio: float | None = None
    roe: float | None = None
    roa: float | None = None
    free_cash_flow: float | None = None
    eps: float | None = None


class FundamentalWarningItem(BaseModel):
    level: str
    field: str
    message: str


class FundamentalTrendItem(BaseModel):
    key: str
    label: str
    latest_year: str | None = None
    latest_value: float | None = None
    previous_year: str | None = None
    previous_value: float | None = None
    change: float | None = None
    direction: str = "neutral"
    tone: str = "neutral"
    summary: str


class FundamentalDimensionSummary(BaseModel):
    id: str
    label: str
    items: list[FundamentalTrendItem] = []
    highlights: list[str] = []


class StockFundamentalsResponse(BaseModel):
    stock_id: str
    available: bool
    source: str | None = None
    updated_at: str | None = None
    source_links: FundamentalSourceLinks | None = None
    years_covered: list[str] = []
    metrics: list[FundamentalMetricItem] = []
    dimensions: list[FundamentalDimensionSummary] = []
    warnings: list[FundamentalWarningItem] = []
    notes: str | None = None
