"""行情連線重設的同日恢復反例。"""
import asyncio
import errno
from types import SimpleNamespace

import aiohttp

from app import data_fetcher
from app.data_fetcher import AsyncTPEXFetcher


class Response:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self):
        return {
            'date': '115/03/02',
            'tables': [{
                'title': '上櫃股票每日收盤行情', 'date': '115/03/02',
                'fields': ['代號', '名稱', '開盤', '最高', '最低', '收盤', '成交股數', '成交金額(元)'],
                'data': [['6488', '環球晶', '100', '101', '99', '100', '1000', '100000']],
            }],
        }


class Session:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0
        self.requests = []

    def get(self, _url, **kwargs):
        assert kwargs['timeout'] == (60 if 'tpex.org.tw' in _url else 30)
        self.calls += 1
        self.requests.append((_url, dict(kwargs['params']), kwargs['timeout']))
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def reset_error():
    key = SimpleNamespace(host='www.tpex.org.tw', port=443, ssl=True)
    return aiohttp.ClientConnectorError(key, ConnectionResetError(errno.ECONNRESET, 'Connection reset by peer'))


def test_tpex_connection_reset_recovers_same_day(monkeypatch):
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(data_fetcher.asyncio, 'sleep', sleep)
    session = Session([reset_error(), Response()])
    frame = asyncio.run(AsyncTPEXFetcher(session).fetch_daily_quotes('20260302'))
    assert frame is not None, '暫時連線重設必須沿用既有同日三次迴圈恢復'
    assert frame.iloc[0]['date'].strftime('%Y%m%d') == '20260302'
    assert session.calls == 2
    assert sleeps == [0.8]

import ssl
import pandas as pd
import pytest
import requests

from app.data_fetcher import AsyncTWSEFetcher, DataFetcherOrchestrator


def twse_payload(date='20260302'):
    return {'stat': 'OK', 'date': date, 'tables': [{
        'title': '每日收盤行情', 'date': date,
        'fields': ['證券代號', '證券名稱', '開盤價', '最高價', '最低價', '收盤價', '成交股數'],
        'data': [['2330', '台積電', '100', '101', '99', '100', '1000']],
    }]}


class PayloadResponse(Response):
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    async def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class SyncResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def close(self):
        self.closed = True

    def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


def no_sleep(monkeypatch):
    async def sleep(_seconds):
        pass
    monkeypatch.setattr(data_fetcher.asyncio, 'sleep', sleep)


@pytest.mark.parametrize('failure', [TimeoutError(), reset_error(), PayloadResponse(TimeoutError()), PayloadResponse(aiohttp.ClientPayloadError('truncated'))])
def test_twse_recovers_with_existing_same_day_fallback(monkeypatch, failure):
    calls = []
    def get(url, **kwargs):
        assert 'MI_INDEX' in url
        assert kwargs['params']['date'] == '20260302'
        assert kwargs['timeout'] == 30
        calls.append(url)
        return SyncResponse(twse_payload())
    monkeypatch.setattr(data_fetcher.requests, 'get', get)
    session = Session([failure])
    fetcher = AsyncTWSEFetcher(session)
    frame = asyncio.run(fetcher.fetch_daily_quotes('20260302'))
    assert frame is not None and frame.iloc[0]['stock_id'] == '2330'
    assert session.calls == 1 and len(calls) == 1
    assert fetcher.failure_reason is None
    assert fetcher.data_source_log[0]['method'] == 'requests_fallback'


@pytest.mark.parametrize('terminal', [PayloadResponse(None, 403), PayloadResponse(ValueError('non-json'))])
def test_twse_prior_307_does_not_override_terminal_response(monkeypatch, terminal):
    no_sleep(monkeypatch)
    def forbidden(*_args, **_kwargs):
        pytest.fail('終端拒收不得因舊307進備援')
    monkeypatch.setattr(data_fetcher.requests, 'get', forbidden)
    session = Session([PayloadResponse(None, 307), terminal, terminal, terminal])
    fetcher = AsyncTWSEFetcher(session)
    assert asyncio.run(fetcher.fetch_daily_quotes('20260302')) is None
    assert fetcher.failure_reason is not None
    assert fetcher.data_source_log == []


@pytest.mark.parametrize('fetcher_type', [AsyncTWSEFetcher, AsyncTPEXFetcher])
@pytest.mark.parametrize('failure', [ssl.SSLError('certificate'), aiohttp.ServerFingerprintMismatch(b'a', b'b', 'host', 443), asyncio.CancelledError()])
def test_certificate_and_cancel_never_retry_or_fallback(monkeypatch, fetcher_type, failure):
    def forbidden(*_args, **_kwargs):
        pytest.fail('憑證／取消不可改走備援')
    monkeypatch.setattr(data_fetcher.requests, 'get', forbidden)
    session = Session([failure])
    fetcher = fetcher_type(session)
    if isinstance(failure, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(fetcher.fetch_daily_quotes('20260302'))
    else:
        assert asyncio.run(fetcher.fetch_daily_quotes('20260302')) is None
        assert fetcher.failure_reason is not None
    assert session.calls == 1
    assert fetcher.data_source_log == []


def test_tpex_body_timeouts_use_third_slot_same_parser(monkeypatch):
    no_sleep(monkeypatch)
    calls = []
    def get(url, **kwargs):
        assert 'stk_wn1430_result.php' in url
        assert kwargs['params']['d'] == '115/03/02'
        assert kwargs['timeout'] == 60
        calls.append(url)
        return SyncResponse(asyncio.run(Response().json()))
    monkeypatch.setattr(data_fetcher.requests, 'get', get)
    session = Session([PayloadResponse(TimeoutError()), PayloadResponse(aiohttp.ClientPayloadError('truncated'))])
    fetcher = AsyncTPEXFetcher(session)
    frame = asyncio.run(fetcher.fetch_daily_quotes('20260302'))
    assert frame is not None and frame.iloc[0]['stock_id'] == '6488'
    assert session.calls == 2 and len(calls) == 1
    assert fetcher.failure_reason is None
    assert fetcher.data_source_log[0]['method'] == 'requests_fallback'


@pytest.mark.parametrize('via_fallback', [False, True])
def test_tpex_public_fetch_uses_ew_for_async_and_third_slot(monkeypatch, via_fallback):
    no_sleep(monkeypatch)
    sync_calls = []

    def get(url, **kwargs):
        sync_calls.append((url, dict(kwargs['params']), kwargs['timeout']))
        return SyncResponse(asyncio.run(Response().json()))

    monkeypatch.setattr(data_fetcher.requests, 'get', get)
    outcomes = [TimeoutError(), TimeoutError()] if via_fallback else [Response()]
    session = Session(outcomes)
    fetcher = AsyncTPEXFetcher(session)
    frame = asyncio.run(fetcher.fetch_daily_quotes('20260302'))
    assert frame is not None and frame.iloc[0]['stock_id'] == '6488'
    assert frame.iloc[0]['date'].strftime('%Y%m%d') == '20260302'
    expected = (
        'https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php',
        {'l': 'zh-tw', 'd': '115/03/02', 'se': 'EW'},
        60,
    )
    assert session.requests == [expected] * (2 if via_fallback else 1)
    assert sync_calls == ([expected] if via_fallback else [])
    assert session.calls + len(sync_calls) == (3 if via_fallback else 1)
    assert fetcher.failure_reason is None
    assert fetcher.data_source_log[0]['method'] == ('requests_fallback' if via_fallback else 'aiohttp')


@pytest.mark.parametrize('market', ['TWSE', 'TPEX'])
def test_fallback_wrong_date_rejected(monkeypatch, market):
    no_sleep(monkeypatch)
    if market == 'TWSE':
        payload = twse_payload('20260303')
        fetcher = AsyncTWSEFetcher(Session([TimeoutError()]))
    else:
        payload = asyncio.run(Response().json())
        payload['date'] = '20260303'
        fetcher = AsyncTPEXFetcher(Session([TimeoutError(), TimeoutError()]))
    monkeypatch.setattr(data_fetcher.requests, 'get', lambda *_a, **_k: SyncResponse(payload))
    assert asyncio.run(fetcher.fetch_daily_quotes('20260302')) is None
    assert 'DateMismatch' in fetcher.failure_reason
    assert fetcher.data_source_log == []


@pytest.mark.parametrize('failed_market', ['TWSE', 'TPEX'])
def test_one_market_transport_failure_cannot_become_partial_batch(monkeypatch, tmp_path, failed_market):
    no_sleep(monkeypatch)
    async def twse(self, _date):
        if failed_market == 'TWSE':
            self.failure_reason = 'category=transport exception_type=TimeoutError'
            return None
        return pd.DataFrame([{'stock_id': '2330', 'close': 100}])
    async def tpex(self, _date):
        if failed_market == 'TPEX':
            self.failure_reason = 'category=transport exception_type=TimeoutError'
            return None
        return pd.DataFrame([{'stock_id': '6488', 'close': 100}])
    monkeypatch.setattr(AsyncTWSEFetcher, 'fetch_daily_quotes', twse)
    monkeypatch.setattr(AsyncTPEXFetcher, 'fetch_daily_quotes', tpex)
    orchestrator = DataFetcherOrchestrator(str(tmp_path))
    assert orchestrator.fetch_historical_data('2026-03-02', '2026-03-02').empty


def test_tpex_three_slots_exhausted_never_starts_fourth(monkeypatch):
    no_sleep(monkeypatch)
    calls = []
    def get(*_args, **kwargs):
        calls.append(kwargs)
        raise requests.Timeout('read timeout')
    monkeypatch.setattr(data_fetcher.requests, 'get', get)
    session = Session([reset_error(), TimeoutError()])
    fetcher = AsyncTPEXFetcher(session)
    assert asyncio.run(fetcher.fetch_daily_quotes('20260302')) is None
    assert session.calls == 2 and len(calls) == 1
    assert 'category=transport' in fetcher.failure_reason
    assert fetcher.data_source_log == []

@pytest.mark.parametrize('via_fallback', [False, True])
def test_twse_invalid_payload_shape_is_failure(monkeypatch, via_fallback):
    session = Session([TimeoutError()] if via_fallback else [PayloadResponse([])])
    monkeypatch.setattr(data_fetcher.requests, 'get', lambda *_a, **_k: SyncResponse([]))
    fetcher = AsyncTWSEFetcher(session)
    assert asyncio.run(fetcher.fetch_daily_quotes('20260302')) is None
    assert 'InvalidPayload' in fetcher.failure_reason
    assert fetcher.data_source_log == []


@pytest.mark.parametrize('external_cancel', [False, True])
def test_all_date_tasks_are_finished_before_return(monkeypatch, tmp_path, external_cancel):
    started = asyncio.Event()
    cleaned = []
    async def day(self, _session, date):
        if date.day == 2:
            await started.wait()
            if external_cancel:
                await asyncio.Event().wait()
            raise RuntimeError('injected date failure')
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.append('cancelled pending date')
    monkeypatch.setattr(DataFetcherOrchestrator, '_fetch_day_data', day)
    async def run():
        orchestrator = DataFetcherOrchestrator(str(tmp_path))
        task = asyncio.create_task(orchestrator._run_async_fetch('2026-03-02', '2026-03-03'))
        if external_cancel:
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(RuntimeError, match='injected date failure'):
                await task
        assert cleaned == ['cancelled pending date']
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    asyncio.run(run())


@pytest.mark.parametrize('fetcher_type', [AsyncTWSEFetcher, AsyncTPEXFetcher])
def test_cancel_waits_for_sync_transport_close(monkeypatch, fetcher_type):
    import threading
    entered, release = threading.Event(), threading.Event()
    response = SyncResponse(twse_payload() if fetcher_type is AsyncTWSEFetcher else asyncio.run(Response().json()))
    def get(*_args, **_kwargs):
        entered.set()
        assert release.wait(2), '測試必須在限時內放行worker'
        return response
    monkeypatch.setattr(data_fetcher.requests, 'get', get)
    no_sleep(monkeypatch)
    outcomes = [TimeoutError()] if fetcher_type is AsyncTWSEFetcher else [TimeoutError(), TimeoutError()]
    async def run():
        task = asyncio.create_task(fetcher_type(Session(outcomes)).fetch_daily_quotes('20260302'))
        assert await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        await asyncio.to_thread(lambda: None)
        assert not task.done(), '取消不得留worker在背景取數'
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert response.closed
    try:
        asyncio.run(run())
    finally:
        release.set()
