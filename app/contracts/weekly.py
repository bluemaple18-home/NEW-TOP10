"""本週動能候選 contract。

這層只定義前端可依賴的資料形狀；候選狀態與市場解讀由 service 組裝。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .market import RankingItem

RiskStyle = Literal["conservative", "balanced", "aggressive"]
TargetType = Literal["stocks", "etfs", "both"]
HoldingPeriod = Literal["swing", "midterm", "longterm"]
EntryPreference = Literal["breakout", "pullback", "continuation", "mixed"]
RiskLimit = Literal["lowVolatility", "excludeThemes", "acceptHighVolatility"]
CandidateStatus = Literal["可分批", "等回測", "觀察突破", "續強觀察", "暫停操作"]


class InvestmentSettingsContract(BaseModel):
    risk_style: RiskStyle = "balanced"
    target_type: TargetType = "stocks"
    holding_period: HoldingPeriod = "swing"
    entry_preference: EntryPreference = "mixed"
    risk_limit: RiskLimit = "excludeThemes"


class OpportunityComponentContract(BaseModel):
    label: str
    value: str
    notes: str | None = None


class WeeklyMarketSummaryContract(BaseModel):
    market_state: str
    operation_environment: str
    opportunity_quality: str
    opportunity_components: list[OpportunityComponentContract]
    dominant_groups: list[str]
    risk_alerts: list[str]
    setting_interpretation: str


class WeeklyCandidateContract(BaseModel):
    priority: int
    target_type: Literal["stock", "etf"]
    stock_id: str
    stock_name: str | None = None
    status: CandidateStatus
    risk_label: str
    next_step: str
    key_price: str
    primary_reasons: list[str]
    ranking: RankingItem


class WeeklyModelPoolItemContract(BaseModel):
    priority: int
    target_type: Literal["stock", "etf"]
    stock_id: str
    stock_name: str | None = None
    ranking: RankingItem


class WeeklySettingsEffectContract(BaseModel):
    reason: str
    count: int
    notes: str | None = None


class WeeklyCandidateLayerContract(BaseModel):
    model_pool_count: int
    stock_model_pool_count: int
    etf_model_pool_count: int
    visible_candidate_count: int
    hidden_by_settings_count: int
    settings_applied: bool = True
    settings_effects: list[WeeklySettingsEffectContract]


class WeeklyChangeContract(BaseModel):
    kind: Literal["暫停 / 降級", "新增觀察", "大反轉"]
    title: str
    notes: str


class WeeklySnapshotContract(BaseModel):
    schema_version: str = "weekly-candidate-snapshot.v1"
    snapshot_date: str | None = None
    ranking_date: str | None = None
    week_version: str | None = None
    source: str = "latest_ranking"
    artifact_path: str | None = None
    generated_at: str | None = None
    model_pool_count: int = 0


class WeeklyCandidatesResponse(BaseModel):
    date: str | None
    version_label: str
    snapshot: WeeklySnapshotContract | None = None
    settings: InvestmentSettingsContract
    status_order: list[CandidateStatus]
    market_summary: WeeklyMarketSummaryContract
    model_pool_count: int
    model_pool: list[WeeklyModelPoolItemContract] = []
    candidate_layer: WeeklyCandidateLayerContract | None = None
    stock_candidates: list[WeeklyCandidateContract]
    etf_candidates: list[WeeklyCandidateContract]
    other_candidates: list[WeeklyCandidateContract]
    week_changes: list[WeeklyChangeContract]
