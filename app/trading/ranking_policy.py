"""排序政策。

保留舊 `final_score`，並把決策層分數拆成可解釋的四個構面：
prediction_score + setup_score + quality_score - risk_penalty。
"""

from __future__ import annotations

import pandas as pd

from .market_regime import MarketRegime
from .portfolio_risk_overlay import PortfolioRiskOverlay
from .tape_guard import add_tape_guard_columns
from .trade_plan import TradePlanService


class RankingPolicy:
    def __init__(
        self,
        trade_plan_service: TradePlanService | None = None,
        portfolio_overlay: PortfolioRiskOverlay | None = None,
    ):
        self.trade_plan_service = trade_plan_service or TradePlanService()
        self.portfolio_overlay = portfolio_overlay or PortfolioRiskOverlay()

    def apply(
        self,
        ranked_df: pd.DataFrame,
        regime: MarketRegime | None = None,
        *,
        apply_selection_guards: bool = False,
    ) -> pd.DataFrame:
        df = ranked_df.copy()
        if df.empty:
            return df

        if "final_score" not in df.columns:
            df["final_score"] = df.get("model_prob", 0.5)

        df = add_tape_guard_columns(df)
        risk_multiplier = regime.risk_multiplier if regime else 1.0
        df["liquidity_factor"] = self._liquidity_factor(df)
        df["setup_quality"] = self._setup_quality(df)
        df["regime_factor"] = risk_multiplier
        df["prediction_score"] = self._prediction_score(df)
        df["setup_score"] = self._setup_score(df)
        df["quality_score"] = self._quality_score(df)
        df["risk_penalty"] = self._risk_penalty(df, risk_multiplier=risk_multiplier)

        trade_plans = []
        risk_rewards = []
        for _, row in df.iterrows():
            plan = self.trade_plan_service.build(row, p_win=row.get("model_prob"), risk_multiplier=risk_multiplier)
            trade_plans.append(plan.to_flat_dict())
            risk_rewards.append(plan.risk_reward)

        df["trade_plan"] = trade_plans
        df["risk_reward"] = risk_rewards
        df["risk_reward_factor"] = pd.Series(risk_rewards, index=df.index).fillna(1.0).clip(0.5, 3.0) / 2.0
        df = self._add_execution_rr_guard(df)
        df["risk_adjusted_score"] = (
            df["prediction_score"] + df["setup_score"] + df["quality_score"] - df["risk_penalty"]
        ).clip(lower=0)
        df["market_regime"] = regime.label if regime else "UNKNOWN"
        df = self.portfolio_overlay.apply_score_overlay(df, regime)
        if apply_selection_guards:
            df = self._apply_tape_veto(df)
        return df.sort_values("risk_adjusted_score", ascending=False)

    def _prediction_score(self, df: pd.DataFrame) -> pd.Series:
        source = df["model_prob"] if "model_prob" in df.columns else df.get("final_score", 0.5)
        return pd.to_numeric(source, errors="coerce").fillna(0.5).clip(0, 1)

    def _setup_score(self, df: pd.DataFrame) -> pd.Series:
        if "rule_score_norm" in df.columns:
            return pd.to_numeric(df["rule_score_norm"], errors="coerce").fillna(0.5).clip(0, 1)
        if "rule_score" not in df.columns:
            return pd.Series(0.5, index=df.index)
        score = pd.to_numeric(df["rule_score"], errors="coerce").fillna(0)
        min_score = score.min()
        max_score = score.max()
        if max_score <= min_score:
            return pd.Series(0.5, index=df.index)
        return ((score - min_score) / (max_score - min_score)).clip(0, 1)

    def _quality_score(self, df: pd.DataFrame) -> pd.Series:
        # UQ-05/UQ-10：基本面 coverage 與 IC 尚未達 ranking gate，先只保留流動性品質。
        return self._liquidity_quality(df).fillna(0.5).clip(0, 1)

    def _liquidity_quality(self, df: pd.DataFrame) -> pd.Series:
        if "avg_value_20d" not in df.columns:
            return pd.Series(0.5, index=df.index)
        value = pd.to_numeric(df["avg_value_20d"], errors="coerce").fillna(0)
        return (value / 30_000_000).clip(0, 1)

    def _risk_penalty(self, df: pd.DataFrame, risk_multiplier: float) -> pd.Series:
        penalty = pd.Series(max(0.0, 1.0 - float(risk_multiplier)), index=df.index)
        penalty = penalty + (1 - self._liquidity_factor(df)).clip(lower=0)

        if "risk_signals" in df.columns:
            has_risk_signal = df["risk_signals"].fillna("").astype(str).str.len() > 0
            penalty = penalty + has_risk_signal.astype(float) * 0.25
        if "long_upper_shadow" in df.columns:
            penalty = penalty + (pd.to_numeric(df["long_upper_shadow"], errors="coerce").fillna(0) > 0).astype(float) * 0.15
        if "event_long_upper_shadow" in df.columns:
            penalty = penalty + (pd.to_numeric(df["event_long_upper_shadow"], errors="coerce").fillna(0) > 0).astype(float) * 0.15
        for column, weight in {
            "td_sell_setup": 0.35,
            "pattern_m_top": 0.45,
            "candle_tombstone_doji": 0.25,
            "candle_shooting_star": 0.20,
            "candle_bear_engulfing": 0.25,
            "candle_evening_star": 0.30,
            "candle_3black": 0.30,
        }.items():
            if column in df.columns:
                penalty = penalty + (pd.to_numeric(df[column], errors="coerce").fillna(0) > 0).astype(float) * weight
        if "td_count" in df.columns:
            td_count = pd.to_numeric(df["td_count"], errors="coerce")
            penalty = penalty + (td_count >= 7).fillna(False).astype(float) * 0.15
        if "rsi" in df.columns:
            rsi = pd.to_numeric(df["rsi"], errors="coerce")
            penalty = penalty + (rsi > 78).fillna(False).astype(float) * 0.2
        if "close" in df.columns and "ma20" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            ma20 = pd.to_numeric(df["ma20"], errors="coerce")
            penalty = penalty + (close < ma20).fillna(False).astype(float) * 0.25
        return penalty.clip(0, 1.5)

    def _liquidity_factor(self, df: pd.DataFrame) -> pd.Series:
        if "avg_value_20d" not in df.columns:
            return pd.Series(1.0, index=df.index)
        value = pd.to_numeric(df["avg_value_20d"], errors="coerce").fillna(0)
        return (value / 30_000_000).clip(0.7, 1.15)

    def _setup_quality(self, df: pd.DataFrame) -> pd.Series:
        quality = pd.Series(1.0, index=df.index)
        if "rsi" in df.columns:
            rsi = pd.to_numeric(df["rsi"], errors="coerce")
            quality = quality.where(~(rsi > 78), quality * 0.72)
            quality = quality.where(~(rsi < 35), quality * 0.9)
        if "long_upper_shadow" in df.columns:
            quality = quality.where(pd.to_numeric(df["long_upper_shadow"], errors="coerce").fillna(0) <= 0, quality * 0.82)
        for column in ("td_sell_setup", "pattern_m_top", "candle_tombstone_doji", "candle_bear_engulfing"):
            if column in df.columns:
                quality = quality.where(pd.to_numeric(df[column], errors="coerce").fillna(0) <= 0, quality * 0.82)
        for column in ("td_buy_setup", "pattern_w_bottom", "candle_bull_engulfing", "candle_dragonfly_doji"):
            if column in df.columns:
                quality = quality.where(pd.to_numeric(df[column], errors="coerce").fillna(0) <= 0, quality * 1.05)
        if "close" in df.columns and "ma20" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            ma20 = pd.to_numeric(df["ma20"], errors="coerce")
            quality = quality.where(~(close < ma20), quality * 0.75)
        return quality.clip(0.45, 1.15)

    def _apply_tape_veto(self, df: pd.DataFrame) -> pd.DataFrame:
        """當日 tape 失控時直接排出主排名，不讓延遲訊號蓋過跌停事實。"""
        if "tape_guard_action" not in df.columns:
            return df
        result = df.copy()
        action = result["tape_guard_action"].fillna("").astype(str)
        exclude = action == "EXCLUDE"
        downgrade = action == "DOWNGRADE"
        copy_guard = action == "COPY_GUARD"
        if "risk_penalty" in result.columns:
            penalty = pd.to_numeric(result["risk_penalty"], errors="coerce").fillna(0.0)
            result["risk_penalty"] = (penalty + exclude.astype(float) * 1.5 + downgrade.astype(float) * 0.75 + copy_guard.astype(float) * 0.25).clip(0, 3)
        if "risk_adjusted_score" in result.columns:
            score = pd.to_numeric(result["risk_adjusted_score"], errors="coerce").fillna(0.0)
            score = score.mask(exclude, -999.0)
            score = score.mask(downgrade, score * 0.35)
            score = score.mask(copy_guard, score * 0.75)
            if "rr_guard_action" in result.columns:
                rr_action = result["rr_guard_action"].fillna("").astype(str)
                score = score.mask(rr_action == "WAIT_PULLBACK", score * 0.55)
                score = score.mask(rr_action == "WAIT_CONFIRM", score * 0.9)
            result["risk_adjusted_score"] = score
        return result

    def _add_execution_rr_guard(self, df: pd.DataFrame) -> pd.DataFrame:
        """估短線執行 RR，和趨勢失效價分開。

        trend stop 可以比較遠，但短線進場要看上方壓力與近期防守價是否划算。
        """
        result = df.copy()
        close = self._numeric_column(result, "close")
        service_target = result.get("trade_plan", pd.Series(index=result.index, dtype=object)).apply(
            lambda plan: plan.get("target_price") if isinstance(plan, dict) else None
        )
        service_stop = result.get("trade_plan", pd.Series(index=result.index, dtype=object)).apply(
            lambda plan: plan.get("stop_loss") if isinstance(plan, dict) else None
        )
        pressure = self._numeric_column(result, "reason_target_price").fillna(
            pd.to_numeric(service_target, errors="coerce")
        ).fillna(self._pressure_price(result, close))
        trend_stop = self._numeric_column(result, "reason_stop_loss").fillna(
            pd.to_numeric(service_stop, errors="coerce")
        )
        execution_stop = self._execution_stop(result, close)
        downside = (close - execution_stop).where((close - execution_stop) > 0)
        upside = (pressure - close).where((pressure - close) > 0)
        rr = upside / downside
        trend_downside = (close - trend_stop).where((close - trend_stop) > 0)
        structural_rr = upside / trend_downside
        result["pressure_price"] = pressure.round(2)
        result["execution_stop_loss"] = execution_stop.round(2)
        result["trend_invalidation_price"] = trend_stop.round(2)
        result["execution_risk_reward"] = rr.round(2)
        result["risk_reward_score"] = structural_rr.round(2)
        action = pd.Series("ALLOW", index=result.index, dtype="object")
        action = action.mask(structural_rr < 0.8, "WAIT_PULLBACK")
        action = action.mask((structural_rr >= 0.8) & (structural_rr < 1.0), "WAIT_CONFIRM")
        result["rr_guard_action"] = action
        result["rr_guard_reason"] = action.map(
            {
                "WAIT_PULLBACK": "上方空間小於下方風險，只能等拉回或重新確認",
                "WAIT_CONFIRM": "上方空間沒有明顯大過下方風險，暫不列主攻",
                "ALLOW": "",
            }
        ).fillna("")
        return result

    def _pressure_price(self, df: pd.DataFrame, close: pd.Series) -> pd.Series:
        pressure = pd.Series(pd.NA, index=df.index, dtype="Float64")
        for column in ("ref_high_20d", "ref_high_60d", "pattern_resistance"):
            if column not in df.columns:
                continue
            candidate = pd.to_numeric(df[column], errors="coerce")
            pressure = pressure.where(pressure.notna() & (pressure > close), candidate.where(candidate > close))
        return pressure.fillna(close * 1.06)

    def _execution_stop(self, df: pd.DataFrame, close: pd.Series) -> pd.Series:
        candidates = []
        for column, multiplier in (("ma5", 0.985), ("ma10", 0.98), ("ref_low_5d", 0.99), ("ref_low_10d", 0.99)):
            if column in df.columns:
                candidates.append(pd.to_numeric(df[column], errors="coerce") * multiplier)
        candidates.append(close * 0.97)
        stop_frame = pd.concat(candidates, axis=1)
        stop_frame = stop_frame.where(stop_frame.lt(close, axis=0))
        return stop_frame.max(axis=1).fillna(close * 0.97)

    def _numeric_column(self, df: pd.DataFrame, column: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(pd.NA, index=df.index, dtype="Float64")
        return pd.to_numeric(df[column], errors="coerce")
