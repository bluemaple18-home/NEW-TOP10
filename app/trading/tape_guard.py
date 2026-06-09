"""當日價格行為 guard。

模型可以抓出前段資金痕跡，但每日推薦仍需要先判斷當天 tape 是否失控。
這裡只做薄判斷：跌停、近跌停、收最低大跌不得被包裝成主攻轉強。
"""

from __future__ import annotations

from typing import Any

import pandas as pd


BLOCK_STATES = {"ONE_PRICE_LIMIT_DOWN", "LIMIT_DOWN", "NEAR_LIMIT_DOWN"}
DOWNGRADE_STATES = {"CLOSE_LOW_BIG_DROP"}


def add_tape_guard_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """補上 return / limit_state / guard 欄位，供 ranking、report、publish 共用。"""
    df = frame.copy()
    if df.empty:
        return df

    open_ = _numeric_series(df, "open")
    high = _numeric_series(df, "high")
    low = _numeric_series(df, "low")
    close = _numeric_series(df, "close")
    prev_close = _numeric_series(df, "prev_close")

    if "return_pct" not in df.columns:
        df["return_pct"] = ((close / prev_close) - 1.0) * 100.0
    else:
        df["return_pct"] = pd.to_numeric(df["return_pct"], errors="coerce")

    intraday_range = high - low
    df["intraday_position"] = ((close - low) / intraday_range).where(intraday_range > 0)
    df["one_price_locked"] = (
        open_.notna()
        & high.notna()
        & low.notna()
        & close.notna()
        & open_.eq(high)
        & high.eq(low)
        & low.eq(close)
    )
    close_at_low = (close - low).abs().le(1e-9)
    return_pct = pd.to_numeric(df["return_pct"], errors="coerce")

    states = pd.Series("NORMAL", index=df.index, dtype="object")
    states = states.mask((return_pct <= -8.8) & df["one_price_locked"], "ONE_PRICE_LIMIT_DOWN")
    states = states.mask((states == "NORMAL") & (return_pct <= -9.5), "LIMIT_DOWN")
    states = states.mask(
        (states == "NORMAL")
        & (return_pct <= -8.0)
        & (close_at_low | df["intraday_position"].fillna(0).le(0.1)),
        "NEAR_LIMIT_DOWN",
    )
    states = states.mask(
        (states == "NORMAL")
        & (return_pct <= -4.0)
        & (close_at_low | df["intraday_position"].fillna(0).le(0.1)),
        "CLOSE_LOW_BIG_DROP",
    )
    states = states.mask((states == "NORMAL") & (return_pct < 0), "NEGATIVE_TAPE")
    df["limit_state"] = states

    actions = pd.Series("ALLOW", index=df.index, dtype="object")
    actions = actions.mask(states.isin(BLOCK_STATES), "EXCLUDE")
    actions = actions.mask(states.isin(DOWNGRADE_STATES), "DOWNGRADE")
    actions = actions.mask((states == "NEGATIVE_TAPE"), "COPY_GUARD")
    df["tape_guard_action"] = actions
    df["tape_guard_reason"] = states.map(TAPE_STATE_REASONS).fillna("")
    return df


def tape_guard_from_mapping(item: dict[str, Any]) -> dict[str, Any]:
    """從 report/payload item 取回 tape guard 狀態。"""
    tape = item.get("tape") if isinstance(item.get("tape"), dict) else {}
    state = str(tape.get("limit_state") or item.get("limit_state") or "NORMAL")
    action = str(tape.get("tape_guard_action") or item.get("tape_guard_action") or "")
    if not action:
        if state in BLOCK_STATES:
            action = "EXCLUDE"
        elif state in DOWNGRADE_STATES:
            action = "DOWNGRADE"
        elif state == "NEGATIVE_TAPE":
            action = "COPY_GUARD"
        else:
            action = "ALLOW"
    return {
        "limit_state": state,
        "tape_guard_action": action,
        "tape_guard_reason": str(tape.get("tape_guard_reason") or item.get("tape_guard_reason") or TAPE_STATE_REASONS.get(state, "")),
        "return_pct": _number(tape.get("return_pct") if tape else item.get("return_pct")),
        "intraday_position": _number(tape.get("intraday_position") if tape else item.get("intraday_position")),
        "open": _number(tape.get("open") if tape else item.get("open")),
        "high": _number(tape.get("high") if tape else item.get("high")),
        "low": _number(tape.get("low") if tape else item.get("low")),
        "prev_close": _number(tape.get("prev_close") if tape else item.get("prev_close")),
    }


def tape_blocks_bullish_language(item: dict[str, Any]) -> bool:
    guard = tape_guard_from_mapping(item)
    action = guard.get("tape_guard_action")
    return action in {"EXCLUDE", "DOWNGRADE", "COPY_GUARD"} or (guard.get("return_pct") is not None and guard["return_pct"] < 0)


def tape_excludes_primary(item: dict[str, Any]) -> bool:
    return tape_guard_from_mapping(item).get("tape_guard_action") == "EXCLUDE"


TAPE_STATE_REASONS = {
    "ONE_PRICE_LIMIT_DOWN": "一字跌停，當天沒有給出正常換手觀察點",
    "LIMIT_DOWN": "接近跌停，賣壓明顯失控",
    "NEAR_LIMIT_DOWN": "接近跌停且收在低位，先視為風險事件",
    "CLOSE_LOW_BIG_DROP": "大跌且收在低位，不能當作轉強訊號",
    "NEGATIVE_TAPE": "當日價格偏弱，正向指標只能當背景，不可直接解讀成轉強",
    "NORMAL": "",
}


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")
    return pd.to_numeric(df[column], errors="coerce")


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed
