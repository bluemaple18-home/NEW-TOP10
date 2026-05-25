"""市場狀態判斷。

目前先用 universe breadth 做薄版 regime，不依賴加權指數外部資料。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MarketRegime:
    label: str
    risk_multiplier: float
    breadth_ma20: float | None
    breakout_ratio: float | None
    avg_rsi: float | None
    notes: str


class MarketRegimeService:
    """用既有特徵估計市場風險開關。"""

    def evaluate(self, features_df: pd.DataFrame, target_date=None) -> MarketRegime:
        if features_df.empty:
            return MarketRegime("UNKNOWN", 0.7, None, None, None, "無特徵資料，降低風險")

        df = features_df.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            if target_date is None:
                target_date = df["date"].max()
            else:
                requested_day = pd.to_datetime(target_date).normalize()
                matching_dates = df.loc[df["date"].dt.normalize() == requested_day, "date"]
                if matching_dates.empty:
                    return MarketRegime("UNKNOWN", 0.7, None, None, None, "指定日期無資料，降低風險")
                target_date = matching_dates.max()
            day_df = df[df["date"] == target_date].copy()
        else:
            day_df = df

        if day_df.empty:
            return MarketRegime("UNKNOWN", 0.7, None, None, None, "指定日期無資料，降低風險")

        breadth_ma20 = self._ratio(day_df, "close", "ma20", lambda close, ma: close > ma)
        breakout_ratio = self._event_ratio(day_df, ["break_20d_high", "breakout_flag"])
        avg_rsi = float(day_df["rsi"].dropna().mean()) if "rsi" in day_df.columns else None

        if breadth_ma20 is not None and breadth_ma20 >= 0.58 and (avg_rsi is None or avg_rsi >= 50):
            return MarketRegime("RISK_ON", 1.08, breadth_ma20, breakout_ratio, avg_rsi, "市場廣度偏多，可正常承擔風險")
        if breadth_ma20 is not None and breadth_ma20 <= 0.38:
            return MarketRegime("RISK_OFF", 0.72, breadth_ma20, breakout_ratio, avg_rsi, "市場廣度偏弱，降低出手與倉位")
        return MarketRegime("NEUTRAL", 1.0, breadth_ma20, breakout_ratio, avg_rsi, "市場中性，依個股品質排序")

    def _ratio(self, df: pd.DataFrame, left: str, right: str, predicate) -> float | None:
        if left not in df.columns or right not in df.columns:
            return None
        data = df[[left, right]].dropna()
        if data.empty:
            return None
        return float(predicate(data[left], data[right]).mean())

    def _event_ratio(self, df: pd.DataFrame, candidates: list[str]) -> float | None:
        for col in candidates:
            if col in df.columns:
                data = df[col].dropna()
                if not data.empty:
                    return float((data > 0).mean())
        return None
