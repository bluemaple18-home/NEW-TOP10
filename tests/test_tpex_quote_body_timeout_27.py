"""TPEX 讀取暫時失敗與同日覆蓋率的離線反例。"""

from __future__ import annotations

import asyncio
import logging

import aiohttp
import pandas as pd
import pytest

from app import data_fetcher
from app.data_fetcher import AsyncTPEXFetcher
from app.pipeline.validation import DatasetContract, PipelineDataValidator


def quote_payload(date: str = "115/10/27") -> dict:
    return {
        "tables": [{
            "title": "上櫃股票每日收盤行情(不含定價)",
            "date": date,
            "fields": ["代號", "名稱", "開盤", "最高", "最低", "收盤", "成交股數", "成交金額(元)"],
            "data": [["6488", "環球晶", "100", "101", "99", "100", "1,000", "100,000"]],
        }],
    }


def quote_payload_without_close() -> dict:
    payload = quote_payload()
    payload["tables"][0]["data"][0][5] = "---"
    return payload


class FakeResponse:
    def __init__(self, value: object, status: int = 200):
        self.value = value
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self):
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value


class FakeSession:
    def __init__(self, responses: list[FakeResponse | BaseException]):
        self.responses = responses
        self.calls = 0

    def get(self, _url, *, params, headers, timeout):
        assert params["d"] == "115/10/27"
        assert headers["User-Agent"]
        assert timeout == 60
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, BaseException):
            raise response
        return response


@pytest.mark.parametrize("first_error", [TimeoutError(), aiohttp.ClientPayloadError("partial")])
def test_transient_body_read_retries_same_date(monkeypatch, caplog, first_error):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(data_fetcher.asyncio, "sleep", fake_sleep)
    session = FakeSession([FakeResponse(first_error), FakeResponse(quote_payload())])
    fetcher = AsyncTPEXFetcher(session)
    with caplog.at_level(logging.INFO, logger="app.data_fetcher"):
        frame = asyncio.run(fetcher.fetch_daily_quotes("20261027"))

    assert session.calls == 2
    assert sleeps == [0.8]
    assert frame is not None and frame.iloc[0]["date"] == pd.Timestamp("2026-10-27")
    assert fetcher.data_source_log[0]["records"] == 1
    assert "date=20261027 stage=body_read http_status=200 attempt=1/3" in caplog.text
    assert f"exception_type={type(first_error).__name__}" in caplog.text
    assert "TPEX 重試成功 date=20261027 attempt=2/3" in caplog.text


def test_timeout_exhaustion_fails_closed(monkeypatch, caplog):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(data_fetcher.asyncio, "sleep", fake_sleep)
    fallback_calls = []

    def fallback(*_args, **kwargs):
        assert kwargs['timeout'] == 60
        assert kwargs['params']['d'] == '115/10/27'
        fallback_calls.append(kwargs)

        class TimedOutBody:
            status_code = 200

            def close(self):
                pass

            def json(self):
                raise TimeoutError()

        return TimedOutBody()

    monkeypatch.setattr(data_fetcher.requests, 'get', fallback)
    session = FakeSession([FakeResponse(TimeoutError()) for _ in range(2)])
    fetcher = AsyncTPEXFetcher(session)
    with caplog.at_level(logging.WARNING, logger="app.data_fetcher"):
        frame = asyncio.run(fetcher.fetch_daily_quotes("20261027"))

    assert frame is None
    assert fetcher.data_source_log == []
    assert session.calls == 2
    assert len(fallback_calls) == 1
    assert sleeps == [0.8, 1.6]
    assert all(f"date=20261027 stage=body_read http_status=200 attempt={i}/3" in caplog.text for i in (1, 2))
    assert "date=20261027 stage=requests_body http_status=None attempt=3/3" in caplog.text
    assert "attempt=3/3 exception_type=TimeoutError retry_exhausted=True" in caplog.text


def test_connection_timeout_records_request_stage(monkeypatch, caplog):
    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(data_fetcher.asyncio, "sleep", fake_sleep)
    session = FakeSession([TimeoutError(), FakeResponse(quote_payload())])
    with caplog.at_level(logging.WARNING, logger="app.data_fetcher"):
        frame = asyncio.run(AsyncTPEXFetcher(session).fetch_daily_quotes("20261027"))

    assert frame is not None
    assert session.calls == 2
    assert "date=20261027 stage=request http_status=None attempt=1/3 exception_type=TimeoutError" in caplog.text


@pytest.mark.parametrize("payload", [{"tables": []}, quote_payload_without_close()])
def test_retry_then_empty_quotes_does_not_report_success(monkeypatch, caplog, payload):
    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(data_fetcher.asyncio, "sleep", fake_sleep)
    session = FakeSession([FakeResponse(TimeoutError()), FakeResponse(payload)])
    fetcher = AsyncTPEXFetcher(session)
    with caplog.at_level(logging.INFO, logger="app.data_fetcher"):
        frame = asyncio.run(fetcher.fetch_daily_quotes("20261027"))

    assert frame is None
    assert session.calls == 2
    assert fetcher.data_source_log == []
    assert "TPEX 重試成功" not in caplog.text


@pytest.mark.parametrize("payload", [quote_payload("115/10/26"), {**quote_payload(), "date": "115/10/26"}])
def test_wrong_response_date_is_rejected_without_retry(caplog, payload):
    session = FakeSession([FakeResponse(payload)])
    with caplog.at_level(logging.WARNING, logger="app.data_fetcher"):
        frame = asyncio.run(AsyncTPEXFetcher(session).fetch_daily_quotes("20261027"))

    assert frame is None
    assert session.calls == 1
    assert "exception_type=DateMismatch" in caplog.text


@pytest.mark.parametrize(
    ("top_date", "table_date", "accepted"),
    [
        ("20261027", "115/10/27", True),
        (20261027, "115/10/27", True),
        ("2026/10/27", "115/10/27", True),
        ("2026-10-27", "115/10/27", True),
        ("20261026", "115/10/27", False),
        ("20261027", "115/10/26", False),
    ],
)
def test_top_level_and_quote_table_dates_must_match_request(caplog, top_date, table_date, accepted):
    payload = quote_payload(table_date)
    payload["date"] = top_date
    session = FakeSession([FakeResponse(payload)])
    fetcher = AsyncTPEXFetcher(session)
    with caplog.at_level(logging.WARNING, logger="app.data_fetcher"):
        frame = asyncio.run(fetcher.fetch_daily_quotes("20261027"))

    assert session.calls == 1
    if accepted:
        assert frame is not None and frame.iloc[0]["date"] == pd.Timestamp("2026-10-27")
        assert fetcher.data_source_log[0]["records"] == 1
        assert "exception_type=DateMismatch" not in caplog.text
    else:
        assert frame is None
        assert fetcher.data_source_log == []
        assert "exception_type=DateMismatch" in caplog.text


def test_legacy_quote_without_response_dates_remains_accepted(caplog):
    payload = quote_payload()
    del payload["tables"][0]["date"]
    session = FakeSession([FakeResponse(payload)])
    fetcher = AsyncTPEXFetcher(session)

    with caplog.at_level(logging.WARNING, logger="app.data_fetcher"):
        frame = asyncio.run(fetcher.fetch_daily_quotes("20261027"))

    assert session.calls == 1
    assert frame is not None and frame.iloc[0]["date"] == pd.Timestamp("2026-10-27")
    assert fetcher.data_source_log[0]["records"] == 1
    assert "exception_type=DateMismatch" not in caplog.text


@pytest.mark.parametrize(
    "response",
    [FakeResponse(quote_payload(), status=503), FakeResponse(ValueError("invalid json")), FakeResponse({"tables": []})],
)
def test_non_transient_or_empty_response_is_not_success(response):
    session = FakeSession([response])
    fetcher = AsyncTPEXFetcher(session)
    assert asyncio.run(fetcher.fetch_daily_quotes("20261027")) is None
    assert session.calls == 1
    assert fetcher.data_source_log == []


def test_cancellation_is_not_swallowed():
    session = FakeSession([FakeResponse(asyncio.CancelledError())])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(AsyncTPEXFetcher(session).fetch_daily_quotes("20261027"))
    assert session.calls == 1


def test_latest_date_tpex_zero_still_fails_coverage_gate(tmp_path, monkeypatch):
    clean_dir = tmp_path / "data" / "clean"
    clean_dir.mkdir(parents=True)
    features = clean_dir / "features.parquet"
    pd.DataFrame([
        {"date": "2026-10-22", "stock_id": "6488", "market": "TPEX", "close": 100},
        {"date": "2026-10-27", "stock_id": "2330", "market": "TWSE", "close": 500},
    ]).to_parquet(features)
    validator = PipelineDataValidator(data_dir=tmp_path / "data")
    monkeypatch.setattr(validator, "_daily_market_coverage_config", lambda: {
        "enabled": True, "required_markets": ["twse", "tpex"], "min_ratio": 0.5,
    })
    monkeypatch.setattr(validator, "_expected_market_counts", lambda _markets: {"twse": 1, "tpex": 1})
    contract = DatasetContract(name="features", path=features, required_columns=("date", "stock_id", "market", "close"))
    summary = validator.validate_contract(contract)

    assert any(
        issue.severity == "ERROR" and "TPEX actual=0 expected=1 ratio=0.0 < min=0.5" in issue.message
        for issue in summary.issues
    )
