"""PCR JSON／CSV 自適應、比率語意與確定性失敗的離線反例。"""

import csv
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from app import market_context_fetcher as market
from scripts.run_automation import AutomationRunner, RuntimePaths
from tests.test_market_context_fetcher import DATE, official, replay


FIXTURE = Path(__file__).parent / "fixtures/taifex_pcr_22/official-response.json"


def csv_body():
    fixture = json.loads(FIXTURE.read_text())
    body = fixture["body"].encode("utf-8")
    assert hashlib.sha256(body).hexdigest() == fixture["sha256"]
    return body


def response(body, status=200, content_type="application/octet-stream"):
    result = requests.Response()
    result._content = body
    result.status_code = status
    result.headers["Content-Type"] = content_type
    result.encoding = "utf-8"
    return result


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("卡 22 測試禁止實際網路")
    monkeypatch.setattr(requests.sessions.Session, "request", deny)


@pytest.mark.parametrize("content_type", ["application/octet-stream", "application/json", "text/html"])
def test_real_csv_uses_oi_ratio_and_never_retries(monkeypatch, content_type):
    calls = []
    monkeypatch.setattr(market.requests, "get", lambda *a, **k: (calls.append(a), response(csv_body(), content_type=content_type))[1])
    monkeypatch.setattr(market.time, "sleep", lambda _: pytest.fail("成功 CSV 不可重試"))
    rows, fmt = market.fetch_pcr()
    row = next(row for row in rows if row["Date"] == "2026-10-28")
    assert row == {"Date": "2026-10-28", "PutOI": "47770", "CallOI": "68849", "PutCallOIRatio%": "69.38"}
    original = next(csv.DictReader(io.StringIO(csv_body().decode("utf-8-sig"))))
    assert original["買賣權成交量比率%"] == "92.29"
    _, _, options, errors = market.parse_taifex_payloads([], rows, [], "2026-10-28", unavailable_sections=frozenset({"futures", "oi"}))
    assert options == {"pcr": 69.38, "put_oi": 47770, "call_oi": 68849} and not errors
    assert fmt == "csv" and len(calls) == 1


@pytest.mark.parametrize("wrapped", [False, True])
def test_json_fixture_with_bom_and_whitespace_still_works(monkeypatch, wrapped):
    data = official("taifex-pcr")
    body = b"\xef\xbb\xbf \n\t" + json.dumps({"data": data} if wrapped else data).encode()
    calls = []
    monkeypatch.setattr(market.requests, "get", lambda *a, **k: (calls.append(a), response(body, content_type="text/csv"))[1])
    rows, fmt = market.fetch_pcr()
    _, _, options, errors = market.parse_taifex_payloads(official("taifex-futures"), rows, official("taifex-oi"), DATE)
    assert options == {"pcr": 66.18, "put_oi": 64809, "call_oi": 97930} and not errors
    assert fmt == "json" and len(calls) == 1
    assert next(r for r in rows if r["Date"] == DATE)["PutCallOIRatio%"] == "66.18"


@pytest.mark.parametrize("first", [requests.ConnectionError("offline"), requests.Timeout("slow"), 503])
def test_transient_failure_retries_then_csv_succeeds(monkeypatch, first):
    calls, sleeps = [], []
    def get(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            if isinstance(first, Exception):
                raise first
            return response(b"busy", status=first)
        return response(csv_body())
    monkeypatch.setattr(market.requests, "get", get)
    monkeypatch.setattr(market.time, "sleep", sleeps.append)
    assert market.fetch_pcr()[1] == "csv"
    assert len(calls) == 2 and sleeps == [1]


def test_4xx_is_not_retried(monkeypatch):
    calls = []
    monkeypatch.setattr(market.requests, "get", lambda *a, **k: (calls.append(a), response(b"quota", status=429))[1])
    monkeypatch.setattr(market.time, "sleep", lambda _: pytest.fail("4xx 不重試"))
    with pytest.raises(RuntimeError, match="HTTP_429.*attempts=1"):
        market.fetch_pcr()
    assert len(calls) == 1


def install_pcr(monkeypatch, body):
    replay(monkeypatch)
    original = market.requests.get
    calls = []
    def get(url, **kwargs):
        if url.endswith("PutCallRatio"):
            calls.append(url)
            return response(body)
        return original(url, **kwargs)
    monkeypatch.setattr(market.requests, "get", get)
    return calls


@pytest.mark.parametrize("body", [b"<html>busy</html>", b"nonsense", b"[broken json", b"\xff"])
def test_neither_format_fails_cli_after_bounded_retries(tmp_path, monkeypatch, body):
    calls = install_pcr(monkeypatch, body)
    sleeps = []
    monkeypatch.setattr(market.time, "sleep", sleeps.append)
    output = tmp_path / "artifacts" / f"market_context_{DATE}.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(date=DATE, backfill=False, output=str(output), twse_t86_input=None))
    assert market.main() == 1
    payload = json.loads(output.read_text())
    assert payload["status"] == "error" and payload["source_status"]["taifex"]["status"] == "error"
    assert any(e.startswith("TAIFEX PCR：") for e in payload["errors"]["taifex"])
    assert any("attempts=3" in e for e in payload["errors"]["taifex"])
    assert len(calls) == 3 and sleeps == [1, 2]
    # 不啟動 Daily；讓既有 artifact 閘門實際讀取上述失敗產物。
    runner = object.__new__(AutomationRunner)
    runner.runtime_paths = RuntimePaths(tmp_path, tmp_path, tmp_path)
    runner.run_date, runner.backfill, runner.dry_run = DATE, False, False
    runner.status = SimpleNamespace(metadata={}, steps=[])
    runner._run_command = lambda name, command: None
    runner._now = lambda: "2026-10-29T00:00:00Z"
    with pytest.raises(RuntimeError, match="market context status invalid: error"):
        runner._run_market_context({"market_context_enabled": True})
    assert runner.status.steps[-1].status == "FAILED"


@pytest.mark.parametrize("fmt", ["csv", "json"])
@pytest.mark.parametrize("defect", ["missing", "nonnumeric", "negative", "fractional", "date", "wrong_date"])
def test_contract_error_never_retries_or_uses_other_date(monkeypatch, fmt, defect):
    row = {"Date": "20261022", "PutOI": "64809", "CallOI": "97930", "PutCallOIRatio%": "66.18"}
    if defect == "missing":
        del row["PutCallOIRatio%"]
    elif defect == "nonnumeric":
        row["PutCallOIRatio%"] = "NaN"
    elif defect == "negative":
        row["PutOI"] = "-1"
    elif defect == "fractional":
        row["CallOI"] = "1.2"
    elif defect == "date":
        row["Date"] = "20261399"
    else:
        row["Date"] = "20261028"
    if fmt == "csv":
        mapping = {"Date": "日期", "PutOI": "賣權未平倉量", "CallOI": "買權未平倉量", "PutCallOIRatio%": "買賣權未平倉量比率%"}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[mapping[k] for k in row])
        writer.writeheader(); writer.writerow({mapping[k]: v for k, v in row.items()})
        body = output.getvalue().encode()
    else:
        body = json.dumps([row]).encode()
    calls = install_pcr(monkeypatch, body)
    monkeypatch.setattr(market.time, "sleep", lambda _: pytest.fail("契約錯誤不可重試"))
    payload = market.build_market_context(DATE)
    assert payload["status"] == "error"
    assert any(e.startswith("TAIFEX PCR：") for e in payload["errors"]["taifex"])
    assert len(calls) == 1


@pytest.mark.parametrize("fmt", ["csv", "json"])
def test_format_is_written_in_artifact(tmp_path, monkeypatch, fmt):
    calls = install_pcr(monkeypatch, csv_body() if fmt == "csv" else json.dumps(official("taifex-pcr")).encode())
    output = tmp_path / "market.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(date=DATE, backfill=False, output=str(output), twse_t86_input=None))
    assert market.main() == 0
    payload = json.loads(output.read_text())
    assert payload["status"] == "ok" and payload["source_status"]["taifex"]["pcr_format"] == fmt
    assert payload["options"] == {"pcr": 66.18, "put_oi": 64809, "call_oi": 97930}
    assert len(calls) == 1
