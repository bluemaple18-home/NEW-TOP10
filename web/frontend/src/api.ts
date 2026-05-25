import type {
  BacktestSummaryResponse,
  GlobalInvestmentSettings,
  LatestRankingResponse,
  StockDetailResponse,
  StockOhlcvResponse,
  WeeklyCandidatesResponse,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001'

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`API 請求失敗：${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export function fetchLatestRanking(limit = 10): Promise<LatestRankingResponse> {
  return fetchJson<LatestRankingResponse>(`/api/rankings/latest?limit=${limit}`)
}

export function fetchWeeklyCandidates(settings: GlobalInvestmentSettings, limit = 10): Promise<WeeklyCandidatesResponse> {
  const params = new URLSearchParams({
    risk_style: settings.riskStyle,
    target_type: settings.targetType,
    holding_period: settings.holdingPeriod,
    entry_preference: settings.entryPreference,
    risk_limit: settings.riskLimit,
    limit: String(limit),
  })
  return fetchJson<WeeklyCandidatesResponse>(`/api/weekly-candidates?${params.toString()}`)
}

export function fetchStockOhlcv(stockId: string, limit = 1200): Promise<StockOhlcvResponse> {
  return fetchJson<StockOhlcvResponse>(`/api/stocks/${stockId}/ohlcv?limit=${limit}`)
}

export function fetchStockDetail(stockId: string, limit = 1200): Promise<StockDetailResponse> {
  return fetchJson<StockDetailResponse>(`/api/stocks/${stockId}/detail?limit=${limit}`)
}

export function fetchBacktestSummary(): Promise<BacktestSummaryResponse> {
  return fetchJson<BacktestSummaryResponse>('/api/backtests/summary')
}
