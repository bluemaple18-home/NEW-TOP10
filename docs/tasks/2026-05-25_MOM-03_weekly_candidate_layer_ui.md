# MOM-03：本週候補分層 UI

任務ID：`MOM-03`

證據路徑：`artifacts/mom03_weekly_candidate_layer_ui_2026-05-25.json`

## 目的

讓本週候補頁清楚呈現「模型初選池」與「全域投資設定後可見候選」不是同一件事。

## 範圍

- `MarketSnapshotPanel` 顯示模型初選池、設定後候選、設定隱藏數量。
- `WeeklyCandidatesPanel` 顯示候選分層摘要。
- 設定後候選為 0 時顯示空狀態與 settings effect 原因。
- 個股頁左側候補共用同一個分層摘要。

## 不做

- 不改 K 線工作台。
- 不改個股詳情頁主要版面。
- 不改 ranking/model/API contract。
- 不接 ETF ranking。

## 驗收

- stocks 模式可看到模型池 10、設定後 10、隱藏 0。
- etfs 模式可看到模型池 10、設定後 0、隱藏 10，且有空狀態原因。
- 無 horizontal overflow / console diagnostics。

## 驗證紀錄

- `pnpm --dir web/frontend build` 通過。
- `node scripts/verify_frontend_smoke.mjs` 通過，確認候補、個股頁、K 線 30D 與 trade rail 仍可載入。
- `node /private/tmp/top10_mom03_acceptance.mjs` 通過，輸出 `artifacts/mom03_weekly_candidate_layer_ui_2026-05-25.json`。

## 證據摘要

- stocks：`模型初選池10 檔`、`設定後候選10 檔`、`設定隱藏0 檔`、候選列 `10`。
- etfs：`模型初選池10 檔`、`設定後候選0 檔`、`設定隱藏10 檔`、空狀態原因含「目前設定只看 ETF」。
- `no_overflow=true`、`no_diagnostics=true`。

## Review 結論

- `REVIEW-MOM-03` 結論：未發現阻塞問題，可放行。
- 已確認本週候補頁與個股頁左側候補共用候選分層摘要。
- 已確認沒有修改 `KLineWorkbench` 或 `StockDetailPanel` 主版面。
- 剩餘小風險：`top10_ops02_frontend_smoke_2026-05-19.json` 檔名仍是舊日期且無 generated timestamp；MOM-03 自己的 acceptance JSON 已覆蓋分層 UI。

## Review 派工卡

任務ID：REVIEW-MOM-03
卡片類型｜派工對象：Review / UI Contract｜另一個 AI
請讀：`docs/tasks/2026-05-25_MOM-03_weekly_candidate_layer_ui.md`、`web/frontend/src/features/market/MarketSnapshotPanel.tsx`、`web/frontend/src/features/weekly-candidates/WeeklyCandidatesPanel.tsx`、`web/frontend/src/app/MarketDeskApp.tsx`、`web/frontend/src/styles.css`
任務目的：檢查本週候補 UI 是否清楚區分模型初選池與設定後可見候選，且沒有影響 K 線或個股頁主版面
證據路徑：`artifacts/mom03_weekly_candidate_layer_ui_2026-05-25.json`
