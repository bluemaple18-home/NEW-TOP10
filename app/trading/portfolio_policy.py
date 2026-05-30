"""TopN 投組配置政策。

這層只做保守、可解釋的 sizing，不做最佳化器，也不觸發回測。
"""

from __future__ import annotations

import pandas as pd

from .market_regime import MarketRegime
from .portfolio_risk_overlay import PortfolioRiskOverlay


class PortfolioPolicy:
    """依 M7 分數與市場狀態產生 TopN 建議權重。"""

    def __init__(self, base_max_position_weight: float = 0.12, portfolio_overlay: PortfolioRiskOverlay | None = None):
        self.base_max_position_weight = float(base_max_position_weight)
        self.portfolio_overlay = portfolio_overlay or PortfolioRiskOverlay()

    def apply(self, ranked_df: pd.DataFrame, regime: MarketRegime | None = None) -> pd.DataFrame:
        df = ranked_df.copy()
        if df.empty:
            return df

        gross_exposure = self._gross_exposure(regime)
        df["gross_exposure"] = gross_exposure
        df["max_position_weight"] = self._max_position_weight(df, gross_exposure)
        df["suggested_weight"] = self._suggested_weights(df, gross_exposure)
        allocated = float(df["suggested_weight"].sum())
        df["allocated_exposure"] = round(allocated, 4)
        df["cash_weight"] = round(max(0.0, 1.0 - allocated), 4)
        df["exposure_note"] = self._exposure_note(regime, gross_exposure, allocated)
        return self.portfolio_overlay.apply_sizing_overlay(df, regime)

    def _gross_exposure(self, regime: MarketRegime | None) -> float:
        if regime is None:
            return 0.6
        if regime.label == "RISK_ON":
            return 0.85
        if regime.label == "RISK_OFF":
            return 0.35
        if regime.label == "UNKNOWN":
            return 0.3
        return round(max(0.3, min(0.85, 0.65 * float(regime.risk_multiplier))), 4)

    def _max_position_weight(self, df: pd.DataFrame, gross_exposure: float) -> pd.Series:
        risk_penalty = pd.to_numeric(df.get("risk_penalty", 0), errors="coerce").fillna(0).clip(0, 1.5)
        risk_cap_factor = (1 - risk_penalty * 0.35).clip(0.45, 1.0)
        base_cap = min(self.base_max_position_weight, max(0.03, gross_exposure / max(len(df), 1) * 1.8))
        return (base_cap * risk_cap_factor).clip(upper=gross_exposure).round(4)

    def _suggested_weights(self, df: pd.DataFrame, gross_exposure: float) -> pd.Series:
        score = pd.to_numeric(df.get("risk_adjusted_score", 0), errors="coerce").fillna(0).clip(lower=0)
        risk_penalty = pd.to_numeric(df.get("risk_penalty", 0), errors="coerce").fillna(0).clip(0, 1.5)
        adjusted_score = (score * (1 - risk_penalty * 0.25).clip(0.25, 1.0)).clip(lower=0)
        if adjusted_score.sum() <= 0:
            adjusted_score = pd.Series(1.0, index=df.index)

        raw_weights = adjusted_score / adjusted_score.sum() * gross_exposure
        caps = pd.to_numeric(df["max_position_weight"], errors="coerce").fillna(0)
        weights = raw_weights.clip(upper=caps)
        remaining = gross_exposure - float(weights.sum())

        # 把 cap 後剩餘曝險分給仍有空間的標的，最多跑幾輪避免浮點誤差。
        for _ in range(5):
            if remaining <= 1e-9:
                break
            room = (caps - weights).clip(lower=0)
            if room.sum() <= 1e-9:
                break
            add = room / room.sum() * remaining
            weights = (weights + add).clip(upper=caps)
            remaining = gross_exposure - float(weights.sum())

        return weights.round(4)

    def _exposure_note(self, regime: MarketRegime | None, gross_exposure: float, allocated: float) -> str:
        label = regime.label if regime else "UNKNOWN"
        if label == "RISK_OFF":
            stance = "市場偏弱，降低總曝險"
        elif label == "RISK_ON":
            stance = "市場偏多，可提高總曝險但保留單檔上限"
        elif label == "UNKNOWN":
            stance = "市場狀態不明，採低曝險"
        else:
            stance = "市場中性，採保守分散配置"
        return f"{stance}；目標總曝險 {gross_exposure:.0%}，目前配置 {allocated:.0%}"
