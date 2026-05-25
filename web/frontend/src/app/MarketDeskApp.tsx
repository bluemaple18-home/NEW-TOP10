import { useEffect, useState, useTransition } from 'react'
import { fetchStockDetail, fetchWeeklyCandidates } from '../api'
import { MarketSnapshotPanel } from '../features/market'
import { GlobalSettingsPanel } from '../features/settings'
import { StockDetailPanel } from '../features/stock-detail'
import { defaultInvestmentSettings, WeeklyCandidatesPanel, type GlobalInvestmentSettings } from '../features/weekly-candidates'
import type { RankingItem, StockDetailResponse, WeeklyCandidatesResponse } from '../types'
import { AppShell } from './AppShell'

type DeskView = 'weekly' | 'stock'

export function MarketDeskApp() {
  const [rankings, setRankings] = useState<RankingItem[]>([])
  const [weeklyDecision, setWeeklyDecision] = useState<WeeklyCandidatesResponse | null>(null)
  const [settings, setSettings] = useState<GlobalInvestmentSettings>(defaultInvestmentSettings)
  const [activeView, setActiveView] = useState<DeskView>('weekly')
  const [stockRailCollapsed, setStockRailCollapsed] = useState(false)
  const [selectedStockId, setSelectedStockId] = useState<string>('')
  const [stockDetail, setStockDetail] = useState<StockDetailResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  useEffect(() => {
    let cancelled = false

    fetchWeeklyCandidates(settings, 10)
      .then((response) => {
        if (cancelled) return
        const candidates = response.stock_candidates
        setWeeklyDecision(response)
        setRankings(candidates.map((candidate) => candidate.ranking))
        setSelectedStockId((current) => (candidates.some((candidate) => candidate.stock_id === current) ? current : candidates[0]?.stock_id ?? ''))
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : '載入排行失敗')
      })

    return () => {
      cancelled = true
    }
  }, [settings])

  useEffect(() => {
    if (!selectedStockId) return
    let cancelled = false

    startTransition(() => {
      setError(null)
      setStockDetail(null)
    })

    fetchStockDetail(selectedStockId)
      .then((response) => {
        if (cancelled) return
        startTransition(() => {
          setStockDetail(response)
        })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : '載入個股資料失敗')
      })

    return () => {
      cancelled = true
    }
  }, [selectedStockId])

  const selectedRanking = rankings.find((item) => item.stock_id === selectedStockId)
  const candidates = weeklyDecision?.stock_candidates ?? []
  const statusOrder = weeklyDecision?.status_order ?? []

  const openStockPage = (stockId: string) => {
    setSelectedStockId(stockId)
    setActiveView('stock')
  }

  return (
    <AppShell
      eyebrow="Momentum Desk"
      metric={
        <>
          <span>本週模型初選池</span>
          <strong>{weeklyDecision?.version_label ?? '本機資料'}</strong>
        </>
      }
      subtitle="做多派、動能順勢；本週候補是一頁，個股 K 線與操作計畫是另一頁。"
      title="動能工作台"
    >
      <nav className="desk-tabs" aria-label="工作台頁面">
        <button
          aria-pressed={activeView === 'weekly'}
          className={activeView === 'weekly' ? 'desk-tab desk-tab--active' : 'desk-tab'}
          onClick={() => setActiveView('weekly')}
          type="button"
        >
          本週候補
        </button>
        <button
          aria-pressed={activeView === 'stock'}
          className={activeView === 'stock' ? 'desk-tab desk-tab--active' : 'desk-tab'}
          disabled={!selectedStockId}
          onClick={() => setActiveView('stock')}
          type="button"
        >
          個股頁
        </button>
      </nav>

      {activeView === 'weekly' ? (
        <section className="weekly-page">
          <div className="weekly-page__settings">
            <GlobalSettingsPanel settings={settings} onChange={setSettings} />
          </div>
          <div className="weekly-page__decision">
            <MarketSnapshotPanel
              candidateLayer={weeklyDecision?.candidate_layer}
              modelPoolCount={weeklyDecision?.model_pool_count ?? rankings.length}
              summary={weeklyDecision?.market_summary}
              versionLabel={weeklyDecision?.version_label ?? '載入中'}
            />
            <WeeklyCandidatesPanel
              candidates={candidates}
              candidateLayer={weeklyDecision?.candidate_layer}
              isPending={isPending}
              onSelectStock={openStockPage}
              selectedStockId={selectedStockId}
              statusOrder={statusOrder}
            />
          </div>
        </section>
      ) : (
        <section className="stock-page">
          <div className={stockRailCollapsed ? 'workspace-grid workspace-grid--rail-collapsed' : 'workspace-grid'}>
            <aside className="left-rail" aria-label="個股頁左側工具欄">
              <div className="rail-titlebar">
                <div>
                  <p className="rail-kicker">Stock Rail</p>
                  <strong>候補與設定</strong>
                </div>
                <button
                  aria-expanded={!stockRailCollapsed}
                  className="rail-toggle"
                  onClick={() => setStockRailCollapsed((current) => !current)}
                  type="button"
                >
                  {stockRailCollapsed ? '展開' : '收合'}
                </button>
              </div>
              {stockRailCollapsed ? (
                <button
                  className="rail-collapsed-card"
                  onClick={() => setStockRailCollapsed(false)}
                  type="button"
                >
                  <span>候補</span>
                  <strong>{candidates.length}</strong>
                  <small>{selectedStockId}</small>
                </button>
              ) : (
                <>
                  <GlobalSettingsPanel settings={settings} onChange={setSettings} />
                  <WeeklyCandidatesPanel
                    candidates={candidates}
                    candidateLayer={weeklyDecision?.candidate_layer}
                    isPending={isPending}
                    onSelectStock={setSelectedStockId}
                    selectedStockId={selectedStockId}
                    statusOrder={statusOrder}
                  />
                </>
              )}
            </aside>
            <div className="stock-page__main">
              <button className="back-to-weekly" onClick={() => setActiveView('weekly')} type="button">
                回本週候補
              </button>
              <StockDetailPanel
                error={error}
                selectedRanking={selectedRanking}
                selectedStockId={selectedStockId}
                stockDetail={stockDetail}
              />
            </div>
          </div>
        </section>
      )}
    </AppShell>
  )
}
