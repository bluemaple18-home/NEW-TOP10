"""交易決策 contract。"""

from __future__ import annotations

from pydantic import BaseModel


class TradePlanContract(BaseModel):
    horizon_days: int
    entry_low: float
    entry_high: float
    stop_loss: float
    target_price: float
    invalidation: str
    risk_reward: float | None = None
    position_hint: str
    stop_basis: str
    target_basis: str


class MarketRegimeContract(BaseModel):
    label: str
    risk_multiplier: float
    breadth_ma20: float | None = None
    breakout_ratio: float | None = None
    avg_rsi: float | None = None
    notes: str
