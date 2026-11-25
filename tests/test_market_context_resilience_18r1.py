"""市場來源有界重試與 FinMind 步驟狀態的離線反例。"""

import json

import pytest
import requests

from app import market_context_fetcher as market
from tests.test_finmind_coverage_persist_19 import _coverage, _runner
from tests.test_market_context_fetcher import DATE, ENDPOINTS, official


class Response:
    def __init__(self, status=200, body="[]", data=None, error=None, content_type="application/json"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.text = body
        self.content = body.encode("utf-8")
        self.data = data
        self.error = error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self.error:
            raise self.error
        return self.data


def test_non_json_2xx_retries_then_succeeds(monkeypatch):
    responses = iter([Response(body="<html>暫時不可用</html>", error=ValueError("bad json"),
                               content_type="text/html"), Response(data=[{"Date": "20261022"}])])
    calls = []
    sleeps = []
    monkeypatch.setattr(market.requests, "get", lambda *a, **k: (calls.append(a), next(responses))[1])
    monkeypatch.setattr(market.time, "sleep", sleeps.append)
    assert market.fetch_json("https://openapi.taifex.com.tw/v1/PutCallRatio") == [{"Date": "20261022"}]
    assert len(calls) == 2 and sleeps == [1]


def test_connection_and_5xx_are_retryable(monkeypatch):
    responses = iter([requests.ConnectionError("offline"), Response(status=503, body="busy"), Response(data=[1])])
    calls = []

    def get(*a, **k):
        calls.append(a)
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    sleeps = []
    monkeypatch.setattr(market.requests, "get", get)
    monkeypatch.setattr(market.time, "sleep", sleeps.append)
    assert market.fetch_json("https://openapi.taifex.com.tw/v1/PutCallRatio") == [1]
    assert len(calls) == 3 and sleeps == [1, 2]


def test_4xx_does_not_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(market.requests, "get", lambda *a, **k: (calls.append(a), Response(status=429, body="quota"))[1])
    monkeypatch.setattr(market.time, "sleep", lambda _: pytest.fail("4xx 不應退避"))
    with pytest.raises(RuntimeError, match="http_status=429.*attempts=1"):
        market.fetch_json("https://openapi.taifex.com.tw/v1/PutCallRatio")
    assert len(calls) == 1


def test_exhausted_non_json_has_bounded_diagnostic(monkeypatch):
    body = "A" * 199 + "\n" + "SECRET_AFTER_PREFIX"
    calls = []
    sleeps = []
    monkeypatch.setattr(market.requests, "get", lambda *a, **k: (
        calls.append(a), Response(body=body, error=ValueError("bad json"), content_type="text/html")
    )[1])
    monkeypatch.setattr(market.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError) as caught:
        market.fetch_json("https://openapi.taifex.com.tw/v1/PutCallRatio")
    message = str(caught.value)
    assert "http_status=200" in message and "content_type='text/html'" in message
    assert "body_prefix=" in message and "attempts=3" in message
    assert "SECRET_AFTER_PREFIX" not in message and "\n" not in message
    assert len(calls) == 3 and sleeps == [1, 2]


def test_exhausted_current_day_remains_fail_closed(monkeypatch):
    def get(url, **kwargs):
        if url.endswith("PutCallRatio"):
            return Response(body="<html>稍後再試</html>", error=ValueError("bad json"),
                            content_type="text/html")
        return Response(data=official(ENDPOINTS[url.rsplit("/", 1)[-1]]))

    monkeypatch.setattr(market.requests, "get", get)
    monkeypatch.setattr(market.time, "sleep", lambda _: None)
    payload = market.build_market_context(DATE, backfill=False)
    assert payload["status"] == "error"
    assert payload["source_status"]["taifex"]["status"] == "error"
    warning = payload["source_status"]["taifex"]["warnings"][0]
    assert "http_status=200" in warning and "content_type='text/html'" in warning
    assert "body_prefix='<html>稍後再試</html>'" in warning and "attempts=3" in warning


@pytest.mark.parametrize("failed,expected", [(100, "PARTIAL"), (0, "OK")])
def test_finmind_step_status_matches_failure_count(tmp_path, failed, expected):
    runner = _runner(tmp_path)
    path = tmp_path / "finmind.json"
    path.write_text(json.dumps(_coverage(failed)))
    runner._record_finmind_stats(path)
    assert runner.status.steps[-1].status == expected
    assert runner.status.metadata["finmind"]["failed_fetch_count"] == failed
