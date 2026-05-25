#!/usr/bin/env node
import { mkdir, writeFile } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { tmpdir } from 'node:os'

const chromePath = process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const frontendUrl = process.env.TOP10_FRONTEND_URL ?? `http://127.0.0.1:${process.env.TOP10_FRONTEND_PORT ?? '5173'}/`
const outputDir = process.env.TOP10_ARTIFACT_DIR ?? '/Users/matt/TOP10new/artifacts'
const evidenceJson = `${outputDir}/top10_ui14_stock_switching_flow_2026-05-20.json`
const screenshot = `${outputDir}/top10_ui14_stock_switching_flow_2026-05-20.png`
const userDataDir = process.env.TOP10_CHROME_PROFILE ?? `${tmpdir()}/top10-ui14-chrome-profile-${Date.now()}-${Math.round(Math.random() * 10000)}`
const port = Number(process.env.TOP10_CDP_PORT ?? String(9560 + Math.floor(Math.random() * 200)))

await mkdir(outputDir, { recursive: true })

let chrome = null
let chromeState = { exited: false, exitCode: null, stderr: '' }
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function assertFrontendReady() {
  try {
    const response = await fetch(frontendUrl)
    if (!response.ok) throw new Error(`status=${response.status}`)
  } catch (error) {
    throw new Error(`FRONTEND_NOT_READY url=${frontendUrl} hint="請先執行 bash scripts/start_ui.sh，或確認 TOP10_FRONTEND_PORT / VITE_API_BASE_URL。" cause="${error instanceof Error ? error.message : String(error)}"`)
  }
}

function startChrome() {
  chromeState = { exited: false, exitCode: null, stderr: '' }
  chrome = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    `--user-data-dir=${userDataDir}`,
    `--remote-debugging-port=${port}`,
    'about:blank',
  ], { stdio: ['ignore', 'pipe', 'pipe'] })

  chrome.stderr?.on('data', (chunk) => {
    chromeState.stderr += chunk.toString()
  })
  chrome.on('exit', (code) => {
    chromeState.exited = true
    chromeState.exitCode = code
  })
}

async function waitForJsonVersion() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (chromeState.exited) {
      throw new Error(`Chrome exited before CDP ready code=${chromeState.exitCode} stderr=${chromeState.stderr.slice(-1200)}`)
    }
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`)
      if (response.ok) return response.json()
    } catch {
      await sleep(100)
    }
  }
  throw new Error('Chrome CDP endpoint not ready')
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl)
  let nextId = 1
  const callbacks = new Map()
  const events = []

  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && callbacks.has(message.id)) {
      const { resolve, reject } = callbacks.get(message.id)
      callbacks.delete(message.id)
      if (message.error) reject(new Error(message.error.message))
      else resolve(message.result ?? {})
      return
    }
    if (message.method) events.push(message)
  })

  const ready = new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })

  const send = async (method, params = {}) => {
    await ready
    const id = nextId
    nextId += 1
    ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => callbacks.set(id, { resolve, reject }))
  }

  return { events, send, ws }
}

async function createPage() {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })
  if (!response.ok) throw new Error(`create page failed: ${response.status}`)
  return response.json()
}

async function waitForExpression(cdp, expression, timeout = 18000) {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    const result = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (result.result?.value) return result.result.value
    await sleep(250)
  }
  throw new Error(`waitForExpression timeout: ${expression}`)
}

async function evalJson(cdp, expression) {
  const result = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text ?? result.exceptionDetails.exception?.description ?? 'Runtime exception')
  }
  return result.result?.value
}

async function capture(cdp, path) {
  const result = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  await writeFile(path, Buffer.from(result.data, 'base64'))
}

function diagnostics(events) {
  return events
    .filter((event) => {
      if (event.method === 'Runtime.exceptionThrown') return true
      if (event.method === 'Runtime.consoleAPICalled') return ['error', 'warning'].includes(event.params?.type)
      if (event.method === 'Log.entryAdded') return ['error', 'warning'].includes(event.params?.entry?.level)
      if (event.method === 'Network.loadingFailed') return true
      if (event.method === 'Network.responseReceived') return event.params?.response?.status >= 400
      return false
    })
    .map((event) => ({
      method: event.method,
      type: event.params?.type ?? event.params?.entry?.level ?? null,
      text: event.params?.entry?.text ?? event.params?.exceptionDetails?.text ?? null,
      url: event.params?.response?.url ?? event.params?.request?.url ?? null,
      status: event.params?.response?.status ?? null,
      errorText: event.params?.errorText ?? null,
    }))
}

const pageStateExpression = `(() => {
  const root = document.documentElement
  const body = document.body
  const candidateRows = Array.from(document.querySelectorAll('.candidate-row'))
  const stockTitle = document.querySelector('.stock-workbench-panel h2')?.textContent?.trim() ?? null
  const activeRows = candidateRows.filter((row) => row.getAttribute('aria-pressed') === 'true').map((row) => row.textContent?.trim() ?? '')
  const workbench = document.querySelector('.kline-workbench')
  return {
    candidateCount: candidateRows.length,
    firstCandidateText: candidateRows[0]?.textContent?.trim() ?? null,
    secondCandidateText: candidateRows[1]?.textContent?.trim() ?? null,
    stockTitle,
    activeRows,
    kline: {
      activeRange: workbench?.dataset.activeRange ?? null,
      windowBars: workbench?.dataset.activeWindowBars ?? null,
      visibleBars: workbench?.dataset.activeVisibleBars ?? null,
      tradeOverlay: workbench?.dataset.tradeOverlay ?? null,
    },
    canvasCount: document.querySelectorAll('.kline-chart canvas').length,
    tradeRailMarkCount: document.querySelectorAll('.kline-trade-plan-rail__mark').length,
    leftRailVisible: Boolean(document.querySelector('.left-rail')),
    documentOverflow: Math.max(root.scrollWidth, body.scrollWidth) > window.innerWidth + 1,
  }
})()`

function stockIdFromText(text) {
  return text?.match(/\b\d{4}\b/)?.[0] ?? null
}

try {
  await assertFrontendReady()
  startChrome()
  await waitForJsonVersion()
  const page = await createPage()
  const cdp = connect(page.webSocketDebuggerUrl)
  await cdp.send('Runtime.enable')
  await cdp.send('Page.enable')
  await cdp.send('Network.enable')
  await cdp.send('Log.enable')
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false })

  await cdp.send('Page.navigate', { url: frontendUrl })
  await waitForExpression(cdp, `document.querySelectorAll('.candidate-row').length >= 2`)
  const weeklyState = await evalJson(cdp, pageStateExpression)
  const firstStockId = stockIdFromText(weeklyState.firstCandidateText)
  const secondStockId = stockIdFromText(weeklyState.secondCandidateText)
  if (!firstStockId || !secondStockId || firstStockId === secondStockId) {
    throw new Error(`candidate ids invalid first=${firstStockId} second=${secondStockId}`)
  }

  await evalJson(cdp, `document.querySelectorAll('.candidate-row')[0]?.click(); true`)
  await waitForExpression(cdp, `document.querySelector('.stock-workbench-panel h2')?.textContent?.includes('${firstStockId}')`)
  await waitForExpression(cdp, `document.querySelector('.kline-workbench')?.dataset.activeWindowBars === '30'`)
  const afterFirst = await evalJson(cdp, pageStateExpression)

  await evalJson(cdp, `document.querySelectorAll('.left-rail .candidate-row')[1]?.click(); true`)
  await waitForExpression(cdp, `document.querySelector('.stock-workbench-panel h2')?.textContent?.includes('${secondStockId}')`)
  await waitForExpression(cdp, `document.querySelector('.kline-workbench')?.dataset.activeWindowBars === '30'`)
  await waitForExpression(cdp, `document.querySelectorAll('.left-rail .candidate-row')[1]?.getAttribute('aria-pressed') === 'true'`)
  await sleep(500)
  const afterSecond = await evalJson(cdp, pageStateExpression)

  await capture(cdp, screenshot)
  const eventDiagnostics = diagnostics(cdp.events)
  const evidence = {
    status: 'passed',
    frontendUrl,
    screenshot,
    ids: { firstStockId, secondStockId },
    states: { weekly: weeklyState, afterFirst, afterSecond },
    checks: {
      weekly_has_candidates: weeklyState.candidateCount >= 2,
      first_click_opened_stock_page: afterFirst.stockTitle?.includes(firstStockId) ?? false,
      left_rail_visible: afterFirst.leftRailVisible && afterSecond.leftRailVisible,
      second_click_changed_stock: afterSecond.stockTitle?.includes(secondStockId) && afterSecond.stockTitle !== afterFirst.stockTitle,
      second_candidate_active: afterSecond.activeRows.some((text) => text.includes(secondStockId)),
      kline_remains_loaded: afterSecond.kline.windowBars === '30' && afterSecond.canvasCount > 0,
      trade_rail_remains_loaded: afterSecond.tradeRailMarkCount >= 3,
      no_horizontal_overflow: !afterSecond.documentOverflow,
      no_browser_diagnostics: eventDiagnostics.length === 0,
    },
    diagnostics: eventDiagnostics,
  }

  await writeFile(evidenceJson, `${JSON.stringify(evidence, null, 2)}\n`)
  console.log(JSON.stringify({ ...evidence, evidenceJson }, null, 2))
  cdp.ws.close()
} finally {
  chrome?.kill()
}
