# CLEANUP-34｜收斂 weekend readiness audit builder

## 任務目的

依 CLEANUP-24 的 MERGE-06，把 weekend overnight campaign、ranking-dir unlock smoke、unsupported unlock audit 三支 builder 收斂為單一具名 profile 入口；完整保留 research-only 與 `NO_PRODUCTION_CHANGE` 邊界後，才退休舊入口。

## 請讀

- `.work/CLEANUP-24/evidence/retirement-plan.json` 的 `MERGE-06`
- `scripts/build_weekend_overnight_campaign_audits.py`
- `scripts/build_weekend_ranking_dir_unlock_smoke.py`
- `scripts/build_weekend_unsupported_unlock_audit.py`
- `scripts/verify_weekend_overnight_campaign_summary.py`
- `scripts/verify_weekend_ranking_dir_unlock_smoke.py`
- `scripts/verify_weekend_unsupported_unlock_audit.py`
- `scripts/weekend_training_common.py`
- `config/script_lifecycle.yaml`

## 可改檔案

- 新增 `scripts/build_weekend_readiness_audit.py`
- 刪除上述三支舊 builder
- 更新兩支直接 import 舊 builder 的 verifier：
  - `scripts/verify_weekend_ranking_dir_unlock_smoke.py`
  - `scripts/verify_weekend_unsupported_unlock_audit.py`
- 新增 focused parity / consumer tests
- 更新 `config/script_lifecycle.yaml`
- 新增 `.work/CLEANUP-34/status.md`、`result.md`、`evidence/parity.json`

## 必須保留的契約

- profile：`campaign`、`ranking-dir-smoke`、`unsupported-unlock`
- campaign 仍一次產出以下四組 JSON/Markdown，不得合併或省略：
  - `weekend_production_baseline_provenance_design_<date>`
  - `weekend_topic_default_entry_filter_contract_audit_<date>`
  - `weekend_regime_slice_data_adequacy_audit_<date>`
  - `overnight_campaign_summary_<date>`
- ranking-dir smoke 與 unsupported unlock 的 schema、path helper、完整 JSON、Markdown、預設 output、console JSON 與 exit code
- verifier 不得再 import 已刪除模組；改接新入口後，其既有 schema/path 判定與 CLI 行為不變
- 每個 profile 的 valid 與 missing fixture old/new normalized JSON、Markdown、console、exit code parity
- 所有新產生 payload 的 `production_impact` 必須精確等於 `weekend_training_common.PRODUCTION_IMPACT`，目前值為 `NO_PRODUCTION_CHANGE`
- campaign 的 `actual_replay_count=0`、禁止 replay/materialization/copy/symlink/production ranking/model/publish 的 contract 不變
- profile 僅負責 dispatch；不得把三套資料模型壓成共同簡化 schema

## 不可改

- `scripts/weekend_training_common.py` 的 `PRODUCTION_IMPACT` 或其他共用語意
- 每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation
- research inventory/rollup/map 語意、既有 artifact 內容或 blocker 結論
- replay、baseline materialization、artifact copy/symlink、任何正式營運狀態

## 驗收證據

- 三個 profile 的 old/new valid/missing parity，campaign 須逐一涵蓋四組 JSON/Markdown
- 兩支更新 verifier 的 consumer gate 通過；既有 overnight campaign summary verifier 亦通過
- focused tests、reference/lifecycle strict-new、完整 pytest、`git diff --check`
- daily 四檔 SHA-256 與 CLEANUP-33 基線完全相同：
  - `scripts/run_daily.sh`: `3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3`
  - `scripts/run_daily_publish.sh`: `ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3`
  - `scripts/com.new-top10.daily.plist`: `eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995`
  - `config/automation.yaml`: `c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a`

## 交付限制

- strict 任務；只建立單一 atomic commit，不 merge、不 push。
- worktree 無 `.venv` 時借用主線既有 `.venv`；不得下載或建立新環境，不得把本機絕對路徑寫進共享文件。
- parity 或 verifier consumer gate 無法證明時保留舊入口並回報 blocker，不可硬刪。
