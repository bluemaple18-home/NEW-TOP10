# WEEKEND-TRAINING-13 canonical production baseline materialization smoke

## 任務目的

承接 `WEEKEND-TRAINING-OVERNIGHT-01` 的結論：

```text
actual_replay_count: 0
baseline blocker: 202,176
TOPIC_DEFAULT blocker: 88,695
regime slice blocker: 283,824
production_impact: NO_PRODUCTION_CHANGE
```

目前最有槓桿的缺口是：

```text
MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production
```

本卡目標是定義並驗證 `artifacts/backtest/production` 的 canonical 來源，最多只做最小 materialization smoke。

## 為什麼需要這張

`WEEKEND-TRAINING-11` 已確認：

- 有多個類似 production / baseline 候選來源。
- 但沒有足夠 provenance 證明它們就是 `artifacts/backtest/production` 的 canonical source。
- 因此不能直接 symlink / copy / rename 任一候選目錄。

如果這張不先做，`202,176` 格就不能合法進 replay。

## 請讀

- `docs/tasks/2026-06-17_WEEKEND-TRAINING-11_production_baseline_ranking_source_audit.md`
- `docs/tasks/2026-06-17_WEEKEND-TRAINING-OVERNIGHT-01_full_night_unlock_and_replay_campaign.md`
- `artifacts/weekend_training/weekend_production_baseline_source_audit_2026-06-13.json`
- `artifacts/weekend_training/weekend_production_baseline_provenance_design_2026-06-17.json`
- `artifacts/weekend_training/overnight_campaign_summary_2026-06-17.json`
- `scripts/weekend_training_common.py`
- `scripts/build_weekend_universe_inventory.py`

## 任務範圍

### Step 1：定義 canonical production baseline contract

必須明確回答：

```text
baseline_source_of_truth
source_artifact_path
date_coverage
required_columns
sort_order_contract
ranking_score_contract
stock_id_contract
no_future_data_contract
provenance_fields
```

### Step 2：找一個最小 materialization candidate

只能選一個最小 slice：

```text
1 source path
1 date or very small date range
1 output temp/staging path
```

不得直接輸出到：

```text
artifacts/backtest/production
```

只能輸出到 staging，例如：

```text
artifacts/weekend_training/staging/production_baseline_smoke/
```

### Step 3：驗證 staging baseline 是否可比較

Verifier 至少要檢查：

```text
schema columns ok
date coverage ok
stock_id format ok
ranking order deterministic
source provenance present
candidate source is not mislabeled as production
no production output path touched
```

### Step 4：只估算可解鎖量，不解鎖

若 smoke OK，只能輸出：

```text
materialization_smoke_status: OK
estimated_unlockable_combo_count: 202176
next_action: open controlled materialization card
```

不得直接重跑 `202,176` 格。

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准 symlink / copy 任一候選目錄到 production baseline path。
- 不准跑 202,176 格 replay。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 smoke OK 解讀成 promotion / production ready。

## 預期產物

- `artifacts/weekend_training/production_baseline_materialization_smoke_YYYY-MM-DD.json`
- `artifacts/weekend_training/production_baseline_materialization_smoke_YYYY-MM-DD.md`
- `artifacts/weekend_training/production_baseline_materialization_smoke_verification_latest.json`
- 若需要 staging：
  - `artifacts/weekend_training/staging/production_baseline_smoke/`

## 驗收標準

```text
smoke_status: OK / BLOCKED
canonical_contract_defined: true
source_provenance_ok: true / false
staging_output_only: true
production_baseline_path_created: false
estimated_unlockable_combo_count: 0 or 202176
production_impact: NO_PRODUCTION_CHANGE
```

Verifier 必須確認：

- `artifacts/backtest/production` 沒被建立。
- output path 不在 production baseline path。
- 若 smoke OK，必須有 source provenance。
- 若 smoke BLOCKED，必須有 blocker reason。
- 不得出現 `PROMOTION_READY`。

## 完成後下一步

若 BLOCKED：

```text
維持 ARTIFACT_BLOCKER_PROVENANCE_GAP
不跑 replay
```

若 OK：

```text
開 WEEKEND-TRAINING-14_controlled_production_baseline_materialization
只 materialize canonical baseline，不跑全量 replay
```
