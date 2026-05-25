import type {
  CandidateStatus,
  EntryPreference,
  GlobalInvestmentSettings,
  HoldingPeriod,
  RiskLimit,
  RiskStyle,
  TargetType,
} from '../../types'

export type {
  CandidateStatus,
  EntryPreference,
  GlobalInvestmentSettings,
  HoldingPeriod,
  RiskLimit,
  RiskStyle,
  TargetType,
}

export const defaultInvestmentSettings: GlobalInvestmentSettings = {
  riskStyle: 'balanced',
  targetType: 'stocks',
  holdingPeriod: 'swing',
  entryPreference: 'mixed',
  riskLimit: 'excludeThemes',
}

export const candidateStatusOrder: CandidateStatus[] = ['可分批', '等回測', '觀察突破', '續強觀察', '暫停操作']

export function riskStyleLabel(value: RiskStyle): string {
  if (value === 'conservative') return '保守動能'
  if (value === 'aggressive') return '積極動能'
  return '穩健動能'
}

export function targetTypeLabel(value: TargetType): string {
  if (value === 'etfs') return 'ETF'
  if (value === 'both') return '都看'
  return '個股'
}

export function holdingPeriodLabel(value: HoldingPeriod): string {
  if (value === 'midterm') return '中期'
  if (value === 'longterm') return '中長期'
  return '波段'
}

export function entryPreferenceLabel(value: EntryPreference): string {
  if (value === 'breakout') return '突破'
  if (value === 'pullback') return '回測'
  if (value === 'continuation') return '趨勢延續'
  return '綜合'
}

export function riskLimitLabel(value: RiskLimit): string {
  if (value === 'lowVolatility') return '只看低波動'
  if (value === 'acceptHighVolatility') return '可接受高波動'
  return '排除高波動題材'
}
