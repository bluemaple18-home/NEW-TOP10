import { MetricPill, Panel } from '../../components'
import type { WeeklyCandidateLayer, WeeklyMarketSummary } from '../../types'

type MarketSnapshotPanelProps = {
  candidateLayer?: WeeklyCandidateLayer | null
  modelPoolCount: number
  summary?: WeeklyMarketSummary | null
  versionLabel: string
}

export function MarketSnapshotPanel({ candidateLayer, modelPoolCount, summary, versionLabel }: MarketSnapshotPanelProps) {
  const groups = summary?.dominant_groups ?? []
  const riskAlert = summary?.risk_alerts?.join(' / ') ?? '載入 weekly decision contract 中。'
  const visibleCount = candidateLayer?.visible_candidate_count ?? modelPoolCount
  const hiddenCount = candidateLayer?.hidden_by_settings_count ?? 0

  return (
    <Panel className="market-panel">
      <div className="market-summary">
        <MetricPill label="本週版本" value={versionLabel} />
        <MetricPill label="模型初選池" value={`${modelPoolCount} 檔`} />
        <MetricPill label="設定後候選" value={`${visibleCount} 檔`} />
        <MetricPill label="設定隱藏" value={`${hiddenCount} 檔`} />
        <MetricPill label="大盤狀態" value={summary?.market_state ?? '載入中'} />
        <MetricPill label="機會品質" tone="positive" value={summary?.opportunity_quality ?? '等待資料'} />
      </div>
      <div className="market-context">
        <div>
          <p className="context-label">候補集中</p>
          {groups.length > 0 ? (
            <div className="context-chip-list" aria-label="本週候補分類集中">
              {groups.slice(0, 4).map((group) => (
                <span key={group}>{group}</span>
              ))}
            </div>
          ) : (
            <p>資料不足，暫以模型排序觀察。</p>
          )}
        </div>
        <div>
          <p className="context-label">操作環境</p>
          <p>{summary?.operation_environment ?? '讀取中'}</p>
        </div>
        <div>
          <p className="context-label">風險提醒</p>
          <p>{riskAlert}</p>
        </div>
      </div>
      {summary ? (
        <div className="opportunity-components">
          {summary.opportunity_components.map((component) => (
            <div className="opportunity-component" key={component.label}>
              <span>{component.label}</span>
              <strong>{component.value}</strong>
              {component.notes ? <small>{component.notes}</small> : null}
            </div>
          ))}
        </div>
      ) : null}
    </Panel>
  )
}
