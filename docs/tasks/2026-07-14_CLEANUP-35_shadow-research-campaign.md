# CLEANUP-35｜收斂 shadow research campaign runners

## 任務目的

依 CLEANUP-24 的 MERGE-07，把 A1 forward monitor、candidate stress matrix、overnight shadow training 與 overnight risk matrix summary 收斂為單一 stage-based research runner；完整保留舊 artifact/manifest 契約與研究邊界後，才退休舊入口。

## 請讀

- `.work/CLEANUP-24/evidence/retirement-plan.json` 的 `MERGE-07`
- `scripts/run_a1_forward_shadow_monitor.py`
- `scripts/run_candidate_stress_matrix.py`
- `scripts/run_overnight_shadow_training.py`
- `scripts/build_overnight_risk_matrix_summary.py`
- `config/script_lifecycle.yaml`

## 可改檔案

- 新增 `scripts/run_shadow_research_campaign.py`
- 刪除上述四支舊 runner/builder
- 新增 focused command-plan、manifest parity、dry-run 與 mocked subprocess tests
- 更新直接引用舊入口的 repo consumer（若搜尋證明存在）
- 更新 `config/script_lifecycle.yaml`
- 新增 `.work/CLEANUP-35/status.md`、`result.md`、`evidence/parity.json`

## 必須保留的契約

- stage/profile：`a1-forward`、`candidate-stress`、`overnight-training`、`risk-matrix-summary`
- 各 stage 保留原 CLI 參數語意、預設值、完整 subprocess command plan、執行順序、失敗判定與 exit code
- 各 stage 保留原 schema、完整 JSON/Markdown/TSV（適用時）、預設 artifact path、console JSON 與研究結論
- A1 保留四步驟與 `--reuse-existing`；lane、model hash guard、monitor status 不變
- candidate stress 保留所有 variants/scenarios、decision/delta/summary 與原 `--dry-run` 行為
- overnight training 保留 planned steps、steps TSV、summary.build、model hash before 與逐步 stdout/stderr tail
- risk matrix summary 必須成為 campaign 的具名 stage，保留 model file hash guard、candidate decision 與 JSON/Markdown
- top-level manifest 必須逐 stage 記錄 planned/running/OK/FAILED/SKIPPED、command、returncode、artifact path；不得以總 status 掩蓋 stage failure
- 新 runner 必須提供全域 `--dry-run`：不得啟動 subprocess、不得刪除既有 steps log、不得寫任何 stage artifact；僅在使用者明確給 top-level `--output` 時可寫 dry-run manifest
- valid/missing/failure fixture 的 old/new normalized payload、Markdown/TSV、console、exit code 與 command-plan parity

## 不可改

- 每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation
- `models/latest_lgbm.pkl`、production ranking/artifacts、正式資料與既有研究 artifact
- 被四支舊 runner 呼叫的 replay、ranking、summary 子工具及其資料語意
- 不得在驗收期間執行真實 replay、shadow ranking、training 或長跑 subprocess；只可用 dry-run 與 mocked subprocess

## 驗收證據

- 四個 stage 的 command-plan 與 manifest parity；涵蓋 valid、missing、subprocess failure
- dry-run side-effect test：subprocess 0 次、既有 TSV/artifact bytes 不變
- mocked subprocess 測試逐 stage status、early/continued execution 語意、console 與 exit code
- focused tests、reference/lifecycle strict-new、完整 pytest、`git diff --check`
- daily 四檔 SHA-256 與 CLEANUP-34 基線完全相同：
  - `scripts/run_daily.sh`: `3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3`
  - `scripts/run_daily_publish.sh`: `ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3`
  - `scripts/com.new-top10.daily.plist`: `eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995`
  - `config/automation.yaml`: `c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a`

## 交付限制

- strict 任務；只建立單一 atomic commit，不 merge、不 push。
- worktree 無 `.venv` 時借用主線既有 `.venv`；不得下載或建立新環境，不得把本機絕對路徑寫進共享文件。
- parity、dry-run side-effect 或 failure semantics 無法證明時保留對應舊入口並回報 blocker，不可硬刪。
