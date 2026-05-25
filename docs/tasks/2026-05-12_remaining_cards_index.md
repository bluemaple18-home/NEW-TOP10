# 剩餘重構卡片索引

## 主線順序

這批卡片目的：把 M4 / M7 / M9 / 個股 UI 接成一條可 review 的垂直路線。另一個對話框每次只做一張卡，做完即停，交給 review；review findings 再回到本線修。

0. `GLOBAL-REWRITE-DIRECTIVE`：先讀全專案翻修授權，知道哪些可以重寫、哪些底線不能破。
1. `M4-01`：建立技術 + 事件 + 基本面的訓練資料契約。`completed`
2. `M4-02`：LightGBM 改吃合併後特徵，並維持 walk-forward / purge。`completed`
3. `M7-01`：排名融合拆成 `prediction_score + setup_score + quality_score - risk_penalty`。`completed`
4. `M9-01`：Top10 輸出建議權重、單檔上限與總曝險。`completed`
5. `UI-01`：補個股詳情後端 contract/API，聚合 K 線、基本面、交易計畫、回測證據。`completed`
6. `UI-02`：前端個股頁改成四區：K 線、基本面、交易計畫、回測證據。`completed`
7. `UI-03`：K 線工作台區間切換、30D 精確資料視窗與 browser 驗收。`completed`
8. `UI-04`：K 線操作 overlay，把進場區間、停損、停利畫進 K 線。`completed`
9. `UI-05`：個股頁下方分析 tabs，讓 Show Case / 基本面 / 交易計畫 / 回測證據不再擠壓 K 線。`completed`
10. `UI-06`：手機版 K 線 readability，窄寬下改 compact mode 避免指標與標籤重疊。`completed`
11. `M13-01`：建立產業與 ETF 維度資料契約，只讀本地 mapping。`completed`
12. `M13-02`：把產業與 ETF 維度接進 ranking/detail 分析輸出。`completed`
13. `M13-03`：研究產業中性化、產業強弱與 ETF overlap 風險是否值得進模型。`completed`
14. `M13-04`：本地產業 reference mapping 覆蓋率補齊，用本地 concept industry membership 產生完整 `stock_industry_map.csv`。`completed`
15. `M13-05`：產業動能與 sector rotation shadow research，只產出研究證據，不進 production score。`completed`
16. `M13-06`：產業動能 shadow ranking / walk-forward 評估，必須使用 leave-one-out / ex-self group factor。`completed`
17. `M13-07`：產業動能 shadow monitor 接入 automation，只更新研究 artifact。`completed`

## Review 卡

- `REVIEW-M13-04`：review M13-03 / M13-04 產業 mapping 與研究修正，確認可否進下一張 `M13-05`。
- `REVIEW-M13-05`：review M13-05 產業動能 shadow research，確認可否進下一張 `M13-06`。
- `REVIEW-M13-06`：review M13-06 ex-self shadow ranking，確認 `monitor_only` 是否成立。
- `REVIEW-M13-07`：review M13-07 產業動能 shadow monitor automation，確認無 production 泄漏。

## Checkpoints

- Checkpoint A：完成 `M4-01`、`M4-02` 後，必須跑 model foundation / review fixes / pipeline validate，並確認 walk-forward 沒有 leakage。
- Checkpoint B：完成 `M7-01`、`M9-01` 後，ranking CSV/API 必須能同時保留舊欄位與新欄位，避免 UI 中斷。
- Checkpoint C：完成 `UI-01`、`UI-02` 後，必須跑 API smoke、`pnpm build`，並用 browser 看個股頁四區是否能載入。
- Checkpoint C2：完成 `UI-03` 後，必須用 browser 驗 `30D / 3M / 6M / 1Y / 全部` 的實際資料視窗，不能只看按鈕 active 或預估 barSpace。
- Checkpoint C3：完成 `UI-04` 後，必須用 browser 驗交易 overlay 存在，且切換 K 線區間後 overlay 仍保留。
- Checkpoint C4：完成 `UI-05` 後，必須用 browser 驗個股頁分析 tabs 可切換、沒有水平溢出，且 K 線寬度不受 tab 內容影響。
- Checkpoint C5：完成 `UI-06` 後，必須用 browser 驗 mobile K 線進入 compact mode，且桌機仍維持 full mode。
- Checkpoint D：完成 `M13-01`、`M13-02` 後，必須確認缺 mapping 時 API/UI 不壞，且產業/ETF 只先揭露不改 ranking score。

## Review 交接規則

- 每張卡做完只回報：改了什麼、驗證結果、已知風險、下一張卡是否可開始。
- 不要一次做多張卡；跨卡改動容易讓 review 失焦。
- 回測績效仍隔離：UI/API 只能讀已存在 artifact，不可在 read API 觸發回測。
- 基本面只讀 cache 或既有離線匯入結果，不可在 ranking/API request path 即時爬外部網站。
