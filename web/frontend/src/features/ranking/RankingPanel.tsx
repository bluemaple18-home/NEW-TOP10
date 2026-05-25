import { Panel, StockListItem } from '../../components'
import { formatPct } from '../../lib/formatters'
import type { RankingItem } from '../../types'

type RankingPanelProps = {
  items: RankingItem[]
  isPending?: boolean
  selectedStockId: string
  onSelectStock: (stockId: string) => void
}

export function RankingPanel({
  isPending = false,
  items,
  onSelectStock,
  selectedStockId,
}: RankingPanelProps) {
  return (
    <Panel as="aside" className="ranking-panel">
      <div className="panel-heading">
        <span>Top 10</span>
        <small>{isPending ? '切換中' : 'Ready'}</small>
      </div>
      <div className="ranking-list">
        {items.map((item, index) => (
          <StockListItem
            active={item.stock_id === selectedStockId}
            id={item.stock_id}
            key={item.stock_id}
            name={item.stock_name}
            onSelect={onSelectStock}
            rank={index + 1}
            score={formatPct(item.model_prob)}
          />
        ))}
      </div>
    </Panel>
  )
}
