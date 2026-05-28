# MARKET-CONTEXT-01：外部每日大盤追蹤研究與 TOP10new 開發建議

日期：2026-05-28
狀態：研究完成，尚未實作
目標讀者：另一台電腦接手開發的 Codex / 開發者

## 結論

這次研究的外部網站不是一個前端即時打 API 的 dashboard，而是：

1. Python 腳本每日抓取市場資料。
2. Jinja2 產生靜態 `index.html` 與 `latest_data.json`。
3. GitHub Actions 定時 commit/push。
4. GitHub Pages 托管靜態 dashboard。
5. WordPress 頁面用 iframe 嵌入 GitHub Pages。

TOP10new 不應照抄它的 WordPress iframe 或未驗證權重。真正值得吸收的是「市場情境層」：

- 大盤/籌碼/期權/國際流動性資料源。
- 每日 market context artifact。
- 多來源 fallback。
- 不直接改 production ranking 的 shadow regime score。
- 日報與前端可讀的市場背景解釋。

## 外部網站結構

入口頁：

- `https://tetsu811.com/daily-market-tracker/`

真正 dashboard iframe：

- `https://tetsu811.github.io/tw-stock-dashboard/`

公開 repo：

- `https://github.com/tetsu811/tw-stock-dashboard`

重要公開檔案：

- `data_fetcher.py`：資料抓取與 fallback。
- `generate.py`：整合資料、算戰略溫度計、渲染模板。
- `dashboard_template.html`：Jinja2 HTML 模板。
- `latest_data.json`：最新輸出資料 schema。
- `.github/workflows/daily_update.yml`：GitHub Actions 排程。

## Runtime Network / JS 研究結果

以 headless Chrome DevTools Protocol 監聽 runtime network 後，結果如下。

WordPress 外層頁載入：

- WordPress / Blocksy / Elementor CSS。
- Smush lazy-load。
- Google Analytics。
- Microsoft Clarity。
- Cloudflare RUM。
- iframe `https://tetsu811.github.io/tw-stock-dashboard/`。

iframe dashboard 本體載入：

- `index.html`
- `https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js`
- `favicon.ico`，回 404。

沒有看到 runtime 市場資料 API：

- 無 `fetch()` 抓市場資料。
- 無 `axios`。
- 無 `XMLHttpRequest` 抓市場資料。
- 市場資料已經預先渲染在 HTML 與 inline JS data 裡。

iframe JS 只做幾件事：

- Chart.js 畫 VIX、DXY、USD/JPY、US10Y、ON RRP 折線圖。
- `localStorage` 保存 dark/light theme。
- `window.parent.postMessage({type: "tw-dashboard-height", height})` 回傳高度給 WordPress iframe 外層。

## 已觀察到的外部資料內容

外部 dashboard 當時顯示資料日：

- `2026-05-25`
- 產生時間：`2026-05-25 21:31:59`
- 注意：研究日期是 `2026-05-28`，所以當時頁面不是最新交易日快照。

主要欄位包含：

- TAIEX 指數、漲跌點、漲跌幅、成交金額、成交金額變化。
- 台指期貨 TX：收盤、漲跌、期現貨價差、開高低收、成交量。
- 三大法人現貨：外資、投信、自營商買賣超。
- 三大法人台指期未平倉：外資、投信、自營。
- 期權觀測：微台/小台多空指標、Put/Call Ratio、Put OI、Call OI。
- VIX 恐慌指數。
- CNN Fear & Greed。
- Crypto Fear & Greed。
- 上市漲跌家數。
- 外資買超 / 賣超 Top 10。
- DXY、USD/JPY、US10Y、ON RRP。

## 外部 repo 的資料源

從公開 `data_fetcher.py` 抽到的主要資料源如下。

台灣市場：

- TWSE `FMTQIK`：加權指數與成交金額。
- TWSE `MI_INDEX`：每日收盤行情與漲跌家數。
- TWSE `BFI82U`：三大法人買賣超。
- TWSE `TWT38U` / `T86`：外資買賣超排行。
- TWSE `MI_MARGN`：融資融券 / 融資維持率估算。
- TWSE OpenAPI `openapi.twse.com.tw/v1/exchangeReport/...`：多個 fallback。
- TPEx 上櫃收盤/漲跌家數資料。
- TAIFEX `futDataDown`：台指期貨。
- TAIFEX `futContractsDateDown`：法人期貨未平倉。
- TAIFEX `pcRatio` / `callsAndPutsDate`：Put/Call Ratio。
- FinMind `api.finmindtrade.com/api/v4/data`：期貨法人、PCR、融資等 fallback。

國際與情緒：

- FRED CSV：VIX、US10Y、DXY 組成、ON RRP。
- NY Fed reverse repo API：ON RRP fallback。
- CNN DataViz Fear & Greed API。
- Alternative.me Crypto Fear & Greed API。
- Google Finance、Stooq、Investing、鉅亨等 fallback。

## 外部 repo 的產生流程

核心流程：

1. `data_fetcher.fetch_all_data(date_str)` 抓資料。
2. 合併 `history_cache.json`，補足 VIX / US10Y / DXY / JPY / ON RRP 走勢。
3. 組成 `data` dict。
4. `generate.prepare_template_data(data)` 格式化欄位與 chart data。
5. `generate.generate_dashboard(data)` 產出：
   - `index.html`
   - `archive/dashboard_YYYYMMDD.html`
   - `latest_data.json`
6. GitHub Actions 於台灣時間 18:00，週一到週五執行。
7. workflow commit `index.html`、`archive/`、`latest_data.json`、`history_cache.json`。

## 戰略溫度計邏輯

外部 repo 的 `generate.py` 有一個 7 維加權分數：

- CNN Fear & Greed：20%
- VIX：15%，反向，VIX 低分數高。
- 外資買賣超：20%，用 ±300 億作滿分區間。
- 小台多空比：15%，-100% 到 +100% 映射 0 到 100。
- PCR：10%，0.6 到 1.4 反向映射。
- 漲跌家數比：10%。
- ON RRP 變化：10%，下降視為資金流入、偏多。

重要限制：

- 這些權重看起來是 heuristic，不是回測產物。
- TOP10new 不可直接把它接到 production ranking。
- 可先做 `market_regime_shadow_score`，只進 artifact / 日報 / UI，不改 `risk_adjusted_score`。

## TOP10new 現況對照

TOP10new 已有：

- `app/data_fetcher.py`：TWSE/TPEX 日行情 async ETL。
- `app/trading/market_regime.py`：用 universe breadth、breakout ratio、avg RSI 做薄版 regime。
- `app/trading/ranking_policy.py`：`prediction_score + setup_score + quality_score - risk_penalty`。
- `app/agent_b_ranking.py`：LightGBM + calibrated probability + rule score。
- `app/reason_generator.py`：個股推薦理由。
- `scripts/run_daily.sh` / `scripts/run_automation.py`：daily pipeline。
- `artifacts/ranking_YYYY-MM-DD.csv`、daily report、Clawd publish payload 等 artifact。

TOP10new 缺口：

- 缺一份獨立 `market_context_YYYY-MM-DD.json`。
- 現行 `MarketRegimeService` 不讀外部大盤 / 期貨 / 期權 / 國際流動性資料。
- daily report 偏個股決策，市場背景敘事較薄。
- 前端可展示個股，但缺「今天市場是什麼天氣」的跨市場 context。

## 建議開發方向

### 第一階段：建立 Market Context Artifact

新增模組：

- `app/market_context_fetcher.py`
- 或若要維持 pipeline 分層，放在 `app/pipeline/market_context.py`

新增 artifact：

- `artifacts/market_context_YYYY-MM-DD.json`

建議 schema：

```json
{
  "schema_version": "market-context.v1",
  "trade_date": "YYYY-MM-DD",
  "generated_at": "ISO-8601",
  "sources": {
    "twse": {"status": "ok", "fallback_used": false},
    "taifex": {"status": "ok", "fallback_used": false},
    "fred": {"status": "warn", "fallback_used": true}
  },
  "taiex": {
    "close": 0,
    "change": 0,
    "change_pct": 0,
    "trade_value": 0,
    "trade_value_change_pct": null
  },
  "futures": {
    "tx_close": 0,
    "tx_change": 0,
    "tx_change_pct": 0,
    "basis": null
  },
  "institutional": {
    "foreign_net": null,
    "trust_net": null,
    "dealer_net": null
  },
  "futures_oi": {
    "foreign_oi": null,
    "foreign_change": null,
    "trust_oi": null,
    "dealer_oi": null
  },
  "options": {
    "pcr": null,
    "put_oi": null,
    "call_oi": null,
    "retail_mini_sentiment": null
  },
  "macro": {
    "vix": null,
    "dxy": null,
    "usd_jpy": null,
    "us10y": null,
    "on_rrp": null
  },
  "sentiment": {
    "cnn_fear_greed": null,
    "crypto_fear_greed": null
  },
  "shadow": {
    "market_regime_score": null,
    "market_regime_label": "UNKNOWN",
    "dimensions_used": 0
  }
}
```

### 第二階段：接到 Daily Pipeline，但不改 ranking 權重

Daily pipeline 後段新增步驟：

```bash
cd <repo-root>
uv run --with-requirements requirements.txt python -m app.market_context_fetcher --date YYYY-MM-DD
```

產物：

- `artifacts/market_context_YYYY-MM-DD.json`

接 daily report：

- `scripts/generate_daily_report.py` 讀 market context。
- 在報告開頭新增「市場背景」區塊。
- 不改 `ranking_YYYY-MM-DD.csv` 的排序欄位。

### 第三階段：MarketRegimeService 讀 context

目前 `app/trading/market_regime.py` 只靠 universe breadth。

建議改成雙層：

- `internal_regime`：現有 universe breadth / avg RSI / breakout ratio。
- `external_context`：TAIEX、法人、期貨、PCR、VIX、US10Y、ON RRP。

初期只用 external context 調整 `risk_multiplier` 的上限/下限：

- 明顯 risk-off 時，壓低最大倉位或降低出手數。
- 不直接改股票排序分數。
- 不修改模型 feature list。

### 第四階段：Shadow Backtest

新增研究腳本：

- `scripts/research_market_context_shadow.py`

驗證問題：

- 加入 market context 後，top10 5D/10D forward return 是否改善？
- 是否降低 drawdown？
- 是否提升 risk-off 日的空手/減碼品質？
- 是否造成過度保守，錯過大行情？

輸出：

- `artifacts/research/market_context_shadow_YYYY-MM-DD.json`
- `artifacts/research/market_context_shadow_YYYY-MM-DD.md`

## 不該做的事

不要抄 WordPress iframe：

- TOP10new 已有前端與 API，不應退回靜態 iframe。

不要直接抄戰略溫度計權重：

- 權重沒有回測支持。
- TOP10new 的 ranking policy 已明確要求權重變動要有證據。

不要把外部 scraper 全部搬進 production：

- KGI、Goodinfo、鉅亨、Investing 這類頁面抓取易碎。
- 優先官方 API，非官方來源只能 fallback，且要明確標示 source status。

不要讓 market context 污染模型訓練：

- 初期只做 artifact / report / regime shadow。
- 若未完成 walk-forward，不進 LightGBM feature list。

不要重蹈 token 洩漏：

- 外部 WordPress 頁會把 query token 帶進 Google Analytics `dl` 參數，也出現在 alternate link。
- TOP10new 若有 tokenized preview URL，要先 strip query 再載 analytics 或外部 script。

## 建議任務切片

### MARKET-CONTEXT-02：Market Context Fetcher

任務目的：

- 新增 market context 資料抓取器，輸出 `artifacts/market_context_YYYY-MM-DD.json`。

範圍：

- 先抓 TAIEX、法人現貨、台指期、PCR、VIX、US10Y。
- ON RRP、CNN、Crypto Fear & Greed 可第二輪。

驗收：

- 有 schema version。
- 有 per-source status。
- API 失敗時不整體 crash，欄位為 null 並記 warning。
- `uv run --with-requirements requirements.txt python -m app.market_context_fetcher --date YYYY-MM-DD` 可跑。

### MARKET-CONTEXT-03：Daily Report Market Background

任務目的：

- 把 market context 接進 daily report，生成可讀市場背景。

範圍：

- 不改 ranking。
- 不改 model。
- 不改 frontend。

驗收：

- daily report JSON 有 `market_context` 摘要。
- Markdown 報告有「市場背景」區。
- source status 會揭露資料缺漏。

### MARKET-CONTEXT-04：Market Regime Shadow Integration

任務目的：

- `MarketRegimeService` 可讀 market context，產生 shadow regime label。

範圍：

- 不直接改 `risk_adjusted_score`。
- 只輸出 shadow 欄位或 report。

驗收：

- ranking smoke 不因 market context 缺檔而失敗。
- 有缺檔 fallback：回到現有 internal regime。

### MARKET-CONTEXT-05：Shadow Backtest

任務目的：

- 驗證 market context 是否值得接 production policy。

範圍：

- 回測不同 risk_multiplier policy。
- 比較 production baseline。

驗收：

- 報告包含 hit rate、avg return、drawdown、turnover、risk-off day behavior。
- 若沒有正向證據，明確標記為 monitor-only。

## 開發注意事項

資料契約先行：

- 先建立 JSON schema 與最小 CLI。
- 再接 daily pipeline。
- 最後才碰 `MarketRegimeService`。

不要讓資料源失敗阻塞 ranking：

- market context 是輔助層，不能讓 TWSE/TAIFEX 某個非核心 endpoint 失敗就讓 daily ranking 失敗。
- 只有 schema 壞掉、artifact 寫不出來、或 production 已明確依賴的欄位缺失，才 fail。

命名建議：

- `market_context`
- `external_regime`
- `market_regime_shadow_score`
- `market_context_source_status`

避免命名：

- `strategy_thermometer`：太像抄外部 repo。
- `fear_greed_score`：容易誤導，以為單一情緒指標決定市場。

## 下一台電腦接手步驟

1. 先讀 `AGENTS.md`。
2. 讀 `.work/current/status.md`。
3. 讀 `.work/current/handoff.md`。
4. 讀本文件。
5. 執行：

```bash
cd <repo-root>
git status --short
git worktree list
```

6. 若不是獨立 worktree 或 branch，不要開始平行實作。
7. 從 `MARKET-CONTEXT-02` 開始，不要跳到 ranking 權重調整。

## 目前限制

- 這份研究沒有把外部 repo clone 到本 repo。
- 本次沒有修改 TOP10new production code。
- 本次沒有跑 TOP10new 測試，因為目前只建立研究與交接文件。
- 外部網站資料日是 `2026-05-25`，不代表 `2026-05-28` 最新市場狀態。
