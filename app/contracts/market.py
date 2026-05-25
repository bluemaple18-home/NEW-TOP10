"""看盤台資料契約。

這裡只定義「前端可依賴的形狀」，不放資料讀取與演算法。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .reference import RankingReferenceSummary


class ApiHealth(BaseModel):
    ok: bool
    features_exists: bool
    ranking_files: int


class RankingItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    stock_id: str
    stock_name: str | None = None
    close: float | None = None
    final_score: float | None = None
    model_prob: float | None = None
    rule_score: float | None = None
    prediction_score: float | None = None
    setup_score: float | None = None
    quality_score: float | None = None
    risk_penalty: float | None = None
    risk_adjusted_score: float | None = None
    suggested_weight: float | None = None
    max_position_weight: float | None = None
    gross_exposure: float | None = None
    allocated_exposure: float | None = None
    cash_weight: float | None = None
    exposure_note: str | None = None
    risk_reward: float | None = None
    market_regime: str | None = None
    industry_code: str | None = None
    industry_name: str | None = None
    sector_name: str | None = None
    market_type: str | None = None
    theme_tags: str | None = None
    concept_tags: str | None = None
    major_etfs: str | None = None
    reasons: str | None = None


class LatestRankingResponse(BaseModel):
    date: str | None
    items: list[RankingItem]
    reference_summary: RankingReferenceSummary | None = None


class StockBar(BaseModel):
    timestamp: int
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    k: float | None = None
    d: float | None = None
    rsi: float | None = None
    volume_ratio_20d: float | None = None
    candle_doji: int | None = None
    candle_dragonfly_doji: int | None = None
    candle_tombstone_doji: int | None = None
    candle_hammer: int | None = None
    candle_hanging_man: int | None = None
    candle_shooting_star: int | None = None
    candle_inverted_hammer: int | None = None
    candle_bull_marubozu: int | None = None
    candle_bear_marubozu: int | None = None
    candle_bull_engulfing: int | None = None
    candle_bear_engulfing: int | None = None
    candle_bull_harami: int | None = None
    candle_bear_harami: int | None = None
    candle_piercing: int | None = None
    candle_dark_cloud: int | None = None
    candle_morning_star: int | None = None
    candle_evening_star: int | None = None
    candle_3white: int | None = None
    candle_3black: int | None = None
    td_count: int | None = None
    td_buy_setup: int | None = None
    td_sell_setup: int | None = None
    pattern_w_bottom: int | None = None
    pattern_m_top: int | None = None
    pattern_neckline: float | None = None
    pattern_stop_loss: float | None = None
    pattern_resistance: float | None = None


class StockOhlcvResponse(BaseModel):
    stock_id: str
    stock_name: str
    items: list[StockBar]
