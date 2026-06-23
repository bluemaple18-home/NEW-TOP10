# WEEKEND-TRAINING-16 research-only baseline materialization smoke

## 任務目的

承接 `WEEKEND-TRAINING-15` 的 review OK 結論：

```text
materialization_review_status: OK
allowed_date_range: 2026-05-13 ~ 2026-05-15
estimated_unlockable_combo_count: 0
production_impact: NO_PRODUCTION_CHANGE
```

本卡只允許把 3 天 staging baseline materialize 到 research-only baseline path。

## 允許輸出

唯一允許 materialize 的目錄：

```text
artifacts/backtest/production_baseline_harness_smoke
```

內容：

```text
manifest.json
ranking_2026-05-13.csv
ranking_2026-05-14.csv
ranking_2026-05-15.csv
```

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准 materialize 超過 2026-05-13 ~ 2026-05-15。
- 不准跑 202,176 格 replay。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 smoke materialization 視為 production baseline 完成。
- 不准把 `estimated_unlockable_combo_count` 設成非 0。

## 請讀

- `docs/tasks/2026-06-18_WEEKEND-TRAINING-16_research_only_baseline_materialization_smoke.md`
- `artifacts/weekend_training/production_baseline_materialization_review_2026-06-18.json`
- `artifacts/weekend_training/staging/production_baseline_harness_2026-06-18/manifest.json`
- `scripts/build_production_baseline_harness.py`
- `scripts/verify_production_baseline_harness.py`

## 要做

新增 materializer：

```text
scripts/materialize_research_only_production_baseline_smoke.py
```

新增 verifier：

```text
scripts/verify_research_only_production_baseline_smoke.py
```

Materializer 必須：

- 讀 `production_baseline_materialization_review_2026-06-18.json`。
- 確認 review OK。
- 只複製 staging harness 的三個 ranking 檔。
- 產 research-only manifest。
- 不碰 `artifacts/backtest/production`。

Verifier 必須確認：

```text
target path == artifacts/backtest/production_baseline_harness_smoke
ranking_file_count == 3
dates == 2026-05-13, 2026-05-14, 2026-05-15
manifest exists
manifest traces source staging harness
estimated_unlockable_combo_count == 0
artifacts/backtest/production does not exist
production_impact == NO_PRODUCTION_CHANGE
no PROMOTION_READY
```

## 預期產物

- `artifacts/backtest/production_baseline_harness_smoke/manifest.json`
- `artifacts/backtest/production_baseline_harness_smoke/ranking_2026-05-13.csv`
- `artifacts/backtest/production_baseline_harness_smoke/ranking_2026-05-14.csv`
- `artifacts/backtest/production_baseline_harness_smoke/ranking_2026-05-15.csv`
- `artifacts/weekend_training/research_only_baseline_materialization_smoke_2026-06-18.json`
- `artifacts/weekend_training/research_only_baseline_materialization_smoke_verification_latest.json`

## 驗收標準

```text
materialization_status: OK
research_only: true
ranking_file_count: 3
target_production_path_created: false
estimated_unlockable_combo_count: 0
production_impact: NO_PRODUCTION_CHANGE
```

## 完成後下一步

若 OK：

開 `WEEKEND-TRAINING-17_baseline_harness_minimal_replay_smoke`。

它只能用 3 天 research-only baseline 做最小 replay smoke，不能進全量。
