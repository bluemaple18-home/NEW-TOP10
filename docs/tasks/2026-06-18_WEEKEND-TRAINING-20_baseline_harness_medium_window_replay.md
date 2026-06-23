# WEEKEND-TRAINING-20 baseline harness medium-window replay

## 任務目的

承接 `WEEKEND-TRAINING-19`：

```text
medium_window_review_status: OK
recommended_medium_window: 100D
recommended_start_date: 2025-12-24
recommended_end_date: 2026-05-15
actual_trading_days_estimate: 90
estimated_unlockable_combo_count: 0
production_impact: NO_PRODUCTION_CHANGE
```

本卡只跑 review 指定的 medium window replay。

這不是全量 replay，不解鎖 `202,176` 格。

## 允許窗口

唯一允許：

```text
2025-12-24 ~ 2026-05-15
```

不得自行改成 60D / 120D / 半年 / 三年。

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准跑 `202,176` 格 replay。
- 不准跑超過 review 指定窗口。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 medium replay OK 視為全量解鎖。

## 請讀

- `docs/tasks/2026-06-18_WEEKEND-TRAINING-20_baseline_harness_medium_window_replay.md`
- `artifacts/weekend_training/baseline_harness_medium_window_review_2026-06-18.json`
- `artifacts/weekend_training/baseline_harness_medium_window_review_verification_latest.json`
- `scripts/build_production_baseline_harness.py`
- `scripts/run_baseline_harness_small_window_replay.py`
- `scripts/verify_baseline_harness_small_window_replay.py`

## 要做

新增 medium replay runner：

```text
scripts/run_baseline_harness_medium_window_replay.py
```

新增 verifier：

```text
scripts/verify_baseline_harness_medium_window_replay.py
```

Runner 必須：

- 讀 WEEKEND-TRAINING-19 review artifact。
- 僅使用 review 指定日期。
- 透過 production baseline harness 產 medium-window research-only baseline。
- materialize 到：

```text
artifacts/backtest/production_baseline_harness_medium_window
```

- 跑 medium-window replay。
- 輸出 summary，不更新 full universe progress。

Verifier 必須確認：

```text
medium_window_status: OK / BLOCKED
input_baseline_path == artifacts/backtest/production_baseline_harness_medium_window
start_date == 2025-12-24
end_date == 2026-05-15
ranking_file_count >= 60
actual_replay_count >= 60
estimated_unlockable_combo_count == 0
target_production_path_created == false
production_impact == NO_PRODUCTION_CHANGE
no PROMOTION_READY
```

## 預期產物

- `artifacts/backtest/production_baseline_harness_medium_window/manifest.json`
- `artifacts/weekend_training/baseline_harness_medium_window_replay_2026-06-18.json`
- `artifacts/weekend_training/baseline_harness_medium_window_replay_2026-06-18.md`
- `artifacts/weekend_training/baseline_harness_medium_window_replay_verification_latest.json`

## 驗收標準

```text
medium_window_status: OK
runner_can_read_baseline: true
ranking_file_count >= 60
actual_replay_count >= 60
estimated_unlockable_combo_count: 0
target_production_path_created: false
production_impact: NO_PRODUCTION_CHANGE
```

## 完成後下一步

若 OK：

開 `WEEKEND-TRAINING-21_baseline_harness_unlock_policy_review`。

這張才討論是否可以從 medium-window baseline 進入 controlled unlock policy；仍不是直接全量跑。
