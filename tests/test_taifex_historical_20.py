"""卡 20：歷史來源、編碼閘門與現行路徑隔離的離線反例。"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import market_context_fetcher as market
from app import taifex_historical as history
from tests.test_market_context_fetcher import DATE, official, replay


FIXTURES = Path(__file__).parent / "fixtures/taifex_historical_20"
CSV_HEADERS = {"Content-Type": "text/html;charset=MS950",
               "Content-Disposition": "attachment;filename=sample.csv"}


def sample(section, fmt="csv"):
    text = (FIXTURES / f"{section}.{fmt}").read_text()
    return text.encode("big5" if fmt == "csv" else "utf-8")


def response(content, headers=None):
    return SimpleNamespace(content=content, headers=headers or CSV_HEADERS,
                           status_code=200, raise_for_status=lambda: None)


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("歷史來源單元測試禁止網路")
    monkeypatch.setattr(history.requests.sessions.Session, "request", deny)


@pytest.mark.parametrize("section", ["futures", "oi"])
def test_csv_and_html_match_official_openapi(section):
    expected = market.parse_taifex_payloads(official("taifex-futures"), official("taifex-pcr"), official("taifex-oi"), DATE)
    for parser, fmt in [(history.parse_csv, "csv"), (history.parse_html, "html")]:
        rows = parser(sample(section, fmt), section, DATE)
        actual = market.parse_taifex_payloads(rows if section == "futures" else official("taifex-futures"),
                                             official("taifex-pcr"), rows if section == "oi" else official("taifex-oi"), DATE)
        assert actual == expected
    assert expected[0]["tx_volume"] == 55226  # 非盤後 35753、非合計 90979。
    assert expected[1]["foreign_oi"] == -87297  # 非交易淨口數 -1221、非契約金額。


@pytest.mark.parametrize("headers, expected", [
    ({"Content-Type": "text/csv"}, True),
    (CSV_HEADERS, True),
    ({"Content-Type": "text/html;charset=UTF-8"}, False),
    ({"Content-Type": "text/html;charset=MS950"}, False),
    ({"Content-Type": "text/html;charset=UTF-8", "Content-Disposition": "attachment;filename=x.csv"}, False),
    ({}, False),
])
def test_header_gate_requires_csv_evidence(headers, expected):
    assert history.is_csv_response(headers) is expected


@pytest.mark.parametrize("section", ["futures", "oi"])
def test_corrupt_big5_fails_loud_without_html_fallback(monkeypatch, section):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        return response(b"\x81")
    monkeypatch.setattr(history.requests, "post", post)
    with pytest.raises(UnicodeDecodeError):
        history.fetch_historical(section, DATE, headers={})
    assert len(calls) == 1


def test_non_csv_does_not_decode_big5_and_remains_unavailable(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        return response(b"\xff", {"Content-Type": "text/html;charset=UTF-8"})
    monkeypatch.setattr(history.requests, "post", post)
    monkeypatch.setattr(history, "parse_csv", lambda *a: pytest.fail("非 CSV 不得進 Big5 解碼"))
    rows, info = history.fetch_historical("oi", "2026-10-23", headers={})
    assert rows == [] and info["status"] == "unavailable_historical"
    assert info["csv_confirmed"] is False and info["reason_code"] == "html_encoding_unavailable"
    assert len(calls) == 2


def test_non_csv_http_error_is_diagnosed_before_decoding(monkeypatch):
    unavailable = response(b"\x81", {"Content-Type": "text/html;charset=UTF-8"})
    unavailable.status_code = 404
    unavailable.raise_for_status = lambda: pytest.fail("非 CSV 應保留 unavailable 診斷")
    monkeypatch.setattr(history.requests, "post", lambda *a, **k: unavailable)
    rows, info = history.fetch_historical("oi", DATE, headers={})
    assert rows == [] and info["status"] == "unavailable_historical"
    assert info["http_status"] == info["html_http_status"] == 404


@pytest.mark.parametrize("section", ["futures", "oi"])
def test_html_fallback_only_after_non_csv(monkeypatch, section):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response(b"not csv" if len(calls) == 1 else sample(section, "html"),
                        {"Content-Type": "text/html;charset=UTF-8"})
    monkeypatch.setattr(history.requests, "post", post)
    rows, info = history.fetch_historical(section, DATE, headers={})
    assert rows and info["status"] == "ok" and info["fallback_used"]
    assert calls[0][1]["data"]["queryStartDate"] == calls[0][1]["data"]["queryEndDate"] == "2026/10/22"
    assert all(c[1]["allow_redirects"] is False for c in calls)


@pytest.mark.parametrize("section", ["futures", "oi"])
def test_wrong_date_not_replaced_by_requested_form_value(section):
    assert history.parse_csv(sample(section), section, "2026-10-23") == []
    content = sample(section, "html") + b'<input name="queryDate" value="2026/10/23">'
    assert history.parse_html(content, section, "2026-10-23") == []


def test_malformed_csv_schema_is_error_not_unavailable(monkeypatch):
    monkeypatch.setattr(history.requests, "post", lambda *a, **k: response(b"wrong,headers\n1,2\n"))
    with pytest.raises(ValueError, match="必要欄位"):
        history.fetch_historical("oi", DATE, headers={})


def test_valid_header_only_csv_is_unavailable(monkeypatch):
    monkeypatch.setattr(history.requests, "post", lambda *a, **k: response(sample("futures").splitlines()[0] + b"\n"))
    rows, info = history.fetch_historical("futures", "2026-10-23", headers={})
    assert rows == [] and info["status"] == "unavailable_historical"
    assert info["csv_confirmed"] and not info["fallback_used"]


def test_backfill_uses_history_and_preserves_schema(monkeypatch):
    replay(monkeypatch)
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        return response(sample("futures" if url.endswith("futDataDown") else "oi"))
    monkeypatch.setattr(history.requests, "post", post)
    original = market.fetch_json
    def get(url, params=None):
        assert not url.endswith(("DailyMarketReportFut", "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"))
        return original(url, params)
    monkeypatch.setattr(market, "fetch_json", get)
    payload = market.build_market_context(DATE, backfill=True)
    assert payload["status"] == "ok" and len(calls) == 2
    assert payload["futures"]["tx_close"] == 46272 and payload["futures_oi"]["foreign_oi"] == -87297
    assert payload["source_status"]["taifex"]["source"] == "taifex_historical"
    assert payload["units"]["futures_oi"] == "contracts"


def test_current_day_never_calls_history(monkeypatch):
    replay(monkeypatch)
    monkeypatch.setattr(market, "fetch_historical", lambda *a, **k: pytest.fail("當日不得進歷史入口"))
    assert market.build_market_context(DATE)["status"] == "ok"


def test_cli_corrupt_csv_returns_failure_with_diagnostic(tmp_path, monkeypatch):
    replay(monkeypatch)
    monkeypatch.setattr(history.requests, "post", lambda *a, **k: response(b"\x81"))
    output = tmp_path / "context.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(date=DATE, backfill=True, twse_t86_input=None, output=str(output)))
    assert market.main() == 1
    payload = json.loads(output.read_text())
    assert payload["status"] == "error"
    assert any("big5" in x for x in payload["errors"]["taifex"])


def test_non_csv_missing_report_cli_is_unavailable_not_failure(tmp_path, monkeypatch):
    replay(monkeypatch)
    monkeypatch.setattr(history.requests, "post", lambda *a, **k: response(
        '<html>查無資料</html>'.encode(), {"Content-Type": "text/html;charset=UTF-8"},
    ))
    output = tmp_path / "context.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(date=DATE, backfill=True, twse_t86_input=None, output=str(output)))
    assert market.main() == 0
    payload = json.loads(output.read_text())
    assert payload["status"] == "unavailable_via_openapi" and not payload["errors"]
    assert payload["source_status"]["taifex"]["source"] == "taifex_historical"
    assert payload["futures"]["tx_close"] is None and payload["futures_oi"]["foreign_oi"] is None


def test_partial_history_preserves_available_component(monkeypatch):
    replay(monkeypatch)
    def post(url, **kwargs):
        if url.endswith("futDataDown"):
            return response(sample("futures"))
        return response(b"<html>no report</html>", {"Content-Type": "text/html;charset=UTF-8"})
    monkeypatch.setattr(history.requests, "post", post)
    payload = market.build_market_context(DATE, backfill=True)
    assert payload["status"] == "unavailable_via_openapi"
    assert payload["source_status"]["taifex"]["unavailable_components"] == ["oi"]
    assert payload["futures"]["tx_close"] == 46272 and payload["futures_oi"]["foreign_oi"] is None


def test_history_and_valid_pcr_both_missing_target_return_zero(tmp_path, monkeypatch):
    pcr = official("taifex-pcr")
    for row in pcr:
        row["Date"] = "20261027"
    replay(monkeypatch, {"taifex-pcr": pcr})
    monkeypatch.setattr(history.requests, "post", lambda *a, **k: response(
        b"<html>no report</html>", {"Content-Type": "text/html;charset=UTF-8"},
    ))
    output = tmp_path / "context.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(date=DATE, backfill=True, twse_t86_input=None, output=str(output)))
    assert market.main() == 0
    payload = json.loads(output.read_text())
    assert payload["status"] == "unavailable_via_openapi" and not payload["errors"]
    assert payload["source_status"]["taifex"]["unavailable_components"] == ["futures", "oi", "options"]
    assert payload["options"] == {"pcr": None, "put_oi": None, "call_oi": None}
    assert payload["unavailable_fields"]["options.pcr"]["reason"] == "unavailable_historical"


def test_newer_pcr_date_without_numeric_fields_is_still_error(monkeypatch):
    replay(monkeypatch, {"taifex-pcr": [{"Date": "20261027"}]})
    monkeypatch.setattr(history.requests, "post", lambda *a, **k: response(
        b"<html>no report</html>", {"Content-Type": "text/html;charset=UTF-8"},
    ))
    payload = market.build_market_context(DATE, backfill=True)
    assert payload["status"] == "error"
    assert any("PCR" in error for error in payload["errors"]["taifex"])
