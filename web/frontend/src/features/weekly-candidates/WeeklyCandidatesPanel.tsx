import { Panel } from '../../components'
import { formatPct } from '../../lib/formatters'
import type { CandidateStatus, RankingItem, WeeklyCandidate, WeeklyCandidateLayer } from '../../types'

type WeeklyCandidatesPanelProps = {
  candidates: WeeklyCandidate[]
  candidateLayer?: WeeklyCandidateLayer | null
  isPending?: boolean
  selectedStockId: string
  statusOrder: CandidateStatus[]
  onSelectStock: (stockId: string) => void
}

export function WeeklyCandidatesPanel({
  candidates,
  candidateLayer,
  isPending = false,
  onSelectStock,
  selectedStockId,
  statusOrder,
}: WeeklyCandidatesPanelProps) {
  const grouped = statusOrder
    .map((status) => [status, candidates.filter((candidate) => candidate.status === status)] as const)
    .filter(([, groupItems]) => groupItems.length > 0)
  const hiddenBySettings = candidateLayer?.hidden_by_settings_count ?? 0
  const settingEffectNotes = candidateLayer?.settings_effects?.map((effect) => effect.notes).filter(Boolean) ?? []

  return (
    <Panel className="weekly-candidates-panel" eyebrow="Candidate Queue" title="本週候補池">
      <div className="candidate-panel-status">
        <span>{isPending ? '切換中' : 'Ready'}</span>
        <strong>{candidates.length} 檔可見</strong>
      </div>
      {candidateLayer ? (
        <div className="candidate-layer-summary" aria-label="候選分層摘要">
          <span>
            <b>模型池</b>
            {candidateLayer.model_pool_count}
          </span>
          <span>
            <b>設定後</b>
            {candidateLayer.visible_candidate_count}
          </span>
          <span>
            <b>隱藏</b>
            {hiddenBySettings}
          </span>
        </div>
      ) : null}
      {candidates.length === 0 ? (
        <div className="candidate-empty-state">
          <strong>目前設定下沒有可見候選</strong>
          {settingEffectNotes.length > 0 ? <p>{settingEffectNotes.join(' ')}</p> : <p>可切換全域投資設定查看模型初選池中的其他標的。</p>}
        </div>
      ) : null}
      <div className="candidate-groups">
        {grouped.map(([status, groupItems]) => (
          <section className="candidate-group" key={status}>
            <header className="candidate-group__header">
              <h3>{status}</h3>
              <span>{groupItems.length}</span>
            </header>
            <div className="candidate-list">
              {groupItems.map((candidate) => (
                <CandidateRow
                  active={candidate.stock_id === selectedStockId}
                  candidate={candidate}
                  key={candidate.stock_id}
                  onSelectStock={onSelectStock}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </Panel>
  )
}

function CandidateRow({
  active,
  candidate,
  onSelectStock,
}: {
  active: boolean
  candidate: WeeklyCandidate
  onSelectStock: (stockId: string) => void
}) {
  const item = candidate.ranking
  const referenceChips = referenceChipsForRanking(item)

  return (
    <button
      aria-pressed={active}
      className={active ? 'candidate-row candidate-row--active' : 'candidate-row'}
      onClick={() => onSelectStock(candidate.stock_id)}
      type="button"
    >
      <span className="candidate-row__rank">{String(candidate.priority).padStart(2, '0')}</span>
      <span className="candidate-row__main">
        <strong>
          {candidate.stock_id} {candidate.stock_name}
        </strong>
        <small>
          {candidate.next_step} · {candidate.key_price}
        </small>
        <em>{candidate.primary_reasons.join(' / ')}</em>
        {referenceChips.length > 0 ? (
          <span className="candidate-row__tags" aria-label="分類與曝險參考">
            {referenceChips.map((chip) => (
              <span key={`${chip.label}-${chip.value}`}>
                <b>{chip.label}</b>
                {chip.value}
              </span>
            ))}
          </span>
        ) : null}
      </span>
      <span className="candidate-row__meta">
        <strong>{candidate.risk_label}</strong>
        <small>{formatPct(item.model_prob)}</small>
      </span>
    </button>
  )
}

function referenceChipsForRanking(item: RankingItem): Array<{ label: string; value: string }> {
  const chips: Array<{ label: string; value: string }> = []
  if (item.industry_name) chips.push({ label: '產業', value: item.industry_name })
  if (item.sector_name && item.sector_name !== item.industry_name) chips.push({ label: 'Sector', value: item.sector_name })
  const etf = splitReferenceText(item.major_etfs)[0]
  if (etf) chips.push({ label: 'ETF', value: etf })
  return chips.slice(0, 3)
}

function splitReferenceText(value?: string | null): string[] {
  if (!value) return []
  return value
    .split(/[|,、/]/)
    .map((item) => item.trim())
    .filter(Boolean)
}
