# WEEKEND-TRAINING-15 controlled production baseline materialization review

## 任務目的

承接 `WEEKEND-TRAINING-14` 的結果：

```text
harness_status: OK
ranking_file_count: 3
date range: 2026-05-13 ~ 2026-05-15
verification status: OK
production_impact: NO_PRODUCTION_CHANGE
artifacts/backtest/production: still missing
```

本卡要審核：staging baseline 是否可以進入 controlled materialization。

注意：這張仍不是全量 replay，也不是 production rollout。

## 請讀

- `docs/tasks/2026-06-18_WEEKEND-TRAINING-14_production_baseline_harness.md`
- `artifacts/weekend_training/staging/production_baseline_harness_2026-06-18/manifest.json`
- `artifacts/weekend_training/production_baseline_harness_smoke_2026-06-18.json`
- `artifacts/weekend_training/production_baseline_harness_verification_latest.json`
- `scripts/build_production_baseline_harness.py`
- `scripts/verify_production_baseline_harness.py`
- `scripts/weekend_training_common.py`

## 要回答

```text
materialization_review_status:
staging_harness_verified:
manifest_provenance_complete:
date_coverage_sufficient_for_smoke:
can_materialize_research_baseline:
target_output_path:
allowed_date_range:
estimated_unlockable_combo_count:
next_action:
production_impact:
```

## 允許範圍

可以審核並提出 controlled materialization 方案。

如果 smoke 條件足夠，可以只允許 materialize 到 research-only baseline path，例如：

```text
artifacts/backtest/production_baseline_harness_smoke/
```

但仍不准直接輸出到：

```text
artifacts/backtest/production
```

## 明確禁止

- 不准直接建立 `artifacts/backtest/production`。
- 不准跑 `202,176` 格 replay。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 3 天 smoke 視為半年 baseline 已完成。
- 不准把 controlled materialization review OK 視為 promotion ready。

## 預期產物

- `artifacts/weekend_training/production_baseline_materialization_review_YYYY-MM-DD.json`
- `artifacts/weekend_training/production_baseline_materialization_review_YYYY-MM-DD.md`
- `artifacts/weekend_training/production_baseline_materialization_review_verification_latest.json`

## 驗收標準

Verifier 必須確認：

- harness verification status 是 OK。
- manifest 存在且 provenance 欄位完整。
- target output path 不是 `artifacts/backtest/production`。
- 若 `can_materialize_research_baseline == true`，只能允許 3 天 smoke date range。
- `estimated_unlockable_combo_count` 只能是 0，因為 3 天 smoke 不能解鎖 202,176 格。
- `production_impact == NO_PRODUCTION_CHANGE`。
- 不得出現 `PROMOTION_READY`。

## 完成後下一步

若 review BLOCKED：

```text
修 harness / manifest blocker
```

若 review OK：

```text
WEEKEND-TRAINING-16_research_only_baseline_materialization_smoke
```

只 materialize 3 天到 research-only path，然後做最小 replay smoke。
