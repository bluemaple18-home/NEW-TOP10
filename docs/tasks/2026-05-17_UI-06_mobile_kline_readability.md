# UI-06：手機版 K 線 readability

任務ID：`UI-06`
卡片類型｜派工對象：Frontend / K 線手機版可讀性｜Codex
請讀：`docs/architecture/MOMENTUM_UI_SPEC.md`、`docs/tasks/2026-05-16_UI-03_kline_range_controls.md`、`docs/tasks/2026-05-16_UI-04_kline_trade_overlay.md`、`docs/tasks/2026-05-17_UI-05_stock_detail_analysis_tabs.md`、`web/frontend/src/charts/KLineWorkbench.tsx`、`web/frontend/src/styles.css`
任務目的：手機版 K 線不要把桌機版完整指標與訊號標籤全部塞進窄畫面，需保留操作核心並降低文字重疊。
證據路徑：`web/frontend` build output、browser screenshot、console/network/DOM 驗收紀錄。

## 狀態

`completed`

## 背景

`UI-05` 已確認 tabs 不再造成水平溢出，但 mobile screenshot 顯示 K 線圖內部仍偏擁擠。根因不是下方 tabs，而是手機寬度下仍顯示桌機版完整指標與大量型態標籤。

## 範圍

- 手機 / 窄寬 K 線進入 compact mode。
- compact mode 只保留：
  - K 線主圖。
  - 成交量。
  - 交易計畫 overlay。
  - 少量近期型態標記。
- compact mode 不顯示 MACD / KDJ panes。
- compact mode 限制型態標籤數量，避免文字互相覆蓋。
- 桌機版維持既有完整 K 線工作台。
- `30D` 仍代表最近 30 根有開盤紀錄日 K。

## 不做

- 不改 K 線資料來源。
- 不改交易計畫演算法。
- 不新增搜尋、持股追蹤或即時價。
- 不改個股頁 tabs 結構。

## 驗收計劃

- `pnpm build` 通過。
- Browser diagnostics 無 error / warning / failed request。
- Desktop viewport：
  - `data-kline-density="full"`。
  - `30D windowBars=30`。
  - 交易 overlay 仍為 ready。
- Mobile viewport：
  - `data-kline-density="compact"`。
  - `30D windowBars=30`。
  - 交易 overlay 仍為 ready。
  - 無水平溢出。
  - K 線圖高度與 tabs 不互相遮擋。
- Desktop / mobile 各截圖一張。

## 已知風險

- 本卡降低手機版資訊密度，不等於補完整手機版操作手勢設計。
- compact mode 仍保留交易 overlay 與少量型態標記；若未來要做到極簡手機圖，需另開卡處理 overlay label 排版。

## 實作紀錄

- `web/frontend/src/charts/KLineWorkbench.tsx` 新增 `data-kline-density="full|compact"`。
- K 線容器寬度 `<= 520px` 時切 compact mode，重新建立圖表 layout。
- full mode 保留桌機版 `K 線 + VOL + MACD + KDJ` 與 MA/BOLL。
- compact mode 改成 `K 線 + VOL`，不建立 MACD / KDJ / MA / BOLL。
- compact mode 關閉 candle / indicator tooltip，避免手機上方 OHLC 與指標文字重疊。
- compact mode 限制型態標記數量：signals 最多近期 5 個，overlay line 最多近期 2 組。
- `web/frontend/src/styles.css` 讓 compact chart 高度固定為 `500px`，並縮小手機提示標籤。

## 驗收結果

- `pnpm build` 通過。
- Browser diagnostics：desktop / mobile console、page error、network failure 皆無異常。
- Desktop viewport `1920x1080`：
  - `data-kline-density="full"`。
  - `activeRange=30D`。
  - `windowBars=30`、`visibleBars=30`。
  - `tradeOverlay=ready`。
  - 無水平溢出。
- Mobile viewport `390x900`：
  - `data-kline-density="compact"`。
  - `activeRange=30D`。
  - `windowBars=30`、`visibleBars=26`。
  - `tradeOverlay=ready`。
  - chart 高度 `500px`，tabs 在 chart 下方。
  - 無水平溢出。
- 證據：
  - `artifacts/top10_ui06_kline_readability_acceptance_2026-05-17.json`
  - `artifacts/top10_ui06_kline_full_desktop_2026-05-17.png`
  - `artifacts/top10_ui06_kline_compact_mobile_2026-05-17.png`

## Review 修正

- 修正 `P2`：chart density、data、overlay 或 trade plan refresh 時，不再固定重灌 `30D`；目前使用 `activeRangeRef` 保留使用者選擇，chart 重建後用目前 range 重新載入。
- 修正 `P3`：compact breakpoint 統一為 `COMPACT_KLINE_WIDTH = 520`，不再用 `window.innerWidth > 640` 作初始判斷；density 一律由容器寬度判定。
- 補 regression 驗收：
  - 起始 viewport `620px`，density 為 `full`。
  - 使用者點 `3M`。
  - resize 到 `390px`，density 變 `compact`，range 仍為 `3M`。
  - resize 回 `620px`，density 回 `full`，range 仍為 `3M`。
  - 驗收結果：`rangePersisted=true`、`barsPersisted=true`、`didNotResetTo30D=true`。
- Review 修正證據：
  - `artifacts/top10_ui06_range_density_regression_2026-05-17.json`
  - `artifacts/top10_ui06_range_density_regression_2026-05-17.png`
