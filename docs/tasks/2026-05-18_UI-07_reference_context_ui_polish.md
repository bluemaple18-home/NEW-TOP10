# UI-07：候補池與個股頁 reference context polish

任務ID：`UI-07`
卡片類型｜派工對象：Frontend / Reference context UI｜Codex
請讀：`docs/architecture/MOMENTUM_UI_SPEC.md`、`docs/tasks/2026-05-17_UI-06_mobile_kline_readability.md`、`docs/tasks/2026-05-17_M13-04_formal_industry_mapping_expansion.md`、`web/frontend/src/features/weekly-candidates/WeeklyCandidatesPanel.tsx`、`web/frontend/src/features/market/MarketSnapshotPanel.tsx`、`web/frontend/src/features/stock-detail/StockDetailPanel.tsx`、`web/frontend/src/styles.css`
任務目的：讓本週候補與個股頁的資訊層級更清楚，將產業 / ETF / 概念 reference 以中性風險揭露呈現，不把它寫成推薦理由，也不影響個股頁 K 線全寬。
證據路徑：`web/frontend` build output、browser screenshot、console/network/DOM 驗收紀錄、`artifacts/top10_ui07_reference_context_acceptance_2026-05-18.json`

## 狀態

`completed`

## 背景

M13-04 到 M13-07 已確認產業與 ETF 維度目前維持 `risk_disclosure_only / monitor_only`。前端可以顯示 reference context，但不能讓使用者誤讀成「產業動能已通過並進入推薦理由」。

同時個股頁必須維持規格中的上中下結構：

- 上：個股決策摘要與 reference context。
- 中：K 線全寬。
- 下：詳細分析 tabs。

## 範圍

- 本週候補列補中性 reference chips，例如產業、sector、ETF。
- 盤面摘要將「主流族群」調整為更中性的「候補集中」。
- 個股頁在 K 線上方補 reference strip，顯示分類、ETF overlap、概念摘要與資料邊界。
- TypeScript 補上 `stockDetail.reference` contract。

## 不做

- 不改 ranking score / LightGBM feature / weekly decision service。
- 不把產業或 sector 寫進 `primary_reasons`。
- 不接 M13-06 / M13-07 shadow monitor 到 UI。
- 不新增盤中即時價、個股搜尋、持股追蹤、ETF 成分 / 曝險分析。
- 不讓任何 reference 區塊放在 K 線左右兩側。

## 驗收計劃

- `pnpm build` 通過。
- Browser desktop：
  - 本週候補列能看到中性 reference chips。
  - 盤面摘要使用「候補集中」語意，不使用「共振」。
  - 個股頁 K 線仍是單欄全寬，reference strip 位於 K 線上方。
- Browser mobile：
  - 無水平溢出。
  - 候補列 chips 與個股 reference strip 可換行，不擠壓 K 線。
- DOM / console / network diagnostics 無明顯錯誤。

## 已知風險

- 目前只做 reference context 呈現，不等於完成產業動能 production integration。
- 若 API 回傳 reference section 缺漏，前端需用 ranking annotation fallback。

## 實作紀錄

- `web/frontend/src/features/weekly-candidates/WeeklyCandidatesPanel.tsx`：本週候補列新增中性 reference chips，顯示產業、sector、ETF fallback。
- `web/frontend/src/features/market/MarketSnapshotPanel.tsx`：盤面摘要由「主流族群」改為「候補集中」，用 chip 呈現分類集中，不寫成推薦訊號。
- `web/frontend/src/features/stock-detail/StockDetailPanel.tsx`：個股頁 K 線上方新增 `stock-reference-strip`，顯示分類、ETF / 概念 fallback 與 `Reference only` 邊界提醒。
- `web/frontend/src/types.ts`：補上 `reference_summary` 與 `stockDetail.reference` TypeScript contract。
- `web/frontend/src/styles.css`：新增 reference chips / strip / mobile wrapping 樣式；reference 區塊維持在 K 線上方，不進 K 線左右欄。

## 驗收結果

- `pnpm build` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py` 通過，`weekly_primary_reasons_no_industry_signal=True`。
- Browser desktop weekly：
  - 本週候補 10 檔。
  - 摘要 label 為「候補集中」。
  - 候補列顯示中性 reference chips，例如 `產業 設備或廠務工程`、`Sector 其他`。
  - 無水平溢出。
- Browser desktop stock：
  - reference strip 位於 K 線上方。
  - K 線仍為單欄全寬，`gridTemplateColumns=2098.5px`。
  - `activeRange=30D`、`data-kline-density=full`。
  - 無水平溢出。
- Browser mobile stock：
  - viewport `390x900`。
  - reference strip 與 K 線同寬 `340px`。
  - `data-kline-density=compact`。
  - 無水平溢出。
- Diagnostics：
  - console 無 error。
  - API request `weekly-candidates` / `stock detail` 均 200。
- 證據：
  - `artifacts/top10_ui07_reference_context_acceptance_2026-05-18.json`
  - `artifacts/top10_ui07_weekly_reference_desktop_2026-05-18.png`
  - `artifacts/top10_ui07_stock_reference_desktop_2026-05-18.png`
  - `artifacts/top10_ui07_stock_reference_mobile_2026-05-18.png`

## Review 派工卡

任務ID：`REVIEW-UI-07`
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-18_UI-07_reference_context_ui_polish.md`、`web/frontend/src/features/weekly-candidates/WeeklyCandidatesPanel.tsx`、`web/frontend/src/features/market/MarketSnapshotPanel.tsx`、`web/frontend/src/features/stock-detail/StockDetailPanel.tsx`、`web/frontend/src/types.ts`、`web/frontend/src/styles.css`
任務目的：review UI-07 是否只做中性 reference context 呈現，沒有把產業/ETF/sector 當推薦理由或接入 production score，並確認 K 線仍維持單欄全寬與 mobile 無 overflow。
證據路徑：`artifacts/top10_ui07_reference_context_acceptance_2026-05-18.json`、`artifacts/top10_ui07_weekly_reference_desktop_2026-05-18.png`、`artifacts/top10_ui07_stock_reference_desktop_2026-05-18.png`、`artifacts/top10_ui07_stock_reference_mobile_2026-05-18.png`
