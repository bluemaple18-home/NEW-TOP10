import { useEffect, useMemo, useState } from 'react'
import { fetchMarketFlowRadar } from '../../api'
import type { MarketFlowRadarResponse } from '../../types'

type RadarState = 'live' | 'loading' | 'empty' | 'error' | 'stale' | 'partial'

const formatValue = (value: number) => `${value < 0 ? '−' : ''}${Math.abs(value / 100000000).toFixed(1)} 億`

export function MarketFlowRadar() {
  const [data, setData] = useState<MarketFlowRadarResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [state, setState] = useState<RadarState>('live')

  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    fetchMarketFlowRadar()
      .then((response) => { if (!cancelled) setData(response) })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : '雷達資料載入失敗') })
    return () => { cancelled = true }
  }, [])

  const visibleItems = useMemo(() => {
    if (!data || state === 'empty') return []
    if (state === 'partial') return data.items.slice(0, 1)
    return data.items
  }, [data, state])
  const effectiveFreshness = state === 'stale' ? 'STALE' : data?.freshness

  return (
    <section className="market-flow-radar" aria-labelledby="market-flow-title">
      <div className="radar-toolbar">
        <div>
          <p className="panel__eyebrow">Read-only research view</p>
          <h2 id="market-flow-title" className="panel__title">Theme 資金雷達</h2>
        </div>
        <label className="radar-state-control">
          <span>狀態預覽</span>
          <select aria-label="雷達狀態預覽" value={state} onChange={(event) => setState(event.target.value as RadarState)}>
            <option value="live">目前 fixture</option>
            <option value="loading">載入中</option>
            <option value="empty">空資料</option>
            <option value="error">錯誤</option>
            <option value="stale">過期資料</option>
            <option value="partial">部分 coverage</option>
          </select>
        </label>
      </div>

      {state === 'loading' ? <div className="radar-state" role="status">正在讀取核准 fixture…</div> : null}
      {state === 'error' ? <div className="radar-state radar-state--error" role="alert">無法載入雷達資料。請保留現有 Top10 工作台，稍後再試。</div> : null}
      {state === 'empty' ? <div className="radar-state" role="status">目前沒有可展示的 Theme observation。</div> : null}
      {state !== 'loading' && state !== 'error' && state !== 'empty' && data ? (
        <>
          <div className="radar-status-strip" aria-label="雷達資料狀態">
            <span><b>資料日</b>{data.as_of_date}</span>
            <span className={effectiveFreshness === 'STALE' ? 'status-text status-text--warn' : 'status-text'}><b>freshness</b>{effectiveFreshness === 'STALE' ? 'STALE' : 'FRESH'}</span>
            <span><b>coverage</b>{Math.round((state === 'partial' ? data.coverage / 2 : data.coverage) * 100)}%</span>
            <span><b>來源</b>{data.source.source_type}</span>
          </div>
          {state === 'stale' ? <div className="radar-notice">資料已超過 freshness 門檻；僅供研究核對，不作即時判斷。</div> : null}
          {state === 'partial' ? <div className="radar-notice">部分 coverage：缺漏資料不以 0 填補。</div> : null}
          <div className="radar-table-wrap">
            <table className="radar-table">
              <caption className="sr-only">Theme 資金流排行</caption>
              <thead><tr><th scope="col">#</th><th scope="col">Theme</th><th scope="col">買進</th><th scope="col">賣出</th><th scope="col">Net</th><th scope="col">coverage</th><th scope="col">狀態</th></tr></thead>
              <tbody>{visibleItems.map((item) => (
                <tr key={item.theme_id}>
                  <td>{item.rank}</td><th scope="row">{item.theme_name}<small>{item.security_count} securities</small></th>
                  <td className="flow-positive">{formatValue(item.institutional_buy_value)}</td>
                  <td className="flow-negative">{formatValue(item.institutional_sell_value)}</td>
                  <td className={item.institutional_net_value >= 0 ? 'flow-positive flow-net' : 'flow-negative flow-net'}>{formatValue(item.institutional_net_value)}</td>
                  <td>{Math.round(item.coverage * 100)}%<small>{item.missing_count ? `${item.missing_count} missing` : 'complete'}</small></td>
                  <td><span className={`radar-badge radar-badge--${item.status.toLowerCase()}`}>{effectiveFreshness === 'STALE' ? 'STALE' : item.status}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="radar-footnote">證據：{data.evidence.join(' · ')} · allocation：{data.allocation_policy}</div>
          <div className="radar-boundary"><b>研究關聯層</b><span>{data.research_boundary.message}</span><em>Graph: {data.research_boundary.graph_drilldown}</em></div>
          <div className="radar-boundary radar-boundary--separated"><b>Top10 recommendation</b><span>維持既有模型候補與決策層；本頁不提供買進建議，也不改寫排名。</span><em>impact: {data.research_boundary.ranking_impact}</em></div>
        </>
      ) : null}
      {error && state === 'live' ? <p className="radar-inline-error">{error}</p> : null}
    </section>
  )
}
