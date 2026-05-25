# UI-13：K 線 overlay 可讀性修正

任務ID：`UI-13`
卡片類型｜派工對象：Frontend / KLine overlay readability｜Codex
請讀：`web/frontend/src/charts/KLineWorkbench.tsx`、`web/frontend/src/styles.css`
任務目的：參考舊專案 KLineCharts overlay 畫法，改善新專案 TD 九轉、K 線型態與交易計畫標註擁擠問題；TD 只顯示 7 / 8 / 9，型態在圖上只留 marker 不顯示文字，交易計畫線留在 K 線上但文案與價位 badge 移到右側外欄。
證據路徑：`artifacts/top10_ui13_kline_overlay_readability_acceptance_2026-05-19.json`、`artifacts/top10_ui13_visual_evidence_kline_trade_badges_2026-05-19.png`

## 狀態

`completed`

## 範圍

- 移除新專案自訂 `patternMarker` overlay。
- 保留舊專案「用 KLineCharts overlay 畫 icon / label，不找 SVG/PNG 資產」的做法。
- 註冊可控 placement 的 `signalBadge` overlay，用 polygon 畫 icon。
- TD 訊號固定在 K 線上方並保留文字；K 線型態在圖上只留 marker，不顯示「十字星 / 多方吞噬 / 蜻蜓十字」等文字。
- TD 計數只顯示 `TD 7`、`TD 8` 與 `TD 買九 / TD 賣九`。
- 同方向 TD 九若在 14 天內連續出現，只保留該段第一個九，避免整排文字壓在 K 線上方。
- 增加 K 線圖高度，並提高 candle pane 可用高度。
- 交易計畫的進場區間、停損、停利目標線保留在 K 線上；右側外欄顯示對應 badge 並用 connector 對齊價格線。
- 關閉 KLineCharts 內建最新價 price mark，避免右軸價格膠囊壓在 K 線區。

## 不做

- 不找 SVG / PNG icon 資產。
- 不改後端型態計算公式。
- 不改 ranking / model / API contract。
- 不把 4 / 5 / 6 顯示回圖上。
- 不把交易計畫文案或價位 badge 畫進 K 線 canvas 內。

## 驗收結果

- `pnpm build` 通過。
- `py_compile` 通過。
- Browser desktop：
  - `weekly-candidates` / `stock detail` API 均為 200。
  - K 線寬度 `1703.015625px`。
  - K 線高度 `900px`。
  - `30D` / `3M` / `6M` / `1Y` / `全部` 按鈕皆會更新 `activeRange`。
  - 3030 目前本地日 K 只有 39 根，所以 `3M` / `6M` / `1Y` / `全部` 會顯示同一個 39 根資料窗，這是資料量限制，不是 range 按鈕未觸發。
  - `density=full`。
  - 無水平 overflow。
- TD overlay 驗收：
  - TD overlay 只由目前報表天數內的 `StockBar.time` 對應訊號動態產生，不使用固定日期清單。
  - 不再渲染 `TD 4`、`TD 5`、`TD 6`。
  - `td_count` 嚴格只允許 `TD 7`、`TD 8`、`TD 9`，不使用 `>= 7` 寬鬆判斷。
  - 連續 `TD 賣九` 已壓成單一段落標註。
- 型態 overlay 驗收：
  - K 線型態在圖上只保留 marker，不顯示型態名稱文字。
  - 已移除 `simpleTag` 型態文字 overlay，避免 `多方吞噬 / 十字星 / 蜻蜓十字` 文字進入 canvas。
  - 型態完整名稱與說明保留在下方 `K 線案例` 區塊。
- 交易計畫 overlay 驗收：
  - 進場區間、停損、停利目標線仍畫在 K 線上，可與 K 棒比對。
  - `進場區間 / 停損 / 停利目標` 文案與數字 badge 顯示在右側外欄，不進 K 線 canvas。
  - 右側 badge 使用 KLineCharts `convertToPixel()` 依真實價格 y 座標定位，並以 connector 對齊線位。
- Range 切換驗收：
  - `30D` / `3M` / `6M` / `1Y` / `全部` 切換後，訊號與 W/M overlay 只允許畫在目前可見 K 棒日期內。
  - 若訊號找不到目前可見 K 棒，不使用 signal price fallback 強行畫到圖上。
  - 驗收結果：所有 range 的 `signalsOutsideWindowAfterFilter=0`、`overlayPointsOutsideWindowAfterFilter=0`。
- Placement 驗收：
  - TD 使用 `bar.high` 錨點，上方標註。
  - candlestick 型態使用 `bar.low` 錨點，只畫 marker，不畫文字。
  - 截圖確認交易計畫線在 K 線上、文字 badge 在右側外欄。

## Review 派工卡

任務ID：`REVIEW-UI-13`
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-19_UI-13_kline_overlay_readability.md`、`web/frontend/src/charts/KLineWorkbench.tsx`、`web/frontend/src/styles.css`
任務目的：review 新專案是否依舊專案 handoff 使用 KLineCharts overlay 畫 icon / label 而非資產檔，TD 是否只顯示 7/8/9 且在上方，K 線型態是否只留 marker 不顯示文字，交易計畫線是否仍在 K 線上且文字/價位 badge 是否移到右側外欄並對齊線位。
證據路徑：`artifacts/top10_ui13_kline_overlay_readability_acceptance_2026-05-19.json`、`artifacts/top10_ui13_visual_evidence_kline_trade_badges_2026-05-19.png`

## Review Fix

- 修正 `[P1]`：移除 `simpleTag` 型態文字 overlay；UI-13 圖上只保留 `signalBadge` marker，型態文字留在下方案例區。
- 修正 `[P2]`：`td_count` 從 `>= 7` 改為嚴格 `[7, 8, 9]`。
- 補新證據圖：`artifacts/top10_ui13_visual_evidence_kline_trade_badges_2026-05-19.png`，畫面同時包含 K 線區、交易線與右側 badge。
- Browser 量測確認：`stageVisibleInViewport=true`、`railIsRightOfChart=true`、`markCount=3`、三個 connector 皆存在。
