export type RankingItem = {
  stock_id: string
  stock_name?: string
  close?: number | null
  final_score?: number
  model_prob?: number
  rule_score?: number | null
  prediction_score?: number | null
  setup_score?: number | null
  quality_score?: number | null
  risk_penalty?: number | null
  risk_adjusted_score?: number | null
  risk_reward?: number | null
  market_regime?: string | null
  industry_code?: string | null
  industry_name?: string | null
  sector_name?: string | null
  market_type?: string | null
  theme_tags?: string | null
  concept_tags?: string | null
  major_etfs?: string | null
  suggested_weight?: number | null
  max_position_weight?: number | null
  gross_exposure?: number | null
  allocated_exposure?: number | null
  cash_weight?: number | null
  exposure_note?: string | null
  reasons?: string
}

export type LatestRankingResponse = {
  date: string | null
  items: RankingItem[]
  reference_summary?: RankingReferenceSummary | null
}

export type ExposureBreakdownItem = {
  name: string
  weight: number
  count: number
}

export type RankingReferenceSummary = {
  industry_exposure: ExposureBreakdownItem[]
  sector_exposure: ExposureBreakdownItem[]
  etf_overlap_count: number
  top_industry_concentration?: number | null
  notes?: string | null
}

export type RiskStyle = 'conservative' | 'balanced' | 'aggressive'
export type TargetType = 'stocks' | 'etfs' | 'both'
export type HoldingPeriod = 'swing' | 'midterm' | 'longterm'
export type EntryPreference = 'breakout' | 'pullback' | 'continuation' | 'mixed'
export type RiskLimit = 'lowVolatility' | 'excludeThemes' | 'acceptHighVolatility'

export type GlobalInvestmentSettings = {
  riskStyle: RiskStyle
  targetType: TargetType
  holdingPeriod: HoldingPeriod
  entryPreference: EntryPreference
  riskLimit: RiskLimit
}

export type WeeklyInvestmentSettingsContract = {
  risk_style: RiskStyle
  target_type: TargetType
  holding_period: HoldingPeriod
  entry_preference: EntryPreference
  risk_limit: RiskLimit
}

export type CandidateStatus = '可分批' | '等回測' | '觀察突破' | '續強觀察' | '暫停操作'

export type WeeklyOpportunityComponent = {
  label: string
  value: string
  notes?: string | null
}

export type WeeklyMarketSummary = {
  market_state: string
  operation_environment: string
  opportunity_quality: string
  opportunity_components: WeeklyOpportunityComponent[]
  dominant_groups: string[]
  risk_alerts: string[]
  setting_interpretation: string
}

export type WeeklyCandidate = {
  priority: number
  target_type: 'stock' | 'etf'
  stock_id: string
  stock_name?: string | null
  status: CandidateStatus
  risk_label: string
  next_step: string
  key_price: string
  primary_reasons: string[]
  ranking: RankingItem
}

export type WeeklyModelPoolItem = {
  priority: number
  target_type: 'stock' | 'etf'
  stock_id: string
  stock_name?: string | null
  ranking: RankingItem
}

export type WeeklySettingsEffect = {
  reason: string
  count: number
  notes?: string | null
}

export type WeeklyCandidateLayer = {
  model_pool_count: number
  stock_model_pool_count: number
  etf_model_pool_count: number
  visible_candidate_count: number
  hidden_by_settings_count: number
  settings_applied: boolean
  settings_effects: WeeklySettingsEffect[]
}

export type WeeklyChange = {
  kind: '暫停 / 降級' | '新增觀察' | '大反轉'
  title: string
  notes: string
}

export type WeeklyCandidatesResponse = {
  date: string | null
  version_label: string
  snapshot?: {
    schema_version: string
    snapshot_date?: string | null
    ranking_date?: string | null
    week_version?: string | null
    source: string
    artifact_path?: string | null
    generated_at?: string | null
    model_pool_count: number
  } | null
  settings: WeeklyInvestmentSettingsContract
  status_order: CandidateStatus[]
  market_summary: WeeklyMarketSummary
  model_pool_count: number
  model_pool: WeeklyModelPoolItem[]
  candidate_layer?: WeeklyCandidateLayer | null
  stock_candidates: WeeklyCandidate[]
  etf_candidates: WeeklyCandidate[]
  other_candidates: WeeklyCandidate[]
  week_changes: WeeklyChange[]
}

export type StockBar = {
  timestamp: number
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ma5?: number | null
  ma10?: number | null
  ma20?: number | null
  ma60?: number | null
  bb_upper?: number | null
  bb_middle?: number | null
  bb_lower?: number | null
  macd?: number | null
  macd_signal?: number | null
  macd_hist?: number | null
  k?: number | null
  d?: number | null
  rsi?: number | null
  volume_ratio_20d?: number | null
  candle_doji?: number | null
  candle_dragonfly_doji?: number | null
  candle_tombstone_doji?: number | null
  candle_hammer?: number | null
  candle_hanging_man?: number | null
  candle_shooting_star?: number | null
  candle_inverted_hammer?: number | null
  candle_bull_marubozu?: number | null
  candle_bear_marubozu?: number | null
  candle_bull_engulfing?: number | null
  candle_bear_engulfing?: number | null
  candle_bull_harami?: number | null
  candle_bear_harami?: number | null
  candle_piercing?: number | null
  candle_dark_cloud?: number | null
  candle_morning_star?: number | null
  candle_evening_star?: number | null
  candle_3white?: number | null
  candle_3black?: number | null
  td_count?: number | null
  td_buy_setup?: number | null
  td_sell_setup?: number | null
  pattern_w_bottom?: number | null
  pattern_m_top?: number | null
  pattern_neckline?: number | null
  pattern_stop_loss?: number | null
  pattern_resistance?: number | null
}

export type StockOhlcvResponse = {
  stock_id: string
  stock_name: string
  items: StockBar[]
}

export type FundamentalMetricItem = {
  year: string
  gross_margin?: number | null
  operating_margin?: number | null
  net_margin?: number | null
  current_ratio?: number | null
  debt_ratio?: number | null
  roe?: number | null
  roa?: number | null
  free_cash_flow?: number | null
  eps?: number | null
}

export type FundamentalWarningItem = {
  level: string
  field: string
  message: string
}

export type FundamentalSourceLinks = {
  income_statement?: string | null
  balance_sheet?: string | null
  cash_flow?: string | null
  mops?: string | null
  mops_otc?: string | null
}

export type FundamentalTrendItem = {
  key: string
  label: string
  latest_year?: string | null
  latest_value?: number | null
  previous_year?: string | null
  previous_value?: number | null
  change?: number | null
  direction: string
  tone: string
  summary: string
}

export type FundamentalDimensionSummary = {
  id: string
  label: string
  items: FundamentalTrendItem[]
  highlights: string[]
}

export type StockFundamentalsResponse = {
  stock_id: string
  available: boolean
  source?: string | null
  updated_at?: string | null
  source_links?: FundamentalSourceLinks | null
  years_covered: string[]
  metrics: FundamentalMetricItem[]
  dimensions: FundamentalDimensionSummary[]
  warnings: FundamentalWarningItem[]
  notes?: string | null
}

export type BacktestArtifact = {
  name: string
  path: string
  kind: string
  size_bytes: number
  modified_at: string
}

export type BacktestReportSummary = {
  name: string
  path: string
  title?: string | null
  excerpt?: string | null
  curve_path?: string | null
  period?: string | null
  threshold?: number | null
  trades?: number | null
  win_rate?: number | null
  avg_return?: number | null
  size_bytes: number
  modified_at: string
}

export type BacktestSummaryResponse = {
  reports: BacktestReportSummary[]
  curves: BacktestArtifact[]
}

export type StockDetailPriceSection = {
  available: boolean
  stock_id: string
  stock_name?: string | null
  items: StockBar[]
  signals: StockPatternSignal[]
  overlays: StockPatternOverlayLine[]
  notes?: string | null
}

export type StockPatternSignal = {
  date: string
  signal_id: string
  label: string
  category: string
  polarity: 'bullish' | 'bearish' | 'neutral' | string
  price?: number | null
  beginner_note?: string | null
  action_hint?: string | null
}

export type StockPatternOverlayLine = {
  signal_id: string
  label: string
  points: Array<Record<string, string | number>>
  notes?: string | null
}

export type StockDetailFundamentalSection = {
  available: boolean
  data?: StockFundamentalsResponse | null
  notes?: string | null
}

export type StockDetailTradePlanSection = {
  available: boolean
  horizon_days?: number | null
  entry_low?: number | null
  entry_high?: number | null
  stop_loss?: number | null
  target_price?: number | null
  risk_reward?: number | null
  position_hint?: string | null
  suggested_weight?: number | null
  max_position_weight?: number | null
  gross_exposure?: number | null
  allocated_exposure?: number | null
  cash_weight?: number | null
  exposure_note?: string | null
  notes?: string | null
}

export type StockDetailBacktestSection = {
  available: boolean
  scope?: string | null
  reports: BacktestReportSummary[]
  curves: BacktestArtifact[]
  notes?: string | null
}

export type StockIndustryClassification = {
  stock_id: string
  available: boolean
  industry_code?: string | null
  industry_name?: string | null
  sector_name?: string | null
  market_type?: string | null
  theme_tags: string[]
  source?: string | null
  updated_at?: string | null
  notes?: string | null
}

export type StockEtfExposure = {
  stock_id: string
  etf_id: string
  etf_name?: string | null
  weight?: number | null
  is_major_holding: boolean
  source?: string | null
  updated_at?: string | null
}

export type StockConceptMembership = {
  stock_id: string
  canonical_concept_id: string
  canonical_name: string
  raw_concept_name: string
  concept_type: string
  source?: string | null
  source_url?: string | null
  observed_at?: string | null
  confidence?: number | null
  match_method?: string | null
}

export type StockReferenceResponse = {
  available: boolean
  stock_id: string
  industry: StockIndustryClassification
  etfs: StockEtfExposure[]
  concepts: StockConceptMembership[]
  notes?: string | null
}

export type StockDetailReferenceSection = {
  available: boolean
  data?: StockReferenceResponse | null
  notes?: string | null
}

export type StockDetailResponse = {
  stock_id: string
  price: StockDetailPriceSection
  reference: StockDetailReferenceSection
  fundamentals: StockDetailFundamentalSection
  trade_plan: StockDetailTradePlanSection
  backtest: StockDetailBacktestSection
}
