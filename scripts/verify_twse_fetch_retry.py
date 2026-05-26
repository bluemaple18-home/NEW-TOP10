#!/usr/bin/env python3
"""驗證 TWSE 307 retry / fallback 邊界。"""

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


class FakeNonJsonResponse(FakeResponse):
    async def json(self):
        raise ValueError("not json")


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


class AlwaysRedirectSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse(307)


class SingleStatusSession:
    def __init__(self, status: int):
        self.status = status
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse(self.status)


class InvalidPayloadSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse(200, {"stat": "很抱歉，沒有符合條件的資料"})


class NonJsonThenSuccessSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return FakeNonJsonResponse(200)
        return FakeResponse(
            200,
            {
                "stat": "OK",
                "tables": [
                    {
                        "title": "每日收盤行情",
                        "fields": ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
                        "data": [["2303", "聯電", "3,000", "90", "120,000", "40", "41", "39", "40.5"]],
                    }
                ],
            },
        )


class FakeRequestsResponse:
    status_code = 200

    def json(self):
        return {
            "stat": "OK",
            "tables": [
                {
                    "title": "每日收盤行情",
                    "fields": ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
                    "data": [["2317", "鴻海", "2,000", "80", "900,000", "200", "205", "198", "204"]],
                }
            ],
        }


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
    await verify_requests_fallback()
    await verify_non_json_response_retries_without_fallback()
    await verify_rate_limit_status_does_not_fallback()
    await verify_non_retry_status_does_not_fallback()
    await verify_non_transient_payload_does_not_fallback()


async def verify_requests_fallback() -> None:
    original_sleep = data_fetcher.asyncio.sleep
    original_get = data_fetcher.requests.get
    calls = {"requests": 0}

    def fake_get(*args, **kwargs):
        calls["requests"] += 1
        return FakeRequestsResponse()

    data_fetcher.asyncio.sleep = fake_sleep
    data_fetcher.requests.get = fake_get
    try:
        session = AlwaysRedirectSession()
        result = await AsyncTWSEFetcher(session).fetch_daily_quotes("20260525")
    finally:
        data_fetcher.asyncio.sleep = original_sleep
        data_fetcher.requests.get = original_get
    assert session.calls == 4
    assert calls["requests"] == 1
    assert result is not None
    assert len(result) == 1
    assert result.iloc[0]["stock_id"] == "2317"


async def verify_non_json_response_retries_without_fallback() -> None:
    original_sleep = data_fetcher.asyncio.sleep
    original_get = data_fetcher.requests.get
    calls = {"requests": 0}

    def fake_get(*args, **kwargs):
        calls["requests"] += 1
        return FakeRequestsResponse()

    data_fetcher.asyncio.sleep = fake_sleep
    data_fetcher.requests.get = fake_get
    try:
        session = NonJsonThenSuccessSession()
        result = await AsyncTWSEFetcher(session).fetch_daily_quotes("20260525")
    finally:
        data_fetcher.asyncio.sleep = original_sleep
        data_fetcher.requests.get = original_get
    assert session.calls == 2
    assert calls["requests"] == 0
    assert result is not None
    assert len(result) == 1
    assert result.iloc[0]["stock_id"] == "2303"


async def verify_rate_limit_status_does_not_fallback() -> None:
    original_sleep = data_fetcher.asyncio.sleep
    original_get = data_fetcher.requests.get
    calls = {"requests": 0}

    def fake_get(*args, **kwargs):
        calls["requests"] += 1
        return FakeRequestsResponse()

    data_fetcher.asyncio.sleep = fake_sleep
    data_fetcher.requests.get = fake_get
    try:
        session = SingleStatusSession(429)
        result = await AsyncTWSEFetcher(session).fetch_daily_quotes("20260525")
    finally:
        data_fetcher.asyncio.sleep = original_sleep
        data_fetcher.requests.get = original_get
    assert session.calls == 4
    assert calls["requests"] == 0
    assert result is None


async def verify_non_retry_status_does_not_fallback() -> None:
    original_get = data_fetcher.requests.get
    calls = {"requests": 0}

    def fake_get(*args, **kwargs):
        calls["requests"] += 1
        return FakeRequestsResponse()

    data_fetcher.requests.get = fake_get
    try:
        session = SingleStatusSession(404)
        result = await AsyncTWSEFetcher(session).fetch_daily_quotes("20260525")
    finally:
        data_fetcher.requests.get = original_get
    assert session.calls == 1
    assert calls["requests"] == 0
    assert result is None


async def verify_non_transient_payload_does_not_fallback() -> None:
    original_get = data_fetcher.requests.get
    calls = {"requests": 0}

    def fake_get(*args, **kwargs):
        calls["requests"] += 1
        return FakeRequestsResponse()

    data_fetcher.requests.get = fake_get
    try:
        session = InvalidPayloadSession()
        result = await AsyncTWSEFetcher(session).fetch_daily_quotes("20260525")
    finally:
        data_fetcher.requests.get = original_get
    assert session.calls == 1
    assert calls["requests"] == 0
    assert result is None


def main() -> int:
    asyncio.run(verify())
    print("TWSE_FETCH_RETRY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
