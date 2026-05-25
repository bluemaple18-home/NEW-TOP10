import { useState } from 'react'
import { KLineWorkbench } from '../../charts'
import { DetailSection, MetricPill, Panel } from '../../components'
import { formatNumber, formatPct } from '../../lib/formatters'
import type {
  BacktestReportSummary,
  FundamentalDimensionSummary,
  FundamentalMetricItem,
  RankingItem,
  StockDetailReferenceSection,
  StockFundamentalsResponse,
  StockDetailResponse,
  StockPatternSignal,
} from '../../types'

type StockDetailPanelProps = {
  error?: string | null
  selectedRanking?: RankingItem
  selectedStockId: string
  stockDetail: StockDetailResponse | null
}

const metricLabels: Array<[keyof FundamentalMetricItem, string, 'pct' | 'number']> = [
  ['roe', 'ROE', 'pct'],
  ['gross_margin', '毛利率', 'pct'],
  ['debt_ratio', '負債比', 'pct'],
  ['eps', 'EPS', 'number'],
  ['free_cash_flow', 'FCF', 'number'],
]

type AnalysisTabId = 'showcase' | 'fundamentals' | 'trade-plan' | 'backtest'

const analysisTabs: Array<{ id: AnalysisTabId; label: string; eyebrow: string }> = [
  { id: 'showcase', label: 'K 線案例', eyebrow: 'Show Case' },
  { id: 'fundamentals', label: '基本面', eyebrow: 'Fundamentals' },
  { id: 'trade-plan', label: '交易計畫', eyebrow: 'Trade Plan' },
  { id: 'backtest', label: '回測證據', eyebrow: 'Backtest' },
]

export function StockDetailPanel({
  error,
  selectedRanking,
  selectedStockId,
  stockDetail,
}: StockDetailPanelProps) {
  const price = stockDetail?.price
  const fundamentals = stockDetail?.fundamentals
  const reference = stockDetail?.reference
  const tradePlan = stockDetail?.trade_plan
  const backtest = stockDetail?.backtest
  const stockName = price?.stock_name ?? selectedRanking?.stock_name ?? ''
  const [activeAnalysisTab, setActiveAnalysisTab] = useState<AnalysisTabId>('showcase')

  return (
    <Panel className="chart-panel stock-workbench-panel">
      {error ? <div className="error-box">{error}</div> : null}
      <div className="workbench-label">
        <span>Stock Workbench</span>
        <strong>個股工作台</strong>
      </div>
      <div className="stock-header">
        <div>
          <p className="eyebrow">Selected Stock</p>
          <h2>
            {price?.stock_id ?? selectedStockId} {stockName}
          </h2>
          <StockDecisionLine selectedRanking={selectedRanking} tradePlan={tradePlan} />
        </div>
        <div className="stock-header__metrics">
          <MetricPill label="模型勝率" tone="positive" value={formatPct(selectedRanking?.model_prob)} />
          <MetricPill label="配置權重" value={formatPct(tradePlan?.suggested_weight ?? selectedRanking?.suggested_weight)} />
        </div>
      </div>
      <StockReferenceStrip reference={reference} selectedRanking={selectedRanking} />

      <div className="stock-detail-layout">
        <DetailSection eyebrow="Price" title="K 線工作台">
          {price?.available ? (
            <KLineWorkbench
              data={price.items}
              overlays={price.overlays}
              signals={price.signals}
              tradePlan={tradePlan?.available ? {
                entryHigh: tradePlan.entry_high,
                entryLow: tradePlan.entry_low,
                stopLoss: tradePlan.stop_loss,
                targetPrice: tradePlan.target_price,
              } : null}
            />
          ) : (
            <UnavailableState text={price?.notes ?? '載入 K 線資料中...'} />
          )}
        </DetailSection>

        <AnalysisTabs
          activeTab={activeAnalysisTab}
          backtest={backtest}
          fundamentals={fundamentals}
          onTabChange={setActiveAnalysisTab}
          priceAvailable={price?.available}
          signals={price?.signals ?? []}
          tradePlan={tradePlan}
        />
      </div>
    </Panel>
  )
}

function StockReferenceStrip({
  reference,
  selectedRanking,
}: {
  reference?: StockDetailReferenceSection
  selectedRanking?: RankingItem
}) {
  const industry = reference?.data?.industry
  const etfs = reference?.data?.etfs ?? []
  const concepts = reference?.data?.concepts ?? []
  const chips: Array<{ label: string; value: string }> = []
  const industryName = industry?.industry_name ?? selectedRanking?.industry_name
  const sectorName = industry?.sector_name ?? selectedRanking?.sector_name

  if (industryName) chips.push({ label: '產業', value: industryName })
  if (sectorName && sectorName !== industryName) chips.push({ label: 'Sector', value: sectorName })

  const majorEtf = etfs.find((item) => item.is_major_holding) ?? etfs[0]
  const fallbackEtf = splitReferenceText(selectedRanking?.major_etfs)[0]
  if (majorEtf) {
    chips.push({ label: 'ETF', value: majorEtf.etf_name ? `${majorEtf.etf_id} ${majorEtf.etf_name}` : majorEtf.etf_id })
  } else if (fallbackEtf) {
    chips.push({ label: 'ETF', value: fallbackEtf })
  }

  const theme = concepts.find((item) => item.concept_type !== 'industry')?.canonical_name ?? splitReferenceText(selectedRanking?.concept_tags)[0]
  if (theme) chips.push({ label: '概念', value: theme })

  if (chips.length === 0) return null

  return (
    <section className="stock-reference-strip" aria-label="分類與曝險參考">
      <div className="reference-chip-list">
        {chips.slice(0, 4).map((chip) => (
          <span className="reference-chip" key={`${chip.label}-${chip.value}`}>
            <b>{chip.label}</b>
            {chip.value}
          </span>
        ))}
      </div>
      <p>Reference only，不作為推薦理由或產業動能加分。</p>
    </section>
  )
}

function StockDecisionLine({
  selectedRanking,
  tradePlan,
}: {
  selectedRanking?: RankingItem
  tradePlan?: StockDetailResponse['trade_plan']
}) {
  const chips = [
    selectedRanking?.market_regime ? `盤勢 ${selectedRanking.market_regime}` : null,
    tradePlan?.available && tradePlan.entry_low && tradePlan.entry_high
      ? `進場 ${formatNumber(tradePlan.entry_low)} - ${formatNumber(tradePlan.entry_high)}`
      : null,
    tradePlan?.available && tradePlan.stop_loss ? `停損 ${formatNumber(tradePlan.stop_loss)}` : null,
    selectedRanking?.risk_reward ? `風報 ${formatNumber(selectedRanking.risk_reward)}` : null,
  ].filter(Boolean) as string[]

  if (chips.length === 0) return null

  return (
    <div className="stock-decision-line" aria-label="個股決策摘要">
      {chips.slice(0, 4).map((chip) => (
        <span key={chip}>{chip}</span>
      ))}
    </div>
  )
}

function AnalysisTabs({
  activeTab,
  backtest,
  fundamentals,
  onTabChange,
  priceAvailable,
  signals,
  tradePlan,
}: {
  activeTab: AnalysisTabId
  backtest?: StockDetailResponse['backtest']
  fundamentals?: StockDetailResponse['fundamentals']
  onTabChange: (tab: AnalysisTabId) => void
  priceAvailable?: boolean
  signals: StockPatternSignal[]
  tradePlan?: StockDetailResponse['trade_plan']
}) {
  return (
    <section className="stock-analysis-tabs" data-active-tab={activeTab} data-analysis-tabs="ready">
      <div className="analysis-tab-list" role="tablist" aria-label="個股詳細分析">
        {analysisTabs.map((tab) => (
          <button
            aria-controls={`analysis-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            className={`analysis-tab ${activeTab === tab.id ? 'analysis-tab--active' : ''}`}
            id={`analysis-tab-${tab.id}`}
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            role="tab"
            type="button"
          >
            <span>{tab.eyebrow}</span>
            <strong>{tab.label}</strong>
          </button>
        ))}
      </div>

      <div
        aria-labelledby={`analysis-tab-${activeTab}`}
        className="analysis-tab-panel"
        id={`analysis-panel-${activeTab}`}
        role="tabpanel"
      >
        {activeTab === 'showcase' ? <KLineShowCaseSection signals={signals} available={priceAvailable} /> : null}
        {activeTab === 'fundamentals' ? (
          <FundamentalSection
            fundamentals={fundamentals?.data}
            notes={fundamentals?.notes}
            available={fundamentals?.available}
          />
        ) : null}
        {activeTab === 'trade-plan' ? <TradePlanSection tradePlan={tradePlan} /> : null}
        {activeTab === 'backtest' ? <BacktestSection backtest={backtest} /> : null}
      </div>
    </section>
  )
}

function KLineShowCaseSection({
  available,
  signals,
}: {
  available?: boolean
  signals: StockPatternSignal[]
}) {
  const showCases = signals
    .filter((signal) => signal.polarity !== 'bearish')
    .slice(-3)
    .reverse()

  return (
    <DetailSection className="analysis-section analysis-section--showcase" eyebrow="Show Case" title="K 線案例">
      {available && showCases.length > 0 ? (
        <div className="showcase-list">
          {showCases.map((signal) => (
            <article className={`showcase-card showcase-card--${signal.polarity}`} key={`${signal.signal_id}-${signal.date}`}>
              <div className="showcase-card__header">
                <strong>{signal.label}</strong>
                <span>{signal.date}</span>
              </div>
              <p>{signal.beginner_note ?? '這是一個可搭配趨勢與量能觀察的 K 線訊號。'}</p>
              <small>{signal.action_hint ?? '先確認支撐與停損，再決定是否分批。'}</small>
            </article>
          ))}
        </div>
      ) : (
        <UnavailableState text={available ? '這檔近期沒有明確多方案例，先看價格結構。' : '載入 K 線案例中...'} />
      )}
    </DetailSection>
  )
}

function FundamentalSection({
  available,
  fundamentals,
  notes,
}: {
  available?: boolean
  fundamentals?: StockFundamentalsResponse | null
  notes?: string | null
}) {
  const metrics = fundamentals?.metrics ?? []
  const latest = metrics[0]
  const dimensions = fundamentals?.dimensions ?? []

  return (
    <DetailSection className="analysis-section analysis-section--fundamentals" eyebrow="Fundamentals" title="基本面品質">
      {available && latest ? (
        <>
          <div className="metric-grid fundamental-metrics">
            {metricLabels.map(([key, label, type]) => {
              const value = latest[key] as number | null | undefined
              return (
                <MetricPill
                  key={key}
                  label={label}
                  value={type === 'pct' ? formatMetricPct(value) : formatNumber(value)}
                />
              )
            })}
          </div>
          {dimensions.length > 0 ? <FundamentalDimensions dimensions={dimensions} /> : null}
          <FundamentalSourceLine fundamentals={fundamentals} />
          {fundamentals?.warnings.length ? (
            <div className="fundamental-warnings">
              {fundamentals.warnings.map((warning) => (
                <span key={`${warning.field}-${warning.message}`}>{warning.field}: {warning.message}</span>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <UnavailableState text={notes ?? '尚無基本面 cache'} />
      )}
      {notes && available ? <p className="detail-note">{notes}</p> : null}
    </DetailSection>
  )
}

function FundamentalDimensions({ dimensions }: { dimensions: FundamentalDimensionSummary[] }) {
  return (
    <div className="fundamental-dimensions">
      {dimensions.map((dimension) => (
        <article className="fundamental-dimension" key={dimension.id}>
          <strong>{dimension.label}</strong>
          <ul>
            {dimension.highlights.slice(0, 3).map((highlight) => (
              <li key={highlight}>{highlight}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  )
}

function FundamentalSourceLine({ fundamentals }: { fundamentals?: StockFundamentalsResponse | null }) {
  if (!fundamentals) return null
  const links = fundamentals.source_links
  return (
    <div className="fundamental-source-line">
      <span>{fundamentals.source ?? '來源未標示'}</span>
      {fundamentals.updated_at ? <span>更新 {fundamentals.updated_at}</span> : null}
      {fundamentals.years_covered.length ? <span>年度 {fundamentals.years_covered.slice(0, 3).join(' / ')}</span> : null}
      {links?.mops ? <a href={links.mops} rel="noopener noreferrer" target="_blank">MOPS</a> : null}
      {links?.income_statement ? <a href={links.income_statement} rel="noopener noreferrer" target="_blank">Goodinfo</a> : null}
    </div>
  )
}

function TradePlanSection({ tradePlan }: { tradePlan?: StockDetailResponse['trade_plan'] }) {
  return (
    <DetailSection className="analysis-section analysis-section--trade-plan" eyebrow="Trade Plan" title="交易計畫">
      {tradePlan?.available ? (
        <>
          <div className="plan-block">
            <h4>執行價位</h4>
            <div className="metric-grid plan-metrics">
              <MetricPill label="進場區間" value={`${formatNumber(tradePlan.entry_low)} - ${formatNumber(tradePlan.entry_high)}`} />
              <MetricPill label="停損" tone="warning" value={formatNumber(tradePlan.stop_loss)} />
              <MetricPill label="目標" tone="positive" value={formatNumber(tradePlan.target_price)} />
              <MetricPill label="風報比" value={formatNumber(tradePlan.risk_reward)} />
            </div>
          </div>
          <div className="plan-block">
            <h4>部位設定</h4>
            <div className="metric-grid plan-metrics">
              <MetricPill label="建議權重" value={formatPct(tradePlan.suggested_weight)} />
              <MetricPill label="單檔上限" value={formatPct(tradePlan.max_position_weight)} />
              <MetricPill label="目標曝險" value={formatPct(tradePlan.gross_exposure)} />
              <MetricPill label="已配置" value={formatPct(tradePlan.allocated_exposure)} />
            </div>
          </div>
          <div className="plan-notes">
            {tradePlan.exposure_note ? <p className="detail-note">{tradePlan.exposure_note}</p> : null}
            {tradePlan.notes ? <p className="detail-note detail-note--muted">{tradePlan.notes}</p> : null}
          </div>
        </>
      ) : (
        <UnavailableState text={tradePlan?.notes ?? '尚無交易計畫'} />
      )}
    </DetailSection>
  )
}

function BacktestSection({ backtest }: { backtest?: StockDetailResponse['backtest'] }) {
  const report = backtest?.reports[0]

  return (
    <DetailSection className="analysis-section analysis-section--backtest" eyebrow="Backtest" title="回測證據">
      {backtest?.available ? (
        <div className="backtest-evidence">
          {report ? <BacktestReportLine report={report} /> : null}
          <div className="backtest-summary">
            <span>{formatBacktestScope(backtest.scope)}</span>
            <span>{backtest.reports.length} 份報告</span>
            <span>{backtest.curves.length > 0 ? `${backtest.curves.length} 張權益曲線` : '權益曲線未提供'}</span>
          </div>
          {backtest.notes ? <p className="detail-note detail-note--muted">{backtest.notes}</p> : null}
        </div>
      ) : (
        <UnavailableState text={backtest?.notes ?? '尚無回測 artifact'} />
      )}
    </DetailSection>
  )
}

function BacktestReportLine({ report }: { report: BacktestReportSummary }) {
  return (
    <div className="backtest-report-line">
      <strong>{report.title ?? report.name}</strong>
      <small>
        勝率 {formatMetricPct(report.win_rate)} · 交易 {report.trades ?? '--'} 筆
      </small>
    </div>
  )
}

function UnavailableState({ text }: { text: string }) {
  return <div className="detail-unavailable">{text}</div>
}

function formatMetricPct(value?: number | null): string {
  if (value === undefined || value === null) return '--'
  return `${value.toFixed(1)}%`
}

function formatBacktestScope(scope?: string | null): string {
  if (scope === 'system') return '系統層回測'
  if (scope === 'stock') return '個股回測'
  return '回測層級未標示'
}

function splitReferenceText(value?: string | null): string[] {
  if (!value) return []
  return value
    .split(/[|,、/]/)
    .map((item) => item.trim())
    .filter(Boolean)
}
