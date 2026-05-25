"""大型價格結構型態。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


PRICE_PATTERN_COLUMNS = (
    "pattern_w_bottom",
    "pattern_m_top",
    "pattern_neckline",
    "pattern_stop_loss",
    "pattern_resistance",
)


@dataclass(frozen=True)
class PivotPoint:
    index: int
    confirm_index: int
    kind: str
    price: float


def add_price_patterns(
    df: pd.DataFrame,
    pivot_window: int = 5,
    tolerance: float = 0.03,
    lookback: int = 120,
) -> pd.DataFrame:
    """新增 W 底 / M 頭欄位。

    每一天只用該日以前的 `lookback` 根 K 棒判斷，避免未來函數。
    """

    required = {"date", "stock_id", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"價格型態缺少必要欄位：{sorted(missing)}")

    result = df.copy().sort_values(["stock_id", "date"]).copy()
    for col in PRICE_PATTERN_COLUMNS:
        result[col] = 0.0

    for _, stock_frame in result.groupby("stock_id", sort=False):
        stock_frame = stock_frame.sort_values("date")
        candidate_pivots = _find_candidate_pivots(stock_frame, pivot_window=pivot_window)
        for position, row_index in enumerate(stock_frame.index):
            start = max(0, position - lookback + 1)
            if position < pivot_window * 2 + 2:
                continue
            pivots = _confirmed_pivots(candidate_pivots, start=start, position=position)
            if len(pivots) < 3:
                continue
            latest_close = float(stock_frame["close"].iloc[position])
            w_payload = _detect_w_bottom(pivots, latest_close, tolerance)
            if w_payload:
                result.at[row_index, "pattern_w_bottom"] = 1
                result.at[row_index, "pattern_neckline"] = w_payload["neckline"]
                result.at[row_index, "pattern_stop_loss"] = w_payload["stop_loss"]
            m_payload = _detect_m_top(pivots, latest_close, tolerance)
            if m_payload:
                result.at[row_index, "pattern_m_top"] = 1
                result.at[row_index, "pattern_neckline"] = m_payload["neckline"]
                result.at[row_index, "pattern_resistance"] = m_payload["resistance"]

    result["pattern_w_bottom"] = result["pattern_w_bottom"].astype(int)
    result["pattern_m_top"] = result["pattern_m_top"].astype(int)
    return result.sort_index()


def _find_candidate_pivots(frame: pd.DataFrame, pivot_window: int) -> list[PivotPoint]:
    highs = pd.to_numeric(frame["high"], errors="coerce").reset_index(drop=True)
    lows = pd.to_numeric(frame["low"], errors="coerce").reset_index(drop=True)
    pivots: list[PivotPoint] = []
    for idx in range(pivot_window, len(frame) - pivot_window):
        high_slice = highs.iloc[idx - pivot_window : idx + pivot_window + 1]
        low_slice = lows.iloc[idx - pivot_window : idx + pivot_window + 1]
        current_high = highs.iloc[idx]
        current_low = lows.iloc[idx]
        if pd.notna(current_high) and current_high == high_slice.max():
            pivots.append(PivotPoint(idx, idx + pivot_window, "high", float(current_high)))
        if pd.notna(current_low) and current_low == low_slice.min():
            pivots.append(PivotPoint(idx, idx + pivot_window, "low", float(current_low)))
    return sorted(pivots, key=lambda pivot: (pivot.index, pivot.kind))


def _confirmed_pivots(candidate_pivots: list[PivotPoint], start: int, position: int) -> list[PivotPoint]:
    pivots: list[PivotPoint] = []
    for pivot in candidate_pivots:
        if pivot.confirm_index > position:
            break
        if pivot.index < start:
            continue
        _append_pivot(pivots, pivot)
    return pivots


def _append_pivot(pivots: list[PivotPoint], pivot: PivotPoint) -> None:
    if not pivots or pivots[-1].kind != pivot.kind:
        pivots.append(pivot)
        return
    previous = pivots[-1]
    if pivot.kind == "high" and pivot.price > previous.price:
        pivots[-1] = pivot
    if pivot.kind == "low" and pivot.price < previous.price:
        pivots[-1] = pivot


def _detect_w_bottom(pivots: list[PivotPoint], latest_close: float, tolerance: float) -> dict[str, float] | None:
    a, b, c = pivots[-3:]
    if [a.kind, b.kind, c.kind] != ["low", "high", "low"]:
        return None
    if a.price <= 0 or abs(a.price - c.price) / a.price > tolerance:
        return None
    neckline = b.price
    if latest_close <= neckline:
        return None
    return {"neckline": neckline, "stop_loss": min(a.price, c.price)}


def _detect_m_top(pivots: list[PivotPoint], latest_close: float, tolerance: float) -> dict[str, float] | None:
    a, b, c = pivots[-3:]
    if [a.kind, b.kind, c.kind] != ["high", "low", "high"]:
        return None
    if a.price <= 0 or abs(a.price - c.price) / a.price > tolerance:
        return None
    neckline = b.price
    if latest_close >= neckline:
        return None
    return {"neckline": neckline, "resistance": max(a.price, c.price)}
