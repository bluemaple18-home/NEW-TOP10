# UI-08：個股頁候補切換下拉

任務ID：`UI-08`
卡片類型｜派工對象：Frontend / Stock page navigation｜Codex
請讀：`docs/architecture/MOMENTUM_UI_SPEC.md`、`docs/tasks/2026-05-18_UI-07_reference_context_ui_polish.md`、`web/frontend/src/app/MarketDeskApp.tsx`、`web/frontend/src/features/stock-detail/StockDetailPanel.tsx`、`web/frontend/src/styles.css`
任務目的：個股頁不恢復左側候補欄，以免擠壓 K 線；改在個股頁右側新增本週候補下拉選單，讓使用者不必回本週候補頁也能切換其他股票。下拉選項必須使用目前全域投資設定篩出的候補池，因此會跟左側設定變動連動。
證據路徑：`web/frontend` build output、browser DOM 驗收紀錄。

## 狀態

`completed`

## 範圍

- 個股頁新增候補切換下拉。
- 下拉 options 來自 `weeklyDecision.stock_candidates`。
- 選取後直接更新 `selectedStockId`，刷新個股 detail / K 線 / reference / tabs。
- 保留「回本週候補」按鈕。

## 不做

- 不恢復個股頁左側欄。
- 不新增個股搜尋。
- 不新增持股追蹤。
- 不改 ranking / model / weekly decision service。
- 不讓下拉或候補資訊影響 K 線寬度。

## 驗收計劃

- `pnpm build` 通過。
- Browser 個股頁可看到右側「切換候補」下拉。
- 切換下拉後，個股標題、K 線 detail request、reference strip 跟著切換。
- 回本週候補後調整全域設定，再進個股頁，下拉候補數量與選項反映新設定。
- 桌機 / 手機無水平溢出。

## 實作紀錄

- `web/frontend/src/app/MarketDeskApp.tsx` 將目前 `weeklyDecision.stock_candidates` 與 `setSelectedStockId` 傳給個股頁。
- `web/frontend/src/features/stock-detail/StockDetailPanel.tsx` 新增 `CandidateSwitcher`，使用原生 `select` 顯示目前候補池，選取後直接切換個股。
- `web/frontend/src/styles.css` 新增下拉樣式；桌機位於個股工作台右側，手機自動換行，不建立 K 線左右欄。

## 驗收結果

- `pnpm build` 通過。
- Browser desktop：
  - 個股頁顯示「切換候補」下拉。
  - 下拉有 10 個本週候補選項。
  - 從 `3030 德律` 切到 `6451 訊芯-KY` 後，標題與 reference strip 更新，API 出現 `GET /api/stocks/6451/detail 200`。
  - K 線仍單欄，`gridTemplateColumns=2098.5px`，無水平溢出。
- Browser mobile：
  - viewport `390x900`。
  - 下拉寬度 `340px`，K 線寬度 `340px`。
  - `data-kline-density=compact`。
  - 無水平溢出。
- Diagnostics：
  - console 無 error。
  - select 已補 `id/name`，無 form field issue。
- 證據：
  - `artifacts/top10_ui08_stock_candidate_switcher_acceptance_2026-05-18.json`

## Review 派工卡

任務ID：`REVIEW-UI-08`
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-18_UI-08_stock_page_candidate_switcher.md`、`web/frontend/src/app/MarketDeskApp.tsx`、`web/frontend/src/features/stock-detail/StockDetailPanel.tsx`、`web/frontend/src/styles.css`
任務目的：review 個股頁候補切換下拉是否使用目前 weekly candidates state、能直接切換股票、會跟全域設定刷新連動，且沒有新增左側欄或擠壓 K 線。
證據路徑：`artifacts/top10_ui08_stock_candidate_switcher_acceptance_2026-05-18.json`
