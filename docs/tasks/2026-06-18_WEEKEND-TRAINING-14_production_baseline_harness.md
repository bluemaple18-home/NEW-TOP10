# WEEKEND-TRAINING-14 production baseline harness

## 任務目的

建立本專案專用的 deterministic `production_baseline_harness`。

它的責任是：

```text
用正式 ranking pipeline contract 產出可追溯的 backtest-safe production baseline staging artifact。
```

不是 Clawd，不是通知工具，也不是 promotion gate。

## 背景

`WEEKEND-TRAINING-13` 已確認：

```text
production_baseline_materialization_smoke: BLOCKED
source_provenance_ok: false
column_contract_ok: true
stock_id_contract_ok: true
production_baseline_path_created: false
estimated_unlockable_combo_count: 0
```

也就是既有候選來源的欄位看起來對，但 provenance 不夠，不能拿來冒充：

```text
artifacts/backtest/production
```

因此需要一個正式 harness，從正確 pipeline contract 產 baseline，而不是 copy / symlink 既有候選目錄。

## 任務範圍

請讀：

- `docs/tasks/2026-06-18_WEEKEND-TRAINING-13_canonical_production_baseline_materialization_smoke.md`
- `artifacts/weekend_training/production_baseline_materialization_smoke_2026-06-18.json`
- `scripts/build_production_baseline_materialization_smoke.py`
- `scripts/verify_production_baseline_materialization_smoke.py`
- `scripts/build_historical_ranking_replay_set.py`
- `scripts/run_capital_aware_replay.py`
- `scripts/build_clawd_publish_payload.py`
- `app/pipeline_cli.py`

## 要做

### 1. 新增 harness 腳本

建議檔名：

```text
scripts/build_production_baseline_harness.py
```

CLI 建議：

```bash
.venv/bin/python scripts/build_production_baseline_harness.py \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --output-dir artifacts/weekend_training/staging/production_baseline_harness_YYYY-MM-DD
```

### 2. 新增 verifier

建議檔名：

```text
scripts/verify_production_baseline_harness.py
```

Verifier 必須驗：

```text
schema columns ok
date coverage ok
stock_id non-empty
ranking order deterministic
manifest exists
manifest has generator command / model artifact / config / data range
output path is staging-only
artifacts/backtest/production not created
not copied from candidate/subset source
production_impact == NO_PRODUCTION_CHANGE
no PROMOTION_READY
```

### 3. 只跑最小 smoke

先跑小日期範圍，例如：

```text
2026-05-13 ~ 2026-05-15
```

目的只是證明 harness 可重跑、可追溯、可驗證。

不准直接跑半年。

### 4. 產出 manifest

Staging 目錄必須有：

```text
manifest.json
ranking_YYYY-MM-DD.csv
```

Manifest 至少包含：

```text
schema_version
generated_at
start_date
end_date
ranking_dates
generator_command
source_pipeline
model_artifact
model_hash
config_hash
data_source
feature_source
no_future_data_contract
output_dir
production_impact
```

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准 copy / symlink 既有 candidate / subset / research ranking 目錄當結果。
- 不准跑 202,176 格 replay。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 harness smoke OK 當成 production ready。

## 預期產物

- `scripts/build_production_baseline_harness.py`
- `scripts/verify_production_baseline_harness.py`
- `artifacts/weekend_training/staging/production_baseline_harness_YYYY-MM-DD/manifest.json`
- `artifacts/weekend_training/production_baseline_harness_smoke_YYYY-MM-DD.json`
- `artifacts/weekend_training/production_baseline_harness_smoke_YYYY-MM-DD.md`
- `artifacts/weekend_training/production_baseline_harness_verification_latest.json`

## 驗收標準

```text
harness_status: OK / BLOCKED
staging_output_only: true
ranking_file_count >= 1
manifest_present: true
provenance_complete: true
target_production_path_created: false
copied_from_candidate_source: false
production_impact: NO_PRODUCTION_CHANGE
```

如果 BLOCKED：

- 必須寫出 blocker reason。
- 不得產生假的 ranking。

如果 OK：

- 下一張只能開 controlled materialization review。
- 不得自動解鎖 `202,176` 格。

## 完成後下一步

若 harness smoke OK：

```text
WEEKEND-TRAINING-15_controlled_production_baseline_materialization_review
```

若 harness smoke BLOCKED：

```text
維持 ARTIFACT_BLOCKER_PROVENANCE_GAP
修正 harness blocker
```
