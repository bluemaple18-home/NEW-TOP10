#!/usr/bin/env python3
"""驗證 TWSE 307 / 429 類暫時性狀態會 retry 後成功解析。"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.data_fetcher as data_fetcher
from app.data_fetcher import AsyncTWSEFetcher


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None):
        self.status = status
        self.payload = payload or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return FakeResponse(307)
        return FakeResponse(
            200,
            {
                "stat": "OK",
                "tables": [
                    {
                        "title": "每日收盤行情",
                        "fields": ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
                        "data": [["2330", "台積電", "1,000", "50", "500,000", "500", "510", "495", "505"]],
                    }
                ],
            },
        )


async def fake_sleep(_seconds: float) -> None:
    return None


async def verify() -> None:
    original_sleep = data_fetcher.asyncio.sleep
    data_fetcher.asyncio.sleep = fake_sleep
    try:
        session = FakeSession()
        result = await AsyncTWSEFetcher(session).fetch_daily_quotes("20260525")
    finally:
        data_fetcher.asyncio.sleep = original_sleep
    assert session.calls == 2
    assert result is not None
    assert len(result) == 1
    assert result.iloc[0]["stock_id"] == "2330"
    assert int(result.iloc[0]["transactions"]) == 50


def main() -> int:
    asyncio.run(verify())
    print("TWSE_FETCH_RETRY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
