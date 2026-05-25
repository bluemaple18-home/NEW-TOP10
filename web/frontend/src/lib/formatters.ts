export function formatPct(value?: number | null): string {
  if (value === undefined || value === null) return '--'
  return `${(value * 100).toFixed(1)}%`
}

export function formatNumber(value?: number | null, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '--'
  return value.toLocaleString('zh-TW', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}
