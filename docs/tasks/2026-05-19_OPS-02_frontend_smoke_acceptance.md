# OPS-02：前端資料載入 Smoke 驗收

任務ID：`OPS-02`
卡片類型：`Ops / Browser Acceptance`
證據路徑：`artifacts/top10_ops02_frontend_smoke_2026-05-19.json`、`artifacts/top10_ops02_frontend_smoke_2026-05-19.png`

## 背景

使用者曾看到「前端骨架出來，但資料沒載入」的狀態。OPS-01 已統一本地 API / Vite port 與 healthcheck；本卡補一個可重跑的 headless browser smoke，確認前端真的把 API 資料接進畫面。

## 範圍

- 新增 `scripts/verify_frontend_smoke.mjs`。
- 使用本機 Chrome CDP，不引入新 npm dependency。
- 驗證：
  - 本週候補列表有資料。
  - 個股頁 tab 可進入且 title 有股票資訊。
  - K 線工作台預設 30D 資料載入。
  - K 線 canvas 存在且高度不是空骨架。
  - 交易計畫右側 rail 至少有 3 個 badge。
  - 無水平 overflow。
  - 無 console / network error。

## 非範圍

- 不改 ranking/model/API contract。
- 不改 UI layout 與 K 線 overlay 規則。
- 不新增 Playwright / Puppeteer dependency。

## 驗證命令

```bash
node scripts/verify_frontend_smoke.mjs
```

## 執行紀錄

- Review 結論：未發現阻塞問題；確認 smoke 不是只驗靜態骨架，也沒有新增 Playwright / Puppeteer / chrome-remote-interface dependency。
- Review 驗證缺口：review 端因本地 dev server 沒開，無法現場重跑完整 smoke；此缺口轉入 `OPS-04` 補清楚的 preflight / server-not-ready 診斷。
- `node --check scripts/verify_frontend_smoke.mjs` 通過。
- `pnpm --dir web/frontend build` 通過。
- `bash scripts/verify_local_dev_health.sh` 通過：
  - `api.health status=200`
  - `api.weekly_candidates status=200`
  - `api.stock_detail status=200`
  - `frontend status=200`
- `node scripts/verify_frontend_smoke.mjs` 通過：
  - `candidateCount=10`
  - `selectedStockTitle=3030 德律`
  - `kline.activeRange=30D`
  - `kline.windowBars=30`
  - `canvasCount=18`
  - `tradeRailMarkCount=3`
  - `no_browser_diagnostics=true`
  - `no_horizontal_overflow=true`

## Review 交接

任務ID：REVIEW-OPS-02
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-19_OPS-02_frontend_smoke_acceptance.md`、`scripts/verify_frontend_smoke.mjs`、`README.md`
任務目的：review 前端 smoke 是否真的驗到資料載入，而不是只驗靜態骨架；確認沒有新增不必要 dependency 或改 production 行為。
證據路徑：`artifacts/top10_ops02_frontend_smoke_2026-05-19.json`、`artifacts/top10_ops02_frontend_smoke_2026-05-19.png`
