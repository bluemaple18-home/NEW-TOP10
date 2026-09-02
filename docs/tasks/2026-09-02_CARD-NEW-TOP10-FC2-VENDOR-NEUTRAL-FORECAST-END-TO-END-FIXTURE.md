# FC2 Vendor-Neutral Forecast End-to-End Fixture 派工卡

工作名稱：FC2 通用 Forecast 端到端 deterministic fixture；chain_id=`FC2-FORECAST-E2E-01`；角色為 strict/core-bounded Worker，交付實作與可重現證據，不做 Mainline 裁決。

來源與目標：canonical main `9abc1592c54e6e34f95cba347f5d61f080a098cd`；沿用既有 `research-dataset-bundle.v1`、`forecast-trial-spec.v1`、forecast artifact receipt 與 forecast evaluation observation contract，以固定小型資料及 deterministic fake／naive executor 證明 create → validate → execute → point/quantile artifact → receipt → evaluation → rebuild 的最小閉環；相同輸入重跑須得到相同 content identity。

實作邊界：不得新增或修改 FC1 contract 欄位，不得出現 `TimesFM*` 通用命名，不得下載模型、呼叫網路或依賴外部服務；不得修改 #13／#14、策略矩陣、queue、runner、capacity、M4–M7、ranking、production 或既有 eligibility policy；不得新增 database、registry、ledger、canonical writer 或第二套 runtime。若現有 FC1 schema 無法完成 fixture，立即回報 `CONTRACT_GAP / HOLD`，不得自行擴 schema。

驗收：正向測試須建立合法 dataset bundle、forecast trial spec、固定 point/quantile artifacts、artifact receipt 與 `ForecastEvaluationObservation`，並驗證 deterministic rebuild；負向測試至少涵蓋 bundle/spec identity mismatch、artifact bytes／digest 替換、production-like usage status、`available_at` 洩漏，以及 forecast observation 不能進入策略 observation ingestion／eligibility。只允許最小 fixture module／tests／必要 evidence，所有 artifact 寫入 test temporary directory，不得污染 repo runtime output。

驗證與回報：使用 GPT-5.5 high；CodeGraph-first；跑 targeted tests、受影響 regression、changed-file allowlist、`git diff --check` 與 worktree clean；以固定 implementation SHA 回報變更檔、測試數、限制與 remaining risks。不得 merge、push、deploy、production、改 Issue 或 external write；完成後由 Mainline 另派獨立 fixed-SHA Reviewer。
