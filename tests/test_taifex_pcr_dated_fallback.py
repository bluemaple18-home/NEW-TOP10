"""OpenAPI落後而官網已公布的PCR來源契約；全部使用記憶體回應。"""
import copy
from html import escape
import pytest
from app import market_context_fetcher as market
from tests.test_market_context_fetcher import DATE, official, replay
from tests.test_taifex_pcr_source_contract_22 import response

HEADERS=('日期','賣權成交量','買權成交量','買賣權成交量比率%','賣權未平倉量','買權未平倉量','買賣權未平倉量比率%')
def html_body(rows):
 return ('<table><tr>'+''.join('<th>'+h+'</th>' for h in HEADERS)+'</tr>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table>').encode()
def target_row():return [DATE.replace('-','/'),'172,113','199,654','86.21','64,809','97,930','66.18']
def setup(monkeypatch, rows):
 stale=[copy.deepcopy(r) for r in official('taifex-pcr') if market.check_date(r['Date'])!=DATE]
 replay(monkeypatch,{'taifex-pcr':stale});calls=[]
 def post(url,**kwargs):
  calls.append((url,kwargs));return response(html_body(rows),content_type='text/html;charset=UTF-8')
 monkeypatch.setattr(market.requests,'post',post)
 return calls

def test_api_lag_uses_exact_official_day_and_records_source(monkeypatch):
 calls=setup(monkeypatch,[target_row()]);payload=market.build_market_context(DATE)
 assert payload['status']=='ok',payload['errors']
 assert payload['options']=={'pcr':66.18,'put_oi':64809,'call_oi':97930}
 source=payload['source_status']['taifex'];assert source['pcr_format']=='html'
 assert source['pcr_source']=='taifex_pcRatioExcel' and source['pcr_fallback_used'] is True and source['fallback_used'] is True
 assert len(calls)==1 and calls[0][0]=='https://www.taifex.com.tw/cht/3/pcRatioExcel'
 assert calls[0][1]['data']=={'queryStartDate':DATE.replace('-','/'),'queryEndDate':DATE.replace('-','/')}
 assert calls[0][1]['allow_redirects'] is False

@pytest.mark.parametrize('defect',['wrong_date','duplicate','nan','infinity','negative_oi','wrong_columns'])
def test_dated_official_fallback_never_weakens_contract(monkeypatch,defect):
 row=target_row();rows=[row]
 if defect=='wrong_date':row[0]='2026/10/21'
 elif defect=='duplicate':rows.append(list(row))
 elif defect=='nan':row[-1]='NaN'
 elif defect=='infinity':row[-1]='Infinity'
 elif defect=='negative_oi':row[4]='-1'
 else:row.pop()
 calls=setup(monkeypatch,rows);payload=market.build_market_context(DATE)
 assert payload['status']=='error' and payload['errors']['taifex']
 assert payload['options']['pcr'] is None
 assert len(calls)==1

def test_current_api_day_never_fetches_fallback(monkeypatch):
 replay(monkeypatch)
 monkeypatch.setattr(market.requests,'post',lambda *a,**k:pytest.fail('同日API正常不可取備援'))
 assert market.build_market_context(DATE)['status']=='ok'


def test_official_unpadded_calendar_date_keeps_exact_target(monkeypatch):
 row=['2026/11/2','148,092','157,966','93.75','69,770','113,305','61.58']
 monkeypatch.setattr(market.requests,'post',lambda *a,**k:response(html_body([row]),content_type='text/html;charset=UTF-8'))
 rows,fmt=market.fetch_dated_pcr_official('2026-11-02')
 assert fmt=='html' and rows==[{'Date':'2026-11-02','PutOI':'69,770','CallOI':'113,305','PutCallOIRatio%':'61.58'}]
