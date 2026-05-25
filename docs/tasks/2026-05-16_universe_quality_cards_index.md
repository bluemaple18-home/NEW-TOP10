# Universe Quality / Fundamental Ranking 卡片索引

## 主線順序

這組卡片目的：修正目前樣本式 universe 對基本面 coverage 與 ranking 評估造成的污染，先建立真實 universe，再重跑基本面 shadow score，最後才決定是否接 ranking。

1. `UQ-01`：建立可交易台股 universe 本地資料契約。`completed`
2. `UQ-02`：建立離線 universe 匯入流程與 summary artifact。`completed`
3. `UQ-03`：找出 features/ranking 的 universe 產生入口，做小批重建 probe。`completed`
4. `UQ-04`：在真實或 probe universe 上重跑基本面 shadow score 評估。`completed`
5. `UQ-05`：根據證據決定是否接入 `quality_score` / `risk_penalty`。`completed`
6. `UQ-06`：移除 `FundamentalStage` dummy fallback，避免假基本面污染資料。`completed`
7. `UQ-07`：Staged real-universe rebuild，不覆蓋正式 `data/clean`。`completed_with_recovery`
8. `UQ-08`：恢復 `models/latest_lgbm.pkl`，避免 ranking 使用模型 fallback。`completed`
9. `UQ-09`：修復或 gate TWSE historical source，處理長週期 coverage warning。`completed_with_gate`
10. `UQ-10`：落實 fundamental ranking gate，避免低 coverage 基本面欄位偷渡進 `quality_score`。`completed`
11. `UQ-11`：落實 fundamental model gate，避免低 coverage 基本面欄位進入 LightGBM。`completed`

## Checkpoints

- Checkpoint A：完成 `UQ-01`、`UQ-02` 後，必須能驗證 `tradable_universe.csv` schema，且 API/read service 不即時抓外部資料。
- Checkpoint B：完成 `UQ-03` 後，不得覆蓋正式 `features.parquet`；只能用 probe artifact 判斷是否可全量重建。
- Checkpoint C：完成 `UQ-04` 後，必須有 coverage / IC / 分組報酬 / ranking sensitivity 報告。
- Checkpoint D：完成 `UQ-05` 後，若證據不足，結論必須明確保留在 explain-only 或 shadow-only。

## 共用限制

- 不在 UI/API request path 即時爬 Goodinfo、TWSE 或 TPEX。
- 不用低 coverage 結果調 ranking 權重。
- 不覆蓋正式資料前，必須先有 probe 與回退路徑。
- 基本面可以先幫助解釋，但要進 ranking 必須有回測/IC 證據。
