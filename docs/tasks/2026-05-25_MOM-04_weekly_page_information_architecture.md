# MOM-04：本週候補頁資訊架構整理

任務ID：`MOM-04`

證據路徑：`artifacts/mom04_weekly_page_ia_2026-05-25.json`

## 目的

把本週候補頁從「設定卡 + 候補列表」整理成更清楚的產品工作區：上方是全域投資設定列，下方是市場/候選摘要與候補清單。

## 範圍

- 本週候補頁設定面板改為橫向設定列。
- 市場摘要與候補清單同層並排呈現。
- 保留 MOM-03 的模型池 / 設定後 / 隱藏摘要。
- 保留手機斷點單欄。

## 不做

- 不改 K 線。
- 不改個股頁主版面。
- 不改 API / ranking / model。
- 不接 ETF ranking。

## 驗收

- desktop：設定列在上方，市場摘要與候補清單並排，無 horizontal overflow。
- mobile：設定列與候補內容單欄，文字不溢出。
- K 線 smoke 仍通過。

## 驗證紀錄

- `pnpm --dir web/frontend build` 通過。
- `node /private/tmp/top10_mom04_acceptance.mjs` 通過，輸出 `artifacts/mom04_weekly_page_ia_2026-05-25.json`。
- `node scripts/verify_frontend_smoke.mjs` 通過，K 線 30D、trade rail、個股頁仍可載入。

## 證據摘要

- desktop：設定列寬度 `1576`，decision grid 為雙欄 `718.516px 843.484px`，候選列 `10`。
- mobile：設定列寬度 `374`，decision grid 為單欄 `374px`，候選列 `10`。
- `no_overflow=true`、`no_diagnostics=true`。

## Review 派工卡

任務ID：REVIEW-MOM-04
卡片類型｜派工對象：Review / UI Layout｜另一個 AI
請讀：`docs/tasks/2026-05-25_MOM-04_weekly_page_information_architecture.md`、`web/frontend/src/app/MarketDeskApp.tsx`、`web/frontend/src/styles.css`
任務目的：檢查本週候補頁資訊架構是否更清楚，且沒有影響 K 線、個股頁主版面或 API 行為
證據路徑：`artifacts/mom04_weekly_page_ia_2026-05-25.json`、`artifacts/top10_ops02_frontend_smoke_2026-05-19.json`
