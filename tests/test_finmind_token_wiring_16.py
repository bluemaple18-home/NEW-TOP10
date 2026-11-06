"""FinMind token 接線、額度預檢與 402 分類的離線驗收。"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app import finmind_fetcher, finmind_integrator
from app.pipeline import fetch_stage
from app.pipeline.daily_close_snapshot import materialize_daily_close_snapshot


def _response(status: int, payload: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, json=lambda: payload)


def _stage_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, stock_count: int = 200) -> dict:
    quotes = pd.DataFrame([
        {"date": pd.Timestamp("2026-10-22"), "stock_id": str(1000 + index),
         "stock_name": f"股票{index}", "market": "TWSE", "open": 10,
         "high": 11, "low": 9, "close": 10, "volume": 1000 + index,
         "value": 10 * (1000 + index)}
        for index in range(stock_count)
    ])

    class _OfflineOrchestrator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def fetch_historical_data(self, **_kwargs: object) -> pd.DataFrame:
            return quotes.copy()

        def fetch_suspended_stocks_list(self) -> list[str]:
            return []

    monkeypatch.delenv("TOP10_STORAGE_VALIDATION_MODE", raising=False)
    monkeypatch.setattr(fetch_stage, "DataFetcherOrchestrator", _OfflineOrchestrator)
    def materialize_snapshot(*_args: object, **_kwargs: object) -> SimpleNamespace:
        manifest_path = tmp_path / "manifest.json"
        records_path = tmp_path / "records.parquet"
        manifest_path.write_text('{"snapshot_id":"offline"}', encoding="utf-8")
        records_path.write_bytes(b"offline snapshot")
        return SimpleNamespace(
            frame=quotes.copy(), manifest={"snapshot_id": "offline", "identity_payload": {
                "records_content_id": "offline", "coverage": {}, "resolution_status": "finalized"}},
            manifest_path=manifest_path, records_path=records_path)

    monkeypatch.setattr(fetch_stage, "materialize_daily_close_snapshot", materialize_snapshot)
    monkeypatch.setattr(fetch_stage.FetchStage, "_filter_tradable_universe", lambda _self, frame, _context: frame)
    monkeypatch.setattr(fetch_stage.FetchStage, "_dedupe_trade_keys", lambda _self, frame, _context: frame)
    return {"start_date": "2026-10-22", "end_date": "2026-10-22", "dirs": {"raw": tmp_path}, "stats": {}}


def test_fake_token_and_missing_token_use_one_sdk_construction(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    seen: list[str] = []

    class _FakeDataLoader:
        def __init__(self, token: str = "") -> None:
            seen.append(token)

    monkeypatch.setattr(finmind_fetcher, "DataLoader", _FakeDataLoader)
    with caplog.at_level(logging.INFO):
        finmind_fetcher.FinMindFetcher(token="fake-test-token")
        finmind_fetcher.FinMindFetcher(token=None)
    assert seen == ["fake-test-token", ""]
    assert "未提供 token" in caplog.text
    assert "fake-test-token" not in caplog.text


def test_env_value_precedes_private_file_and_missing_value_is_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    path = tmp_path / ".env"
    path.write_text("FINMIND_TOKEN=fake-file-token\n", encoding="utf-8")
    monkeypatch.setattr(fetch_stage, "FINMIND_ENV_FILE", path)
    monkeypatch.setenv("FINMIND_TOKEN", "fake-env-token")
    assert fetch_stage._finmind_token() == "fake-env-token"
    monkeypatch.delenv("FINMIND_TOKEN")
    assert fetch_stage._finmind_token() == "fake-file-token"
    path.unlink()
    assert fetch_stage._finmind_token() is None


@pytest.mark.parametrize("read_error", [PermissionError, OSError])
def test_unreadable_env_falls_back_without_exposing_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    read_error: type[OSError],
) -> None:
    path = tmp_path / ".env"
    monkeypatch.setattr(fetch_stage, "FINMIND_ENV_FILE", path)
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)

    def unreadable(_path: Path, **_kwargs: object) -> str:
        raise read_error("private-file-content-must-not-leak")

    monkeypatch.setattr(Path, "read_text", unreadable)
    with caplog.at_level(logging.WARNING):
        assert fetch_stage._finmind_token() is None
    assert "檔案不可讀" in caplog.text
    assert read_error.__name__ in caplog.text
    assert "private-file-content-must-not-leak" not in caplog.text


def test_user_info_is_called_once_and_parsed_without_token_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict] = []

    def fake_get(_url: str, **kwargs: object) -> SimpleNamespace:
        seen.append(kwargs)
        return _response(200, {"api_request_limit_hour": 600, "user_count": 125,
                               "next_available_time": "2026-10-28T13:00:00+08:00"})

    monkeypatch.setattr(finmind_integrator.requests, "get", fake_get)
    quota = finmind_integrator.preflight_finmind_quota("fake-test-token", 400)
    assert len(seen) == 1
    assert seen[0]["headers"] == {"Authorization": "Bearer fake-test-token"}
    assert quota == {"limit": 600, "used": 125, "remaining": 475,
                     "next_available_time": "2026-10-28T13:00:00+08:00",
                     "planned_data_fetch_count": 400, "sdk_login_cost": 1,
                     "required_fetch_count": 401}
    assert "fake-test-token" not in repr(quota)


def test_zero_used_and_empty_window_time_passes_with_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(finmind_integrator.requests, "get", lambda *_args, **_kwargs: _response(
        200, {"api_request_limit_hour": 600, "user_count": 0, "next_available_time": ""}))
    quota = finmind_integrator.preflight_finmind_quota("fake-test-token", 400)
    assert quota["limit"] == 600
    assert quota["used"] == 0
    assert quota["remaining"] == 600
    assert quota["next_available_time"] is None
    assert quota["required_fetch_count"] == 401


def test_used_quota_with_empty_window_time_remains_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(finmind_integrator.requests, "get", lambda *_args, **_kwargs: _response(
        200, {"api_request_limit_hour": 600, "user_count": 120, "next_available_time": ""}))
    with pytest.raises(finmind_integrator.FinMindQuotaError) as caught:
        finmind_integrator.preflight_finmind_quota("fake-test-token", 400)
    assert caught.value.reason_code == "FINMIND_QUOTA_PRECHECK_INVALID"


@pytest.mark.parametrize("payload", [
    {"api_request_limit_hour": 600, "user_count": 0},
    {"api_request_limit_hour": 600, "user_count": 0, "next_available_time": None},
    {"api_request_limit_hour": 400, "user_count": 0, "next_available_time": ""},
])
def test_empty_window_time_does_not_bypass_missing_fields_or_insufficient_quota(
    monkeypatch: pytest.MonkeyPatch, payload: dict,
) -> None:
    monkeypatch.setattr(finmind_integrator.requests, "get", lambda *_args, **_kwargs: _response(200, payload))
    with pytest.raises(finmind_integrator.FinMindQuotaError) as caught:
        finmind_integrator.preflight_finmind_quota("fake-test-token", 400)
    expected = (
        "FINMIND_QUOTA_INSUFFICIENT"
        if payload.get("api_request_limit_hour") == 400
        else "FINMIND_QUOTA_PRECHECK_INVALID"
    )
    assert caught.value.reason_code == expected


@pytest.mark.parametrize("used,should_pass", [(200, False), (199, True)])
def test_sdk_login_cost_is_reserved_at_quota_boundary(
    monkeypatch: pytest.MonkeyPatch, used: int, should_pass: bool,
) -> None:
    monkeypatch.setattr(finmind_integrator.requests, "get", lambda *_args, **_kwargs: _response(
        200, {"api_request_limit_hour": 600, "user_count": used,
              "next_available_time": "2026-10-28T13:00:00+08:00"}))
    if should_pass:
        quota = finmind_integrator.preflight_finmind_quota("fake-test-token", 400)
    else:
        with pytest.raises(finmind_integrator.FinMindQuotaError) as caught:
            finmind_integrator.preflight_finmind_quota("fake-test-token", 400)
        assert caught.value.reason_code == "FINMIND_QUOTA_INSUFFICIENT"
        quota = caught.value.quota
    assert quota["remaining"] == 600 - used
    assert quota["planned_data_fetch_count"] == 400
    assert quota["sdk_login_cost"] == 1
    assert quota["required_fetch_count"] == 401


def test_insufficient_precheck_stops_after_price_snapshot_before_integrator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    context = _stage_context(monkeypatch, tmp_path)
    monkeypatch.setattr(fetch_stage, "materialize_daily_close_snapshot", materialize_daily_close_snapshot)
    monkeypatch.setattr(fetch_stage, "_finmind_token", lambda: "fake-test-token")
    monkeypatch.setattr(finmind_integrator.requests, "get", lambda *_args, **_kwargs: _response(
        200, {"api_request_limit_hour": 600, "user_count": 250,
              "next_available_time": "2026-10-28T13:00:00+08:00"}))
    monkeypatch.setattr(fetch_stage, "FinMindIntegrator", lambda **_kwargs: pytest.fail("額度不足仍建構 FinMind"))
    with pytest.raises(finmind_integrator.FinMindQuotaError, match="FINMIND_QUOTA_INSUFFICIENT"):
        fetch_stage.FetchStage().execute(pd.DataFrame(), context)
    stats = context["stats"]["finmind"]
    assert stats["status"] == "quota_insufficient"
    assert (stats["limit"], stats["used"], stats["remaining"], stats["required_fetch_count"]) == (600, 250, 350, 401)
    assert stats["sdk_login_cost"] == 1
    assert stats["next_available_time"] == "2026-10-28T13:00:00+08:00"
    snapshot = context["stats"]["daily_close_snapshot"]
    assert Path(snapshot["manifest_path"]).is_file()
    assert Path(snapshot["records_path"]).is_file()
    assert "data_fetching" not in context["stats"]


def test_missing_token_cannot_use_registered_limit_from_user_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(finmind_integrator.requests, "get", lambda *_args, **_kwargs: _response(
        200, {"api_request_limit_hour": 600, "user_count": 0,
              "next_available_time": "2026-10-28T13:00:00+08:00"}))
    with pytest.raises(finmind_integrator.FinMindQuotaError) as caught:
        finmind_integrator.preflight_finmind_quota(None, 400)
    assert caught.value.reason_code == "FINMIND_QUOTA_INSUFFICIENT"
    assert caught.value.quota["limit"] == 300
    assert caught.value.quota["remaining"] == 300


def test_http_402_during_margin_fetch_is_distinct_and_stops_requests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    context = _stage_context(monkeypatch, tmp_path, stock_count=2)
    monkeypatch.setattr(fetch_stage, "_finmind_token", lambda: "fake-test-token")
    monkeypatch.setattr(fetch_stage, "preflight_finmind_quota", lambda _token, required: {
        "limit": 600, "used": 0, "remaining": 600,
        "next_available_time": "2026-10-28T13:00:00+08:00", "required_fetch_count": required,
    })
    attempts: list[str] = []

    class _FakeFetcher:
        def get_institutional_investors(self, stock_id: str, *_dates: str) -> pd.DataFrame:
            return pd.DataFrame([
                {"date": "2026-10-22", "stock_id": stock_id, "name": name, "buy": 10, "sell": 1}
                for name in ("Foreign_Investor", "Investment_Trust", "Dealer")
            ])

        def get_margin_purchase_short_sale(self, stock_id: str, *_dates: str) -> pd.DataFrame:
            attempts.append(stock_id)
            raise RuntimeError("FinMind 融資融券失敗") from Exception(
                "FinMind API unexpected response: Requests reach the upper limit."
            )

    integrator = finmind_integrator.FinMindIntegrator(offline=True)
    integrator.fetcher = _FakeFetcher()
    monkeypatch.setattr(fetch_stage, "FinMindIntegrator", lambda **_kwargs: integrator)
    with pytest.raises(finmind_integrator.FinMindQuotaError, match="FINMIND_QUOTA_EXHAUSTED"):
        fetch_stage.FetchStage().execute(pd.DataFrame(), context)
    assert len(attempts) == 1
    assert context["stats"]["finmind"]["status"] == "quota_exhausted"
    assert context["stats"]["finmind"]["failed_stock_count"] == 1
    assert context["stats"]["finmind"]["reason_code"] == "FINMIND_QUOTA_EXHAUSTED"
