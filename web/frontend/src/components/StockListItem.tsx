import type { ReactNode } from 'react'

import { Button } from './Button'

export type StockListItemProps = {
  id: string
  active?: boolean
  className?: string
  name?: string
  onSelect?: (stockId: string) => void
  rank?: number
  score?: ReactNode
  subtitle?: ReactNode
}

export function StockListItem({
  active = false,
  className,
  id,
  name,
  onSelect,
  rank,
  score,
  subtitle,
}: StockListItemProps) {
  const classes = ['stock-list-item', active ? 'stock-list-item--active' : undefined, className]
    .filter(Boolean)
    .join(' ')

  const handleClick = () => {
    onSelect?.(id)
  }

  return (
    <Button
      aria-pressed={active}
      className={classes}
      fullWidth
      onClick={handleClick}
      variant={active ? 'solid' : 'ghost'}
    >
      {rank !== undefined ? (
        <span className="stock-list-item__rank">{String(rank).padStart(2, '0')}</span>
      ) : null}
      <span className="stock-list-item__main">
        <strong>{id}</strong>
        <small>{name ?? subtitle ?? '未命名'}</small>
      </span>
      {score ? <span className="stock-list-item__score">{score}</span> : null}
    </Button>
  )
}
