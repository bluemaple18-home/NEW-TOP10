import type { ReactNode } from 'react'

export type MetricTone = 'neutral' | 'positive' | 'warning' | 'danger'

export type MetricPillProps = {
  label: ReactNode
  value: ReactNode
  className?: string
  hint?: ReactNode
  tone?: MetricTone
}

export function MetricPill({
  className,
  hint,
  label,
  tone = 'neutral',
  value,
}: MetricPillProps) {
  const classes = ['metric-pill', `metric-pill--${tone}`, className].filter(Boolean).join(' ')

  return (
    <div className={classes}>
      <span className="metric-pill__label">{label}</span>
      <strong className="metric-pill__value">{value}</strong>
      {hint ? <small className="metric-pill__hint">{hint}</small> : null}
    </div>
  )
}
