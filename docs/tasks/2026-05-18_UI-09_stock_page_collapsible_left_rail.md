# UI-09：個股頁可收合左側欄

任務ID：`UI-09`
卡片類型｜派工對象：Frontend / Stock page layout｜Codex
請讀：`docs/architecture/MOMENTUM_UI_SPEC.md`、`docs/tasks/2026-05-18_UI-08_stock_page_candidate_switcher.md`、`web/frontend/src/app/MarketDeskApp.tsx`、`web/frontend/src/features/settings/GlobalSettingsPanel.tsx`、`web/frontend/src/styles.css`
任務目的：個股頁加入可收合左側欄，讓使用者在個股頁也能調整全域投資設定與切換本週候補；收合後 K 線仍能撐滿主要工作區。
證據路徑：`web/frontend` build output、browser DOM 驗收紀錄。

## 狀態

`completed`

## 範圍

- 個股頁使用既有 `workspace-grid / left-rail / rail-collapsed-card` layout。
- 左側欄展開時顯示全域投資設定與本週候補清單。
- 左側欄收合時只保留窄 rail，不把候補資訊放在 K 線右側。
- 個股頁右上候補下拉保留，作為快速切換。

## 不做

- 不新增個股搜尋。
- 不新增持股追蹤。
- 不改 ranking / model / weekly decision service。
- 不把左側欄變成固定不可收合。

## 驗收計劃

- `pnpm build` 通過。
- Browser 個股頁左側欄可見，含全域設定與候補清單。
- 點收合後主區變寬，K 線仍單欄。
- 點展開後可從左側候補清單切換個股。
- 左側全域設定變更後，候補清單與右上下拉使用刷新後的候補 state。
- 桌機 / 手機無水平溢出。

## 實作紀錄

- `web/frontend/src/app/MarketDeskApp.tsx`：個股頁改用既有 `workspace-grid / left-rail` 結構，新增 `stockRailCollapsed` state。
- 左側欄展開時直接重用共用元件：
  - `GlobalSettingsPanel`
  - `WeeklyCandidatesPanel`
- 左側欄收合時使用既有 `rail-collapsed-card`。
- `web/frontend/src/styles.css`：補 `stock-page__main` 與 rail 內部候補列表高度；rail 內候補列重用原 component，但隱藏 reference chips 以降低側欄擁擠。
- UI-08 右上 `CandidateSwitcher` 保留，與左側候補列表共用同一份 `weeklyDecision.stock_candidates` state。

## 驗收結果

- `pnpm build` 通過。
- Browser desktop expanded：
  - 左側欄可見，含共用 `GlobalSettingsPanel` 與 `WeeklyCandidatesPanel`。
  - `gridTemplateColumns=379.992px 1742.02px`。
  - K 線寬度 `1704.515625px`。
  - 無水平溢出。
- Browser desktop collapsed：
  - `gridTemplateColumns=78px 2044.01px`。
  - K 線寬度擴為 `2006.5078125px`。
  - 無水平溢出。
- 左側候補切換：
  - 從 `3030 德律` 切到 `6451 訊芯-KY`。
  - 右上候補下拉同步為 `6451`。
  - 無水平溢出。
- Browser mobile：
  - viewport `390x900`。
  - 左側欄改為單欄寬 `374px`。
  - K 線寬 `340px`，`data-kline-density=compact`。
  - 無水平溢出。
- Diagnostics：
  - console 無 error。
  - API request 均 200。
- 證據：
  - `artifacts/top10_ui09_stock_collapsible_left_rail_acceptance_2026-05-18.json`

## Review 派工卡

任務ID：`REVIEW-UI-09`
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-18_UI-09_stock_page_collapsible_left_rail.md`、`web/frontend/src/app/MarketDeskApp.tsx`、`web/frontend/src/styles.css`、`web/frontend/src/features/settings/GlobalSettingsPanel.tsx`、`web/frontend/src/features/weekly-candidates/WeeklyCandidatesPanel.tsx`
任務目的：review 個股頁可收合左側欄是否重用共用元件、收合後 K 線主區有變寬、左側候補切換與右上下拉是否同步，且桌機/手機無水平溢出。
證據路徑：`artifacts/top10_ui09_stock_collapsible_left_rail_acceptance_2026-05-18.json`

## Header Replan 修正

使用者指出右上原生下拉視覺很醜，且擠壓個股工作台文案。修正方向：

- 移除個股主區右上原生下拉。
- 個股切換回歸左側共用 `WeeklyCandidatesPanel`。
- 個股 header 改為：
  - 左側：股票代號 / 名稱。
  - 下方：決策摘要 chips（盤勢、進場、停損、風報）。
  - 右側：模型勝率與配置權重。
- K 線上方 reference strip 維持。

補充驗收：

- `pnpm build` 通過。
- Browser desktop：
  - 原生 select 已移除。
  - header 顯示決策摘要 chips。
  - K 線寬度 `1704.515625px`，無水平溢出。
- Browser mobile：
  - 原生 select 已移除。
  - K 線寬度 `340px`，`data-kline-density=compact`。
  - 無水平溢出。
- 證據：
  - `artifacts/top10_ui09_stock_header_replan_acceptance_2026-05-18.json`
