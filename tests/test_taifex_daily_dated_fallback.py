"""每日API整份落後時沿用指定日來源，拒收錯日及非有限數值。"""
import copy
import pytest
from app import market_context_fetcher as market
from tests.test_market_context_fetcher import DATE, official, replay


def setup_lag(monkeypatch):
    overrides={}
    for name in ('taifex-futures','taifex-oi','taifex-pcr'):
        rows=copy.deepcopy(official(name))
        for row in rows:
            if market.check_date(row['Date'])==DATE: row['Date']='20261021'
        overrides[name]=rows
    replay(monkeypatch,overrides)
    calls=[]
    def dated(section,trade_date,**kwargs):
        calls.append((section,trade_date))
        return copy.deepcopy(official('taifex-'+section)),{'status':'ok','data_date':trade_date,'fallback_used':False}
    monkeypatch.setattr(market,'fetch_historical',dated)
    monkeypatch.setattr(market,'fetch_dated_pcr_official',lambda date:(copy.deepcopy(official('taifex-pcr')),'html'))
    return calls


def test_all_three_lag_reuses_existing_exact_day_sources(monkeypatch):
    calls=setup_lag(monkeypatch)
    payload=market.build_market_context(DATE)
    assert payload['status']=='ok',payload['errors']
    assert calls==[('futures',DATE),('oi',DATE)]
    source=payload['source_status']['taifex']
    assert source['source']=='taifex_openapi_with_dated_fallback'
    assert source['dated_fallback']['futures']['api_data_date']=='2026-10-21'
    assert source['pcr_fallback_used'] is True
    assert payload['options']['pcr']==66.18


@pytest.mark.parametrize('defect',['wrong_date','nan','infinity','duplicate','unavailable','raise'])
def test_dated_futures_failure_is_still_fatal(monkeypatch,defect):
    setup_lag(monkeypatch)
    def dated(section,date,**kwargs):
        rows=copy.deepcopy(official('taifex-'+section))
        info={'status':'ok','data_date':date,'fallback_used':False}
        if section=='futures':
            selected=[r for r in rows if market.check_date(r['Date'])==DATE and r.get('Contract')=='TX' and r.get('TradingSession')=='一般' and r.get('ContractMonth(Week)')=='202611']
            assert selected
            if defect=='wrong_date':
                for row in rows:row['Date']='20261021'
            elif defect=='nan':selected[0]['Last']='NaN'
            elif defect=='infinity':selected[0]['Last']='Infinity'
            elif defect=='duplicate':rows.append(copy.deepcopy(selected[0]))
            elif defect=='unavailable':rows=[];info['status']='unavailable_historical'
            else:raise RuntimeError('bounded source failure')
        return rows,info
    monkeypatch.setattr(market,'fetch_historical',dated)
    p=market.build_market_context(DATE)
    assert p['status']=='error' and p['errors']['taifex']
    assert p['futures']['tx_close'] is None


@pytest.mark.parametrize('defect',['empty','bad_date','target_nan'])
def test_bad_current_api_never_hides_behind_dated_source(monkeypatch,defect):
    rows=copy.deepcopy(official('taifex-futures'))
    if defect=='empty':rows=[]
    elif defect=='bad_date':rows[0]['Date']='not-a-date'
    else:
        for row in rows:
            if row.get('Contract')=='TX' and row.get('TradingSession')=='一般':row['Last']='NaN'
    replay(monkeypatch,{'taifex-futures':rows})
    monkeypatch.setattr(market,'fetch_historical',lambda *a,**k:pytest.fail('損壞或同日錯值不應走指定日來源'))
    p=market.build_market_context(DATE)
    assert p['status']=='error' and p['errors']['taifex']
