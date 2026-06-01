# REVIEW-20260601-model-gov-full

## 卡片類型
Review

## 任務目的
審查 `MODEL-GOV-FULL` 實作是否真的只是 model experiment ledger / evidence memory layer，並確認它沒有長成第二套 acceptance engine、promotion gate 或 retrain pipeline。

## 背景
`MODEL-GOV-FULL` 已完成 checkpoint A/B/C，ledger entries 目前為 4，狀態為 pending 2、failed 2、passed 0。Promotion adapter 回報 `MISSING_LEDGER_EVIDENCE`，這是預期狀態：治理系統已可追蹤實驗，但沒有、也不應該宣稱任何模型可升版。

Daily report 實跑缺 `artifacts/ranking_2026-05-31.csv`，此缺口只能視為日報資料缺口，不應被判定為 ledger / governance 主線失敗。

## Scope
- Review `MODEL-GOV-FULL` 相關 ledger schema、CLI、verifier、research flow integration、result resolver、stats、backfill dry-run、promotion evidence adapter。
- Review result report 是否仍是 verdict source of truth，ledger resolver 是否只同步狀態。
- Review promotion adapter 是否只輸出 ledger evidence status，不輸出 promotion-ready 類狀態。
- Review daily / weekend governance surfacing 是否只露出摘要，不改 ranking 或推薦理由。
- Review backfill 是否保守處理舊 artifact，不把 monitor-only / stale 舊資料升級成 passed。

## Out Of Scope
- 不重訓正式模型。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不改 production ranking / `risk_adjusted_score`。
- 不新增 sealed OOS、replay、rollback 或 model group acceptance 的替代 gate。
- 不把 ledger `passed` 解讀成 production promotion。
- 不修 daily report 缺 `ranking_2026-05-31.csv`，除非另開資料補跑卡。

## 驗收條件
- Ledger verifier self-test 通過。
- Ledger current file verifier 通過。
- `run_model_research_flow.py` 產物 verifier 通過，且 summary 包含 ledger updates / pending / collision / verification status。
- Result report verifier 通過，且 result report 仍是 verdict source of truth。
- Backfill dry-run 通過，且不修改舊 artifact。
- Promotion adapter 輸出只允許 `MISSING_LEDGER_EVIDENCE` / `LEDGER_EVIDENCE_BLOCKED` / `LEDGER_EVIDENCE_OK`。
- Review 確認 forbidden outputs 不存在：`PROMOTION_READY`、`AUTO_PROMOTE`、`MODEL_APPROVED`。
- Review 確認 sealed / replay / rollback / model group acceptance 沒有被 ledger 取代。
- `git diff --check` 通過。

## Review Questions
- [P1] Ledger verifier 是否真的只檢查 ledger integrity，沒有重做 no-hindsight / sealed / replay / promotion gate？
- [P1] Promotion adapter 是否可能被下游誤讀為模型升版授權？
- [P1] Result resolver 是否有重新計算 verdict 或改寫 result report 的 decision policy？
- [P2] `due` / `expired` / `reschedule` / `supersede` 的狀態轉移是否會覆蓋 history，而不是 append-only？
- [P2] Backfill 是否會把舊 monitor-only、partial、stale artifact 誤升成 passed？
- [P2] Daily / weekend report 是否只顯示 governance summary，沒有污染股票推薦訊息或 ranking score？
- [P2] `source_artifacts` 是否全部 repo-relative，沒有本機絕對路徑或跨機不可用命令？
- [P2] 缺 `ranking_2026-05-31.csv` 是否只被記錄為資料缺口，而不是治理主線失敗？
