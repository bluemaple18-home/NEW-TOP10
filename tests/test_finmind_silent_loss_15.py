"""FinMind 逐檔失敗與 Daily 既有統計欄位的離線反例。"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.finmind_fetcher import FinMindFetcher
from app.finmind_integrator import FinMindIntegrator
from app.pipeline import fetch_stage


def _quotes(count: int = 200) -> pd.DataFrame:
    return pd.DataFrame([
        {"date": pd.Timestamp("2026-10-22"), "stock_id": str(1000 + index),
         "stock_name": f"股票{index}", "market": "TWSE", "open": 10,
         "high": 11, "low": 9, "close": 10, "volume": 1000 + index,
         "value": 10 * (1000 + index)}
        for index in range(count)
    ])


class _FakeFinMind:
    def __init__(self, *, fail_margin_after: int | None = None, fail_institutional: bool = False):
        self.fail_margin_after = fail_margin_after
        self.fail_institutional = fail_institutional

    def get_institutional_investors(self, stock_id: str, *_dates: str) -> pd.DataFrame:
        if self.fail_institutional:
            raise RuntimeError("離線法人例外")
        return pd.DataFrame([
            {"date": "2026-10-22", "stock_id": stock_id, "name": name, "buy": 10, "sell": 1}
            for name in ("Foreign_Investor", "Investment_Trust", "Dealer")
        ])

    def get_margin_purchase_short_sale(self, stock_id: str, *_dates: str) -> pd.DataFrame:
        if self.fail_margin_after is not None and int(stock_id) >= 1000 + self.fail_margin_after:
            raise RuntimeError("離線融資融券例外")
        return pd.DataFrame({"date": ["2026-10-22"], "MarginPurchaseTodayBalance": [10],
                             "MarginPurchaseYesterdayBalance": [9], "ShortSaleTodayBalance": [1],
                             "ShortSaleYesterdayBalance": [1]})


def _stage_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quotes: pd.DataFrame,
                   integrator: FinMindIntegrator) -> dict:
    class _OfflineOrchestrator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def fetch_historical_data(self, **_kwargs: object) -> pd.DataFrame:
            return quotes.copy()

        def fetch_suspended_stocks_list(self) -> list[str]:
            return []

    monkeypatch.delenv("TOP10_STORAGE_VALIDATION_MODE", raising=False)
    monkeypatch.setattr(fetch_stage, "DataFetcherOrchestrator", _OfflineOrchestrator)
    monkeypatch.setattr(fetch_stage, "FinMindIntegrator", lambda **_kwargs: integrator)
    monkeypatch.setattr(fetch_stage, "_finmind_token", lambda: None)
    monkeypatch.setattr(fetch_stage, "preflight_finmind_quota", lambda _token, required: {
        "limit": 1000, "used": 0, "remaining": 1000,
        "next_available_time": "2026-10-28T13:00:00+08:00", "required_fetch_count": required,
    })
    monkeypatch.setattr(fetch_stage, "materialize_daily_close_snapshot", lambda *_args, **_kwargs: SimpleNamespace(
        frame=quotes.copy(), manifest={"snapshot_id": "offline", "identity_payload": {
            "records_content_id": "offline", "coverage": {}, "resolution_status": "finalized"}},
        manifest_path=tmp_path / "manifest.json", records_path=tmp_path / "records.parquet"))
    monkeypatch.setattr(fetch_stage.FetchStage, "_filter_tradable_universe", lambda _self, frame, _context: frame)
    monkeypatch.setattr(fetch_stage.FetchStage, "_dedupe_trade_keys", lambda _self, frame, _context: frame)
    return {"start_date": "2026-10-22", "end_date": "2026-10-22", "dirs": {"raw": tmp_path}, "stats": {}}


def test_fetcher_exceptions_log_stock_and_type_without_empty_success(caplog: pytest.LogCaptureFixture) -> None:
    class _BrokenApi:
        def taiwan_stock_margin_purchase_short_sale(self, **_kwargs: str) -> pd.DataFrame:
            raise TimeoutError("離線逾時")

        def taiwan_daily_short_sale_balances(self, **_kwargs: str) -> pd.DataFrame:
            raise ConnectionError("離線連線失敗")

    fetcher = FinMindFetcher.__new__(FinMindFetcher)
    fetcher.api = _BrokenApi()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError, match="2330"):
            fetcher.get_margin_purchase_short_sale("2330", "2026-10-22", "2026-10-22")
        with pytest.raises(RuntimeError, match="2454"):
            fetcher.get_daily_short_sale_balances("2454", "2026-10-22", "2026-10-22")
    assert "stock_id=2330 error_type=TimeoutError" in caplog.text
    assert "stock_id=2454 error_type=ConnectionError" in caplog.text


def test_last_100_of_200_margin_failures_are_counted_in_stage_stats(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    quotes = _quotes()
    integrator = FinMindIntegrator(offline=True)
    integrator.fetcher = _FakeFinMind(fail_margin_after=100)
    context = _stage_context(monkeypatch, tmp_path, quotes, integrator)
    with caplog.at_level(logging.WARNING):
        enriched = fetch_stage.FetchStage().execute(pd.DataFrame(), context)
    stats = context["stats"]["finmind"]
    assert len(enriched) == 200
    assert stats["status"] == "partial"
    assert stats["failed_stock_count"] == 100
    assert stats["expected_fetch_count"] == 400
    assert stats["received_fetch_count"] == 300
    assert stats["failed_fetch_count"] == 100
    assert stats["by_dataset"]["margin"] == {
        "expected_stock_count": 200, "received_stock_count": 100, "failed_stock_count": 100}
    assert "stock_id=1199 error_type=RuntimeError" in caplog.text
    assert "failed_stock_count=100" in caplog.text


def test_institutional_exceptions_keep_failure_count_on_fail_loud_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    quotes = _quotes(2)
    integrator = FinMindIntegrator(offline=True)
    integrator.fetcher = _FakeFinMind(fail_institutional=True)
    context = _stage_context(monkeypatch, tmp_path, quotes, integrator)
    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError, match="離線法人例外"):
        fetch_stage.FetchStage().execute(pd.DataFrame(), context)
    stats = context["stats"]["finmind"]
    assert stats["status"] == "failed"
    assert stats["failed_stock_count"] == 1
    assert stats["by_dataset"]["institutional"]["failed_stock_count"] == 1
    assert "stock_id=1001 error_type=RuntimeError" in caplog.text
    assert "failed_stock_count=1" in caplog.text
