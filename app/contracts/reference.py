"""產業與 ETF reference 資料契約。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TradableUniverseItem(BaseModel):
    stock_id: str
    stock_name: str
    market_type: str
    is_etf: bool = False
    is_active: bool = True
    source: str | None = None
    updated_at: str | None = None


class TradableUniverseResponse(BaseModel):
    available: bool
    items: list[TradableUniverseItem] = Field(default_factory=list)
    notes: str | None = None


class StockIndustryClassification(BaseModel):
    stock_id: str
    available: bool
    industry_code: str | None = None
    industry_name: str | None = None
    sector_name: str | None = None
    market_type: str | None = None
    theme_tags: list[str] = Field(default_factory=list)
    source: str | None = None
    updated_at: str | None = None
    notes: str | None = None


class StockEtfExposure(BaseModel):
    stock_id: str
    etf_id: str
    etf_name: str | None = None
    weight: float | None = None
    is_major_holding: bool = False
    source: str | None = None
    updated_at: str | None = None


class StockConceptMembership(BaseModel):
    stock_id: str
    canonical_concept_id: str
    canonical_name: str
    raw_concept_name: str
    concept_type: str = "theme"
    source: str | None = None
    source_url: str | None = None
    observed_at: str | None = None
    confidence: float | None = None
    match_method: str | None = None


class StockReferenceResponse(BaseModel):
    available: bool
    stock_id: str
    industry: StockIndustryClassification
    etfs: list[StockEtfExposure] = Field(default_factory=list)
    concepts: list[StockConceptMembership] = Field(default_factory=list)
    notes: str | None = None


class ExposureBreakdownItem(BaseModel):
    name: str
    weight: float
    count: int


class RankingReferenceSummary(BaseModel):
    industry_exposure: list[ExposureBreakdownItem] = Field(default_factory=list)
    sector_exposure: list[ExposureBreakdownItem] = Field(default_factory=list)
    etf_overlap_count: int = 0
    top_industry_concentration: float | None = None
    notes: str | None = None
