# WEEKEND-TRAINING-12 artifact blocker rollup integration

## 任務目的

承接 `WEEKEND-TRAINING-11` 的結論：

```text
baseline_source_status: BLOCKED_PROVENANCE_GAP
can_materialize_artifacts_backtest_production: false
unlockable_combo_count_estimate: 0
```

因此 `UNSUPPORTED_RANKING_DIR_MISSING` 不能再被當成「下一批可以直接跑的灰霧」。

本卡要把它明確標成 artifact provenance blocker，讓 weekend rollup / research map 顯示正確狀態。

## 背景

目前最大 unsupported 類別：

```text
UNSUPPORTED_RANKING_DIR_MISSING: 202,176
top reason: MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production
```

`WEEKEND-TRAINING-11` 已確認：

- 有類似 candidate source。
- 但沒有任何來源能證明自己是 `artifacts/backtest/production` 的 canonical global baseline。
- 不准用 candidate ranking、subset ranking、或 work artifact 假裝 production baseline。

## 任務範圍

請讀：

- `docs/tasks/2026-06-17_WEEKEND-TRAINING-11_production_baseline_ranking_source_audit.md`
- `artifacts/weekend_training/weekend_production_baseline_source_audit_2026-06-13.json`
- `scripts/build_weekend_training_rollup.py`
- `scripts/build_research_fog_map.py`
- `scripts/verify_weekend_training_rollup.py`
- `scripts/verify_research_fog_map.py`

要做：

1. 在 rollup 中新增 artifact blocker summary，至少包含：

```text
artifact_blocker_count
artifact_blocker_category_counts
artifact_blocker_reason_top_counts
```

2. 將 `UNSUPPORTED_RANKING_DIR_MISSING` 明確歸入：

```text
ARTIFACT_BLOCKER_PROVENANCE_GAP
```

3. research map / fog map 要能顯示：

```text
unsupported: 574,695
artifact blocker: 202,176
ranking baseline provenance gap: 202,176
```

4. 這是狀態揭露，不是解鎖，不得增加 executed progress。

## 明確禁止

- 不准 materialize `artifacts/backtest/production`。
- 不准建立 symlink / copy baseline 目錄。
- 不准跑 202,176 格 replay。
- 不准把 blocker 顯示成 completed / executed / inherited。
- 不准改 production ranking / model / Clawd。

## 預期產物

- 更新 `artifacts/weekend_training/weekend_training_rollup_YYYY-MM-DD.json`
- 更新 `artifacts/research_map/research_fog_map_latest.json`
- 更新 verifier output：
  - `artifacts/weekend_training/weekend_training_rollup_verification_latest.json`
  - `artifacts/research_map/research_fog_map_verification_latest.json`

## 驗收標準

- `rollup_classified_total` 仍等於 `full_universe_total`。
- `expanded_processed` 不因 artifact blocker 增加。
- `artifact_blocker_count == 202176`。
- `artifact_blocker_count` 必須包含在 `unsupported_count` 裡，不得重複計入 full universe。
- verifier 必須檢查 artifact blocker count 與 source audit blocker 一致。
- `production_impact == NO_PRODUCTION_CHANGE`。

## 完成後的下一步

若這張完成，後續才開：

```text
WEEKEND-TRAINING-13_production_baseline_provenance_design
```

用來定義 canonical production baseline 要如何長出來；不是把現有候選來源直接拿來用。
