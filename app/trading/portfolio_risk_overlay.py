"""Portfolio risk overlay 的 default-off production scaffold。

此模組把研究階段的 regime-aware score / sizing overlay 收斂成一個可關閉的
純函式物件。預設 disabled，不改 production ranking 或配置。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .market_regime import MarketRegime


@dataclass(frozen=True)
class PortfolioRiskOverlayConfig:
    enabled: bool = False
    score_overlay_enabled: bool = False
    sizing_overlay_enabled: bool = False
    risk_profile: str = "baseline"

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> "PortfolioRiskOverlayConfig":
        data = payload or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            score_overlay_enabled=bool(data.get("score_overlay_enabled", False)),
            sizing_overlay_enabled=bool(data.get("sizing_overlay_enabled", False)),
            risk_profile=str(data.get("risk_profile") or "baseline"),
        )


class PortfolioRiskOverlay:
    """研究通過後才可開啟的 portfolio overlay。

    default-off 時所有方法都回傳原 dataframe，不新增欄位、不改排序。
    """

    def __init__(self, config: PortfolioRiskOverlayConfig | None = None):
        self.config = config or PortfolioRiskOverlayConfig()

    def apply_score_overlay(self, ranked_df: pd.DataFrame, regime: MarketRegime | None = None) -> pd.DataFrame:
        if not self.config.enabled or not self.config.score_overlay_enabled or ranked_df.empty:
            return ranked_df

        regime_label = self._regime_label(ranked_df, regime)
        df = ranked_df.copy()
        prediction = pd.to_numeric(df.get("prediction_score", df.get("model_prob", 0.5)), errors="coerce").fillna(0.5)
        quality = pd.to_numeric(df.get("quality_score", 0.5), errors="coerce").fillna(0.5)
        risk = pd.to_numeric(df.get("risk_penalty", 0.0), errors="coerce").fillna(0.0)
        base = prediction + quality - risk

        volume_rank = self._percentile(df.get("avg_volume_20d", pd.Series(index=df.index, dtype=float)))
        value_rank = self._percentile(df.get("avg_value_20d", pd.Series(index=df.index, dtype=float)))
        volume_heat = (volume_rank + value_rank) / 2
        industry_strength = self._percentile(df.get("industry_breadth_ma20_loo", pd.Series(index=df.index, dtype=float)))
        sector_strength = self._percentile(df.get("sector_return_1d_loo", pd.Series(index=df.index, dtype=float)))
        trend_extension = self._percentile(df.get("pct_from_low_60d", pd.Series(index=df.index, dtype=float)))
        bb_width = self._percentile(df.get("bb_width", pd.Series(index=df.index, dtype=float)))

        if regime_label == "NARROW_LEADER":
            score = base + 0.32 * industry_strength + 0.24 * sector_strength + 0.18 * volume_heat
        elif regime_label == "EARLY_REVERSAL":
            score = base + 0.32 * sector_strength + 0.22 * industry_strength + 0.18 * volume_heat
        elif regime_label == "MIXED_NEUTRAL":
            score = base - 0.30 * volume_heat + 0.18 * industry_strength - 0.12 * trend_extension
        elif regime_label == "RISK_OFF":
            score = base + 0.25 * (1 - trend_extension) + 0.20 * (1 - bb_width) + 0.14 * industry_strength
        elif regime_label == "PANIC_SELLING":
            score = base + 0.28 * volume_heat + 0.20 * (1 - bb_width) + 0.16 * sector_strength
        else:
            score = base + 0.10 * industry_strength

        df["portfolio_overlay_regime"] = regime_label
        df["portfolio_overlay_score"] = score.clip(lower=0)
        df["risk_adjusted_score"] = df["portfolio_overlay_score"]
        return df.sort_values("risk_adjusted_score", ascending=False)

    def apply_sizing_overlay(self, ranked_df: pd.DataFrame, regime: MarketRegime | None = None) -> pd.DataFrame:
        if not self.config.enabled or not self.config.sizing_overlay_enabled or ranked_df.empty:
            return ranked_df

        df = ranked_df.copy()
        regime_label = self._regime_label(df, regime)
        current_gross = pd.to_numeric(df.get("gross_exposure", 0.0), errors="coerce").dropna()
        source_gross = float(current_gross.iloc[0]) if not current_gross.empty else 0.65
        target_gross = self._gross_exposure_cap(regime_label, source_gross)

        suggested = pd.to_numeric(df.get("suggested_weight", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
        if suggested.sum() <= 0:
            suggested = pd.Series(1 / len(df), index=df.index, dtype=float)
        weights = suggested / suggested.sum() * target_gross

        position_cap = min(0.12, max(0.03, target_gross / max(len(df), 1) * 1.8))
        risk_penalty = pd.to_numeric(df.get("risk_penalty", 0.0), errors="coerce").fillna(0.0).clip(0, 1.5)
        risk_cap_factor = (1 - risk_penalty * 0.35).clip(0.45, 1.0)
        caps = (position_cap * risk_cap_factor).clip(upper=target_gross)
        weights = weights.clip(upper=caps)

        remaining = target_gross - float(weights.sum())
        for _ in range(5):
            if remaining <= 1e-9:
                break
            room = (caps - weights).clip(lower=0)
            if room.sum() <= 1e-9:
                break
            add = room / room.sum() * remaining
            weights = (weights + add).clip(upper=caps)
            remaining = target_gross - float(weights.sum())

        allocated = float(weights.sum())
        df["portfolio_overlay_regime"] = regime_label
        df["gross_exposure"] = round(target_gross, 4)
        df["max_position_weight"] = caps.round(4)
        df["suggested_weight"] = weights.round(4)
        df["allocated_exposure"] = round(allocated, 4)
        df["cash_weight"] = round(max(0.0, 1.0 - allocated), 4)
        df["exposure_note"] = f"portfolio overlay {regime_label}；研究版總曝險上限 {target_gross:.0%}"
        return df

    def _regime_label(self, df: pd.DataFrame, regime: MarketRegime | None) -> str:
        for column in ("portfolio_overlay_regime", "shadow_market_regime", "market_regime"):
            if column in df.columns:
                values = df[column].dropna().astype(str)
                values = values[values.str.strip() != ""]
                if not values.empty:
                    return values.iloc[0]
        return regime.label if regime else "UNKNOWN"

    def _gross_exposure_cap(self, regime_label: str, current_gross: float) -> float:
        caps_by_profile = {
            "shadow_regime_guard_balanced": {
                "PANIC_SELLING": 0.35,
                "RISK_OFF": 0.50,
                "MIXED_NEUTRAL": 0.50,
                "EARLY_REVERSAL": 0.60,
                "NARROW_LEADER": 0.65,
                "UNKNOWN": 0.35,
            },
            "shadow_regime_guard": {
                "PANIC_SELLING": 0.30,
                "RISK_OFF": 0.35,
                "MIXED_NEUTRAL": 0.45,
                "EARLY_REVERSAL": 0.55,
                "NARROW_LEADER": 0.65,
                "UNKNOWN": 0.30,
            },
        }
        caps = caps_by_profile.get(self.config.risk_profile, caps_by_profile["shadow_regime_guard"])
        return min(float(current_gross), caps.get(regime_label, 0.45))

    def _percentile(self, series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce")
        ranked = values.rank(pct=True, ascending=True)
        return ranked.fillna(0.5).clip(0, 1)
