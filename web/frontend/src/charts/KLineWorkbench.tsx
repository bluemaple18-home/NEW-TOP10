import { useEffect, useRef, useState } from 'react'
import { dispose, init, registerOverlay, type Chart, type KLineData, type LayoutChild, type OverlayFigure } from 'klinecharts'
import type { StockBar, StockPatternOverlayLine, StockPatternSignal } from '../types'

type KLineWorkbenchProps = {
  data: StockBar[]
  overlays?: StockPatternOverlayLine[]
  signals?: StockPatternSignal[]
  tradePlan?: TradePlanOverlay | null
}

type RangeKey = '30D' | '3M' | '6M' | '1Y' | 'all'
type KLineDensity = 'full' | 'compact'

const COMPACT_KLINE_WIDTH = 520

type TradePlanOverlay = {
  entryLow?: number | null
  entryHigh?: number | null
  stopLoss?: number | null
  targetPrice?: number | null
}

type TradePlanOverlayData = {
  entryLow: number
  entryHigh: number
  stopLoss: number
  targetPrice: number
}
type TradePlanRailMark = {
  tone: 'entry' | 'stop' | 'target'
  label: string
  value: string
  top: number
}
type SignalBadgeOverlayData = {
  color: string
  label: string
  placement: 'above' | 'below'
  showLabel: boolean
  textSize: number
}

let isTradePlanOverlayRegistered = false
let isSignalBadgeOverlayRegistered = false

function ensureTradePlanOverlayRegistered() {
  if (isTradePlanOverlayRegistered) return

  registerOverlay<TradePlanOverlayData>({
    name: 'tradePlanOverlay',
    totalStep: 1,
    lock: true,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ bounding, coordinates }) => {
      const entryLowY = coordinates[0]?.y
      const entryHighY = coordinates[1]?.y
      const stopY = coordinates[2]?.y
      const targetY = coordinates[3]?.y
      if (
        entryLowY === undefined ||
        entryHighY === undefined ||
        stopY === undefined ||
        targetY === undefined
      ) {
        return []
      }

      const entryTop = Math.min(entryLowY, entryHighY)
      const entryHeight = Math.max(2, Math.abs(entryHighY - entryLowY))

      return [
        {
          type: 'rect',
          attrs: { x: 0, y: entryTop, width: bounding.width, height: entryHeight },
          styles: { color: 'rgba(127, 213, 196, 0.13)', borderColor: 'rgba(127, 213, 196, 0.42)', borderSize: 1 },
          ignoreEvent: true,
        },
        lineFigure(entryLowY, '#7fd5c4', 'solid', 2, bounding.width),
        lineFigure(entryHighY, '#7fd5c4', 'solid', 2, bounding.width),
        lineFigure(stopY, '#f2d57e', 'dashed', 2, bounding.width),
        lineFigure(targetY, '#f23663', 'dashed', 2, bounding.width),
      ]
    },
  })

  isTradePlanOverlayRegistered = true
}

function ensureSignalBadgeOverlayRegistered() {
  if (isSignalBadgeOverlayRegistered) return

  registerOverlay<SignalBadgeOverlayData>({
    name: 'signalBadge',
    totalStep: 1,
    lock: true,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates, overlay }) => {
      const coordinate = coordinates[0]
      const data = overlay.extendData
      if (!coordinate || !data) return []

      const isAbove = data.placement === 'above'
      const iconY = coordinate.y + (isAbove ? -12 : 12)
      const textY = coordinate.y + (isAbove ? -20 : 20)
      const triangle = isAbove
        ? [
            { x: coordinate.x - 5, y: iconY - 4 },
            { x: coordinate.x + 5, y: iconY - 4 },
            { x: coordinate.x, y: iconY + 5 },
          ]
        : [
            { x: coordinate.x - 5, y: iconY + 4 },
            { x: coordinate.x + 5, y: iconY + 4 },
            { x: coordinate.x, y: iconY - 5 },
          ]

      const figures: OverlayFigure[] = [
        {
          type: 'line',
          attrs: { coordinates: [{ x: coordinate.x, y: coordinate.y }, { x: coordinate.x, y: iconY }] },
          styles: { color: data.color, size: 1, style: 'dashed' },
          ignoreEvent: true,
        },
        {
          type: 'polygon',
          attrs: { coordinates: triangle },
          styles: { color: data.color, borderColor: data.color, borderSize: 1 },
          ignoreEvent: true,
        }
      ]

      if (data.showLabel) {
        figures.push({
          type: 'text',
          attrs: {
            x: coordinate.x,
            y: textY,
            text: data.label,
            align: 'center',
            baseline: isAbove ? 'bottom' : 'top',
          },
          styles: {
            color: '#f3f0e8',
            size: data.textSize,
            weight: 'bold',
            backgroundColor: 'rgba(17, 24, 32, 0.82)',
          },
          ignoreEvent: true,
        })
      }

      return figures
    },
  })

  isSignalBadgeOverlayRegistered = true
}

function lineFigure(y: number, color: string, style = 'solid', size = 1, width = Number.MAX_SAFE_INTEGER): OverlayFigure {
  return {
    type: 'line',
    attrs: { coordinates: [{ x: 0, y }, { x: width, y }] },
    styles: { color, size, style },
    ignoreEvent: true,
  }
}

function toKLineData(data: StockBar[]): KLineData[] {
  return data.map((bar) => ({
    timestamp: bar.timestamp,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  }))
}

function fullLayout(): LayoutChild[] {
  return [
    {
      type: 'candle',
      options: {
        id: 'candle_pane',
        height: 620,
        minHeight: 420,
        dragEnabled: true,
        axis: {
          scrollZoomEnabled: true,
          inside: false,
          position: 'right',
        },
      },
    },
    {
      type: 'indicator',
      content: ['VOL'],
      options: {
        id: 'volume_pane',
        height: 104,
        minHeight: 72,
        dragEnabled: true,
        axis: { scrollZoomEnabled: true },
      },
    },
    {
      type: 'indicator',
      content: ['MACD'],
      options: {
        id: 'macd_pane',
        height: 108,
        minHeight: 72,
        dragEnabled: true,
        axis: { scrollZoomEnabled: true },
      },
    },
    { type: 'xAxis' },
  ]
}

function compactLayout(): LayoutChild[] {
  return [
    {
      type: 'candle',
      options: {
        id: 'candle_pane',
        height: 430,
        minHeight: 340,
        dragEnabled: true,
        axis: {
          scrollZoomEnabled: true,
          inside: false,
          position: 'right',
        },
      },
    },
    {
      type: 'indicator',
      content: ['VOL'],
      options: {
        id: 'volume_pane',
        height: 84,
        minHeight: 72,
        dragEnabled: true,
        axis: { scrollZoomEnabled: true },
      },
    },
    { type: 'xAxis' },
  ]
}

function densityForWidth(width: number | null | undefined): KLineDensity {
  return typeof width === 'number' && width <= COMPACT_KLINE_WIDTH ? 'compact' : 'full'
}

export function KLineWorkbench({ data, overlays = [], signals = [], tradePlan }: KLineWorkbenchProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<Chart | null>(null)
  const activeRangeRef = useRef<RangeKey>('30D')
  const [isChartActive, setIsChartActive] = useState(false)
  const [activeRange, setActiveRange] = useState<RangeKey>('30D')
  const [activeBarSpace, setActiveBarSpace] = useState(0)
  const [activeVisibleBars, setActiveVisibleBars] = useState(0)
  const [activeWindowBars, setActiveWindowBars] = useState(0)
  const [activeRangeLimited, setActiveRangeLimited] = useState(false)
  const [activeTradeOverlay, setActiveTradeOverlay] = useState<'ready' | 'empty'>('empty')
  const [tradePlanRailMarks, setTradePlanRailMarks] = useState<TradePlanRailMark[]>([])
  const [chartDensity, setChartDensity] = useState<KLineDensity>('full')
  const [rangeRevision, setRangeRevision] = useState(0)

  const scrollToLatest = () => {
    const latest = data.at(-1)
    if (!latest) return
    chartRef.current?.scrollToTimestamp(latest.timestamp, 180)
  }

  const zoom = (scale: number) => {
    chartRef.current?.zoomAtCoordinate(scale, undefined, 160)
  }

  const focusWindow = (range: RangeKey) => {
    if (data.length === 0) return

    const chart = chartRef.current
    if (!chart) return

    setActiveRange(range)
    activeRangeRef.current = range
    setRangeRevision((revision) => revision + 1)

    chart.resize()

    const allChartData = toKLineData(data)
    const requestedBars = rangeToRequestedBars(range, data.length)
    const targetBars = rangeToBars(range, data.length)
    const windowedData = data.slice(-targetBars)
    const chartWidth = chart.getSize('candle_pane')?.width ?? containerRef.current?.clientWidth ?? 900
    const maxBarSpace = 50
    const targetBarSpace = Math.max(3, Math.min(maxBarSpace, chartWidth / Math.max(targetBars, 1)))

    chart.setDataLoader({
      getBars: ({ callback }) => {
        callback(allChartData, false)
      },
    })
    chart.resetData()
    chart.setBarSpace(targetBarSpace)
    chart.setOffsetRightDistance(12)
    drawPatternOverlays(
      chart,
      windowedData,
      signalsForWindow(windowedData, signals),
      overlaysForWindow(windowedData, overlays),
      chartDensity,
    )
    setActiveTradeOverlay(drawTradePlanOverlay(chart, tradePlan, windowedData) ? 'ready' : 'empty')
    setActiveBarSpace(Number(chart.getBarSpace().bar.toFixed(2)))
    setActiveWindowBars(windowedData.length)
    setActiveRangeLimited(range !== 'all' && requestedBars > data.length)
    chart.scrollToRealTime(180)

    window.requestAnimationFrame(() => {
      chart.setBarSpace(targetBarSpace)
      chart.setOffsetRightDistance(12)
      chart.scrollToRealTime(0)
      const visibleRange = chart.getVisibleRange()
      setActiveBarSpace(Number(chart.getBarSpace().bar.toFixed(2)))
      setActiveVisibleBars(Math.max(0, Math.round(visibleRange.to - visibleRange.from)))
      setTradePlanRailMarks(tradePlanMarksForRail(chart, tradePlan, windowedData))
    })
  }

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    container.replaceChildren()

    const chart = init(container, {
      zoomAnchor: 'cursor',
      layout: chartDensity === 'compact' ? compactLayout() : fullLayout(),
      styles: {
        candle: {
          ...(chartDensity === 'compact'
            ? {
                tooltip: {
                  showRule: 'none',
                },
              }
            : {}),
          priceMark: {
            show: false,
          },
          bar: {
            upColor: '#ef5350',
            downColor: '#26a69a',
            noChangeColor: '#b8c2cc',
            upBorderColor: '#ef5350',
            downBorderColor: '#26a69a',
            noChangeBorderColor: '#b8c2cc',
            upWickColor: '#ef5350',
            downWickColor: '#26a69a',
            noChangeWickColor: '#b8c2cc',
          },
        },
        grid: {
          horizontal: { color: 'rgba(221, 230, 237, 0.08)' },
          vertical: { color: 'rgba(221, 230, 237, 0.08)' },
        },
        ...(chartDensity === 'compact'
          ? {
              indicator: {
                tooltip: {
                  showRule: 'none',
                },
              },
            }
          : {}),
      },
    })

    if (!chart) return

    chartRef.current = chart
    chart.setScrollEnabled(false)
    chart.setZoomEnabled(false)
    chart.setSymbol({ ticker: 'TWSE', pricePrecision: 2, volumePrecision: 0 })
    chart.setPeriod({ type: 'day', span: 1 })
    if (chartDensity === 'full') {
      chart.createIndicator('MA', false, { id: 'candle_pane' })
      chart.createIndicator('BOLL', false, { id: 'candle_pane' })
      chart.createIndicator('KDJ')
    }

    const resizeObserver = new ResizeObserver(() => {
      const nextDensity = densityForWidth(container.clientWidth)
      setChartDensity((current) => (current === nextDensity ? current : nextDensity))
      chart.resize()
    })
    resizeObserver.observe(container)

    return () => {
      try {
        resizeObserver.disconnect()
        dispose(chart)
      } finally {
        container.replaceChildren()
        if (chartRef.current === chart) {
          chartRef.current = null
        }
      }
    }
  }, [chartDensity])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    chart.setScrollEnabled(isChartActive)
    chart.setZoomEnabled(isChartActive)
  }, [isChartActive])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsChartActive(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    window.requestAnimationFrame(() => {
      focusWindow(activeRangeRef.current)
    })
  }, [data, overlays, signals, tradePlan, chartDensity])

  return (
    <div
      className="kline-workbench"
      data-active-bar-space={activeBarSpace}
      data-active-range={activeRange}
      data-active-visible-bars={activeVisibleBars}
      data-active-window-bars={activeWindowBars}
      data-entry-high={tradePlan?.entryHigh ?? ''}
      data-entry-low={tradePlan?.entryLow ?? ''}
      data-kline-density={chartDensity}
      data-range-limited={activeRangeLimited}
      data-range-revision={rangeRevision}
      data-stop-loss={tradePlan?.stopLoss ?? ''}
      data-target-price={tradePlan?.targetPrice ?? ''}
      data-trade-overlay={activeTradeOverlay}
    >
      <div className="chart-toolbar">
        <div className="toolbar-group">
          <RangeButton activeRange={activeRange} label="30D" onClick={() => focusWindow('30D')} />
          <RangeButton activeRange={activeRange} label="3M" onClick={() => focusWindow('3M')} />
          <RangeButton activeRange={activeRange} label="6M" onClick={() => focusWindow('6M')} />
          <RangeButton activeRange={activeRange} label="1Y" onClick={() => focusWindow('1Y')} />
          <RangeButton activeRange={activeRange} label="all" text="全部" onClick={() => focusWindow('all')} />
        </div>
        <div className="toolbar-group">
          <button type="button" onClick={() => zoom(1.15)}>放大</button>
          <button type="button" onClick={() => zoom(0.85)}>縮小</button>
          <button type="button" onClick={scrollToLatest}>回到最新</button>
        </div>
      </div>
      {activeRangeLimited ? (
        <div className="range-limit-note">
          目前只有 {data.length} 根日 K，此區間已顯示全部可用資料。
        </div>
      ) : null}
      <div className={isChartActive ? 'gesture-hint gesture-hint--active' : 'gesture-hint'}>
        {isChartActive ? '圖表操作中：可拖曳平移、滾輪縮放；滑出圖表或按 Esc 結束。' : '頁面滾動不會縮放 K 線；點一下圖表後才啟用拖曳與滾輪縮放。'}
      </div>
      <div
        className={isChartActive ? 'kline-chart-stage kline-chart-stage--active' : 'kline-chart-stage'}
        onMouseLeave={() => setIsChartActive(false)}
        onPointerDown={() => setIsChartActive(true)}
        onWheelCapture={(event) => {
          if (!isChartActive) event.stopPropagation()
        }}
      >
        <div className="kline-chart" ref={containerRef} />
        <TradePlanSummary marks={tradePlanRailMarks} tradePlan={tradePlan} />
      </div>
    </div>
  )
}

function TradePlanSummary({
  marks,
  tradePlan,
}: {
  marks: TradePlanRailMark[]
  tradePlan?: TradePlanOverlay | null
}) {
  const normalized = normalizeTradePlan(tradePlan)
  if (!normalized) return null

  const fallbackMarks: TradePlanRailMark[] = [
    { tone: 'entry', label: '進場區間', value: `${formatPrice(normalized.entryLow)} - ${formatPrice(normalized.entryHigh)}`, top: 110 },
    { tone: 'stop', label: '停損', value: formatPrice(normalized.stopLoss), top: 170 },
    { tone: 'target', label: '停利目標', value: formatPrice(normalized.targetPrice), top: 50 },
  ]
  const railMarks = marks.length > 0 ? marks : fallbackMarks

  return (
    <aside className="kline-trade-plan-rail" aria-label="K 線交易計畫摘要">
      {railMarks.map((mark) => (
        <span
          className={`kline-trade-plan-rail__mark kline-trade-plan-rail__mark--${mark.tone}`}
          key={mark.tone}
          style={{ top: `${mark.top}px` }}
        >
          <b>{mark.label}</b>
          <em>{mark.value}</em>
        </span>
      ))}
    </aside>
  )
}

function rangeToBars(range: RangeKey, dataLength: number): number {
  return Math.min(rangeToRequestedBars(range, dataLength), Math.max(dataLength, 1))
}

function rangeToRequestedBars(range: RangeKey, dataLength: number): number {
  if (range === '30D') return 30
  if (range === '3M') return 60
  if (range === '6M') return 120
  if (range === '1Y') return 240
  return Math.max(dataLength, 1)
}

function signalsForWindow(data: StockBar[], signals: StockPatternSignal[]): StockPatternSignal[] {
  const visibleDates = new Set(data.map((bar) => bar.time))
  if (visibleDates.size === 0) return []
  return signals.filter((signal) => visibleDates.has(signal.date))
}

function overlaysForWindow(
  data: StockBar[],
  overlays: StockPatternOverlayLine[],
): StockPatternOverlayLine[] {
  const visibleDates = new Set(data.map((bar) => bar.time))
  if (visibleDates.size === 0) return []
  return overlays
    .map((overlay) => ({
      ...overlay,
      points: overlay.points.filter((point) => (
        typeof point.time === 'string' && visibleDates.has(point.time)
      )),
    }))
    .filter((overlay) => overlay.points.length > 0)
}

function drawTradePlanOverlay(
  chart: Chart,
  tradePlan: TradePlanOverlay | null | undefined,
  data: StockBar[],
): boolean {
  const overlayChart = chart as unknown as {
    createOverlay: (overlay: Record<string, unknown>) => unknown
    removeOverlay: (filter: Record<string, unknown>) => unknown
  }
  overlayChart.removeOverlay({ groupId: 'trade-plan' })

  const latest = data.at(-1)
  const normalized = normalizeTradePlan(tradePlan)
  if (!latest || !normalized) return false

  ensureTradePlanOverlayRegistered()
  overlayChart.createOverlay({
    name: 'tradePlanOverlay',
    groupId: 'trade-plan',
    lock: true,
    points: [
      { timestamp: latest.timestamp, value: normalized.entryLow },
      { timestamp: latest.timestamp, value: normalized.entryHigh },
      { timestamp: latest.timestamp, value: normalized.stopLoss },
      { timestamp: latest.timestamp, value: normalized.targetPrice },
    ],
    extendData: normalized,
  })
  return true
}

function tradePlanMarksForRail(
  chart: Chart,
  tradePlan: TradePlanOverlay | null | undefined,
  data: StockBar[],
): TradePlanRailMark[] {
  const latest = data.at(-1)
  const normalized = normalizeTradePlan(tradePlan)
  if (!latest || !normalized) return []

  const points = chart.convertToPixel(
    [
      { timestamp: latest.timestamp, value: normalized.entryLow },
      { timestamp: latest.timestamp, value: normalized.entryHigh },
      { timestamp: latest.timestamp, value: normalized.stopLoss },
      { timestamp: latest.timestamp, value: normalized.targetPrice },
    ],
    { paneId: 'candle_pane' },
  )
  if (!Array.isArray(points)) return []

  const entryLowY = toFiniteNumber(points[0]?.y)
  const entryHighY = toFiniteNumber(points[1]?.y)
  const stopY = toFiniteNumber(points[2]?.y)
  const targetY = toFiniteNumber(points[3]?.y)
  if (entryLowY === null || entryHighY === null || stopY === null || targetY === null) return []
  const paneHeight = chart.getSize('candle_pane')?.height ?? 620
  const labelTop = (value: number) => Math.round(clamp(value, 34, Math.max(34, paneHeight - 34)))

  return [
    {
      tone: 'entry',
      label: '進場區間',
      value: `${formatPrice(normalized.entryLow)} - ${formatPrice(normalized.entryHigh)}`,
      top: labelTop((entryLowY + entryHighY) / 2),
    },
    {
      tone: 'stop',
      label: '停損',
      value: formatPrice(normalized.stopLoss),
      top: labelTop(stopY),
    },
    {
      tone: 'target',
      label: '停利目標',
      value: formatPrice(normalized.targetPrice),
      top: labelTop(targetY),
    },
  ]
}

function normalizeTradePlan(tradePlan: TradePlanOverlay | null | undefined): TradePlanOverlayData | null {
  const entryLow = toFiniteNumber(tradePlan?.entryLow)
  const entryHigh = toFiniteNumber(tradePlan?.entryHigh)
  const stopLoss = toFiniteNumber(tradePlan?.stopLoss)
  const targetPrice = toFiniteNumber(tradePlan?.targetPrice)
  if (
    entryLow === null ||
    entryHigh === null ||
    stopLoss === null ||
    targetPrice === null
  ) {
    return null
  }
  return { entryLow, entryHigh, stopLoss, targetPrice }
}

function toFiniteNumber(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function formatPrice(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '--'
}

function RangeButton({
  activeRange,
  label,
  onClick,
  text,
}: {
  activeRange: RangeKey
  label: RangeKey
  onClick: () => void
  text?: string
}) {
  return (
    <button
      aria-pressed={activeRange === label}
      className={activeRange === label ? 'toolbar-button toolbar-button--active' : 'toolbar-button'}
      type="button"
      onClick={onClick}
    >
      {text ?? label}
    </button>
  )
}

function drawPatternOverlays(
  chart: Chart,
  visibleBars: StockBar[],
  signals: StockPatternSignal[],
  overlays: StockPatternOverlayLine[],
  density: KLineDensity,
) {
  const overlayChart = chart as unknown as {
    createOverlay: (overlay: Record<string, unknown>) => unknown
    removeOverlay: (filter: Record<string, unknown>) => unknown
  }
  overlayChart.removeOverlay({ groupId: 'pattern-signals' })
  ensureSignalBadgeOverlayRegistered()

  const visibleSignals = density === 'compact'
    ? chartSignalAnnotations(signals).slice(-5)
    : chartSignalAnnotations(signals).slice(-18)
  const textSize = density === 'compact' ? 10 : 11
  const barsByDate = new Map(visibleBars.map((bar) => [bar.time, bar]))

  visibleSignals.forEach((signal) => {
    const anchorPrice = signalAnchorPrice(signal, barsByDate)
    if (!anchorPrice) return
    const placement = signal.category === 'td_sequential' ? 'above' : 'below'
    overlayChart.createOverlay({
      name: 'signalBadge',
      groupId: 'pattern-signals',
      lock: true,
      points: [{ timestamp: Date.parse(signal.date), value: anchorPrice }],
      extendData: {
        color: colorForPolarity(signal.polarity),
        label: displaySignalLabel(signal),
        placement,
        showLabel: signal.category === 'td_sequential',
        textSize,
      } satisfies SignalBadgeOverlayData,
    })
  })

}

function signalAnchorPrice(signal: StockPatternSignal, barsByDate: Map<string, StockBar>): number | null {
  const bar = barsByDate.get(signal.date)
  if (!bar) return null
  if (signal.category === 'td_sequential') return bar.high
  return bar.low
}

function chartSignalAnnotations(signals: StockPatternSignal[]): StockPatternSignal[] {
  const annotations = signals.filter((signal) => {
    if (signal.signal_id === 'td_count') return [7, 8, 9].includes(tdCountValue(signal))
    if (isTdSetupSignal(signal)) return true
    return signal.category !== 'td_sequential'
  })
  const lastTdSetupDateById = new Map<string, number>()
  return annotations.filter((signal) => {
    if (!isTdSetupSignal(signal)) return true
    const timestamp = Date.parse(signal.date)
    const lastTimestamp = lastTdSetupDateById.get(signal.signal_id)
    lastTdSetupDateById.set(signal.signal_id, timestamp)
    if (lastTimestamp === undefined) return true
    const daysSinceLast = Math.abs(timestamp - lastTimestamp) / 86_400_000
    return daysSinceLast > 14
  })
}

function displaySignalLabel(signal: StockPatternSignal): string {
  if (signal.signal_id === 'td_buy_setup') return 'TD 買九'
  if (signal.signal_id === 'td_sell_setup') return 'TD 賣九'
  return signal.label
}

function isTdSetupSignal(signal: StockPatternSignal): boolean {
  return signal.signal_id === 'td_buy_setup' || signal.signal_id === 'td_sell_setup'
}

function tdCountValue(signal: StockPatternSignal): number {
  const match = signal.label.match(/\d+/)
  return match ? Number(match[0]) : 0
}

function colorForPolarity(polarity: string) {
  if (polarity === 'bullish') return '#ef5350'
  if (polarity === 'bearish') return '#26a69a'
  return '#f2d57e'
}
