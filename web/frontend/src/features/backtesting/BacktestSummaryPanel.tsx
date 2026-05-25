import { Panel } from '../../components'
import type { BacktestSummaryResponse } from '../../types'

type BacktestSummaryPanelProps = {
  summary: BacktestSummaryResponse | null
}

export function BacktestSummaryPanel({ summary }: BacktestSummaryPanelProps) {
  return (
    <Panel className="backtest-panel" eyebrow="Backtest" title="回測績效摘要">
      {summary ? (
        <div className="backtest-summary">
          <span>{summary.reports.length} 份報告</span>
          <span>{summary.curves.length} 張權益曲線</span>
        </div>
      ) : (
        <div className="backtest-summary backtest-summary--muted">回測資料獨立載入，不阻塞看盤台。</div>
      )}
    </Panel>
  )
}
