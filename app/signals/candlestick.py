"""K 線型態訊號。"""

from __future__ import annotations

import numpy as np
import pandas as pd


CANDLESTICK_COLUMNS = (
    "candle_hammer",
    "candle_hanging_man",
    "candle_shooting_star",
    "candle_inverted_hammer",
    "candle_doji",
    "candle_dragonfly_doji",
    "candle_tombstone_doji",
    "candle_bull_marubozu",
    "candle_bear_marubozu",
    "candle_bull_engulfing",
    "candle_bear_engulfing",
    "candle_bull_harami",
    "candle_bear_harami",
    "candle_piercing",
    "candle_dark_cloud",
    "candle_morning_star",
    "candle_evening_star",
    "candle_3white",
    "candle_3black",
)


def add_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """新增常見 K 線型態欄位。

    訊號只使用當日與過去 K 棒，避免偷看未來。
    """

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"K 線型態缺少必要欄位：{sorted(missing)}")

    result = df.copy()
    open_ = pd.to_numeric(result["open"], errors="coerce")
    high = pd.to_numeric(result["high"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    close = pd.to_numeric(result["close"], errors="coerce")

    body = (close - open_).abs()
    candle_range = (high - low).replace(0, np.nan)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low
    bullish = close > open_
    bearish = close < open_
    body_ratio = body / candle_range

    result["candle_doji"] = (body_ratio <= 0.10).astype(int)
    result["candle_dragonfly_doji"] = (
        (result["candle_doji"] == 1)
        & ((lower_shadow / candle_range) >= 0.60)
        & ((upper_shadow / candle_range) <= 0.15)
    ).astype(int)
    result["candle_tombstone_doji"] = (
        (result["candle_doji"] == 1)
        & ((upper_shadow / candle_range) >= 0.60)
        & ((lower_shadow / candle_range) <= 0.15)
    ).astype(int)

    result["candle_hammer"] = (
        (lower_shadow >= body * 2)
        & (upper_shadow <= body * 0.6)
        & ((body / candle_range) <= 0.45)
    ).astype(int)
    result["candle_hanging_man"] = result["candle_hammer"]
    result["candle_shooting_star"] = (
        (upper_shadow >= body * 2)
        & (lower_shadow <= body * 0.6)
        & ((body / candle_range) <= 0.45)
    ).astype(int)
    result["candle_inverted_hammer"] = result["candle_shooting_star"]

    result["candle_bull_marubozu"] = (bullish & (body_ratio >= 0.85)).astype(int)
    result["candle_bear_marubozu"] = (bearish & (body_ratio >= 0.85)).astype(int)

    prev_open = _group_shift(result, "open", 1)
    prev_close = _group_shift(result, "close", 1)
    prev_bullish = prev_close > prev_open
    prev_bearish = prev_close < prev_open

    result["candle_bull_engulfing"] = (
        bullish
        & prev_bearish
        & (open_ <= prev_close)
        & (close >= prev_open)
    ).astype(int)
    result["candle_bear_engulfing"] = (
        bearish
        & prev_bullish
        & (open_ >= prev_close)
        & (close <= prev_open)
    ).astype(int)

    result["candle_bull_harami"] = (
        bullish
        & prev_bearish
        & (open_ >= prev_close)
        & (close <= prev_open)
    ).astype(int)
    result["candle_bear_harami"] = (
        bearish
        & prev_bullish
        & (open_ <= prev_close)
        & (close >= prev_open)
    ).astype(int)

    prev_mid = (prev_open + prev_close) / 2
    result["candle_piercing"] = (
        bullish
        & prev_bearish
        & (open_ < prev_close)
        & (close > prev_mid)
        & (close < prev_open)
    ).astype(int)
    result["candle_dark_cloud"] = (
        bearish
        & prev_bullish
        & (open_ > prev_close)
        & (close < prev_mid)
        & (close > prev_open)
    ).astype(int)

    prev2_close = _group_shift(result, "close", 2)
    prev2_open = _group_shift(result, "open", 2)
    prev_body = (prev_close - prev_open).abs()
    result["candle_morning_star"] = (
        (prev2_close < prev2_open)
        & (prev_body <= body.rolling(5, min_periods=1).mean() * 0.8)
        & bullish
        & (close > ((prev2_open + prev2_close) / 2))
    ).astype(int)
    result["candle_evening_star"] = (
        (prev2_close > prev2_open)
        & (prev_body <= body.rolling(5, min_periods=1).mean() * 0.8)
        & bearish
        & (close < ((prev2_open + prev2_close) / 2))
    ).astype(int)

    prev1_bull = prev_close > prev_open
    prev2_bull = prev2_close > prev2_open
    prev1_bear = prev_close < prev_open
    prev2_bear = prev2_close < prev2_open
    result["candle_3white"] = (bullish & prev1_bull & prev2_bull & (close > prev_close) & (prev_close > prev2_close)).astype(int)
    result["candle_3black"] = (bearish & prev1_bear & prev2_bear & (close < prev_close) & (prev_close < prev2_close)).astype(int)

    for col in CANDLESTICK_COLUMNS:
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0).astype(int)
    return result


def _group_shift(df: pd.DataFrame, column: str, periods: int) -> pd.Series:
    if "stock_id" not in df.columns:
        return pd.to_numeric(df[column], errors="coerce").shift(periods)
    return pd.to_numeric(df[column], errors="coerce").groupby(df["stock_id"], sort=False).shift(periods)
