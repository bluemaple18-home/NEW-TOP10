# UI-04：K 線操作 overlay

任務ID：`UI-04`
卡片類型｜派工對象：Frontend / K 線操作視覺化｜Codex
請讀：`docs/tasks/2026-05-16_UI-03_kline_range_controls.md`、`docs/architecture/MOMENTUM_UI_SPEC.md`、`docs/KLINE_UI_DECISION.md`、`web/frontend/src/charts/KLineWorkbench.tsx`、`web/frontend/src/features/stock-detail/StockDetailPanel.tsx`
任務目的：把交易計畫的進場區間、停損、停利畫到 K 線圖上，讓個股頁能直接從圖上理解「怎麼買、怎麼等、怎麼跑」。
證據路徑：`web/frontend` build output、browser screenshot、console/network 驗收紀錄。

## 狀態

`completed`

## 背景

`UI-03` 已修好 K 線區間切換，尤其 `30D` 現在是最近 30 根有開盤紀錄的日 K。下一個主要缺口是 `MOMENTUM_UI_SPEC.md` 要求 K 線互動區包含：

- 買點區。
- 停損線。
- 停利區。
- 型態標記。

目前型態標記已有初步 Show Case overlay；本卡先補交易計畫 overlay。

## 範圍

- 從 `stockDetail.trade_plan` 取值：
  - `entry_low`
  - `entry_high`
  - `stop_loss`
  - `target_price`
- 在 K 線主圖上畫：
  - 進場區間帶。
  - 停損線。
  - 目標 / 停利線。
- overlay 不可影響 K 線寬度與布局。
- overlay 必須跟著 `30D / 3M / 6M / 1Y / 全部` 區間切換重畫。
- 缺任一價位時不可讓圖表 crash。

## 不做

- 不新增盤中即時價。
- 不新增個股搜尋。
- 不新增持有股追蹤。
- 不做 ETF 成分 / 曝險分析。
- 不改交易計畫演算法。
- 不把操作計畫做成右側欄位壓縮 K 線。

## 驗收計劃

- `pnpm build` 通過。
- Browser console 無 error / warn。
- `/api/stocks/1110/detail?limit=1200` 回 200。
- 個股頁 K 線區塊存在交易 overlay：
  - `data-trade-overlay="ready"`。
  - `data-entry-low` / `data-entry-high` / `data-stop-loss` / `data-target-price` 有值。
- 切換 `3M -> 30D -> 全部 -> 30D` 後：
  - `30D` 仍為 `windowBars 30 / visibleBars 30`。
  - trade overlay 仍為 ready。
- 截圖留在 `artifacts/`。

## 已知風險

- 本卡只補操作 overlay，不處理「下方詳細分析 tabs」。
- 本卡只視覺化既有 trade plan，不檢查 stop/target 演算法品質。

## 實作紀錄

- `web/frontend/src/features/stock-detail/StockDetailPanel.tsx` 將 `stockDetail.trade_plan` 的進場區間、停損、目標價傳入 K 線工作台。
- `web/frontend/src/charts/KLineWorkbench.tsx` 註冊 `tradePlanOverlay`，在主圖畫出進場區間帶、停損線、目標線與價位標籤。
- overlay 跟著 `30D / 3M / 6M / 1Y / 全部` 重設資料視窗後重畫。
- K 線根節點補上 `data-trade-overlay`、`data-entry-low`、`data-entry-high`、`data-stop-loss`、`data-target-price`，供 browser 驗收讀取。

## 驗收結果

- `pnpm build` 通過。
- Browser console 無 error / warn。
- `/api/stocks/1110/detail?limit=1200` 回 200。
- Browser 驗收狀態：
  - 初始：`activeRange=30D`、`windowBars=30`、`visibleBars=30`、`data-trade-overlay=ready`。
  - `3M`：`windowBars=60`、`visibleBars=59`、`data-trade-overlay=ready`。
  - 回 `30D`：`windowBars=30`、`visibleBars=30`、`data-trade-overlay=ready`。
  - `全部`：`windowBars=300`、`visibleBars=291`、`data-trade-overlay=ready`。
  - 再回 `30D`：`windowBars=30`、`visibleBars=30`、`data-trade-overlay=ready`。
- 驗收截圖：`artifacts/top10_kline_trade_overlay_2026-05-16.png`。
