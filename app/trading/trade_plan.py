"""交易計畫服務。

統一 entry / stop / target / position hint，避免 ranking、report、UI 各算一套。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class TradePlan:
    horizon_days: int
    entry_low: float
    entry_high: float
    stop_loss: float
    target_price: float
    invalidation: str
    risk_reward: float | None
    position_hint: str
    stop_basis: str
    target_basis: str

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "horizon_days": self.horizon_days,
            "entry_zone": {"low": self.entry_low, "high": self.entry_high},
            "invalidation": self.invalidation,
            "take_profit": [self.target_basis, "若爆量長上影或 RSI > 75，分批停利"],
            "position_hint": self.position_hint,
            "risk_reward": self.risk_reward,
            "stop_loss": self.stop_loss,
            "target_price": self.target_price,
        }

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


class TradePlanService:
    """以現有技術欄位生成薄而一致的交易計畫。"""

    def build(self, row: pd.Series | dict[str, Any], p_win: float | None = None, risk_multiplier: float = 1.0) -> TradePlan:
        data = row if isinstance(row, dict) else row.to_dict()
        close = float(data.get("close") or 0)
        ma20 = self._positive_float(data.get("ma20"))
        low_20 = self._positive_float(data.get("low_20d"))
        rsi = self._positive_float(data.get("rsi"))

        entry_low = close
        entry_high = close * 1.015

        stop_candidates = []
        if ma20:
            stop_candidates.append((ma20 * 0.98, "月線支撐"))
        if low_20:
            stop_candidates.append((low_20 * 0.99, "20日低點"))
        stop_candidates.append((close * 0.94, "6%風險停損"))

        stop_loss, stop_basis = max(stop_candidates, key=lambda item: item[0])
        risk_per_share = max(close - stop_loss, 0)

        resistance = self._positive_float(data.get("ref_high_20d")) or self._positive_float(data.get("ref_high_60d"))
        rr_target = close + risk_per_share * 2 if risk_per_share > 0 else close * 1.1
        target_price = max(close * 1.06, min(close * 1.16, max(rr_target, resistance or 0)))
        target_basis = "2R 或前高壓力區"

        risk_reward = (target_price - close) / risk_per_share if risk_per_share > 0 else None
        position_hint = self._position_hint(p_win=p_win, risk_multiplier=risk_multiplier, rsi=rsi)

        return TradePlan(
            horizon_days=10,
            entry_low=round(entry_low, 2),
            entry_high=round(entry_high, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target_price, 2),
            invalidation=f"跌破 {stop_loss:.2f} ({stop_basis})",
            risk_reward=round(risk_reward, 2) if risk_reward is not None else None,
            position_hint=position_hint,
            stop_basis=stop_basis,
            target_basis=target_basis,
        )

    def _position_hint(self, p_win: float | None, risk_multiplier: float, rsi: float | None) -> str:
        base = 0.08
        if p_win is not None and p_win >= 0.7:
            base = 0.12
        elif p_win is not None and p_win < 0.45:
            base = 0.05
        if rsi is not None and rsi > 75:
            base *= 0.6
        base *= risk_multiplier
        return f"單筆上限約 {max(min(base, 0.15), 0.03) * 100:.1f}% 資金"

    def _positive_float(self, value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(parsed) or parsed <= 0:
            return None
        return parsed
