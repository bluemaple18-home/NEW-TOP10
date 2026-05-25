"""TD Sequential 九轉訊號。"""

from __future__ import annotations

import pandas as pd


TD_COLUMNS = ("td_count", "td_buy_setup", "td_sell_setup")


def add_td_sequential(df: pd.DataFrame) -> pd.DataFrame:
    """新增 TD 九轉欄位。

    `td_count`：正數代表上漲 setup，負數代表下跌 setup。
    `td_buy_setup`：下跌 setup 到第九根。
    `td_sell_setup`：上漲 setup 到第九根。
    """

    required = {"date", "stock_id", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"TD 九轉缺少必要欄位：{sorted(missing)}")

    result = df.copy().sort_values(["stock_id", "date"]).copy()
    td_count = pd.Series(0, index=result.index, dtype="int64")

    for _, stock_frame in result.groupby("stock_id", sort=False):
        closes = pd.to_numeric(stock_frame["close"], errors="coerce").reset_index(drop=True)
        counts: list[int] = []
        up_count = 0
        down_count = 0
        for idx, close in enumerate(closes):
            if idx < 4 or pd.isna(close) or pd.isna(closes.iloc[idx - 4]):
                up_count = 0
                down_count = 0
                counts.append(0)
                continue
            if close > closes.iloc[idx - 4]:
                up_count += 1
                down_count = 0
                counts.append(up_count)
            elif close < closes.iloc[idx - 4]:
                down_count += 1
                up_count = 0
                counts.append(-down_count)
            else:
                up_count = 0
                down_count = 0
                counts.append(0)
        td_count.loc[stock_frame.index] = counts

    result["td_count"] = td_count
    result["td_buy_setup"] = (result["td_count"] <= -9).astype(int)
    result["td_sell_setup"] = (result["td_count"] >= 9).astype(int)
    return result.sort_index()
