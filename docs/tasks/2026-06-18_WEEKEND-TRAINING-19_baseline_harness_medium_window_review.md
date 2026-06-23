# WEEKEND-TRAINING-19 baseline harness medium-window review

## 任務目的

承接 `WEEKEND-TRAINING-18`：

```text
small_window_status: OK
runner_can_read_baseline: true
ranking_file_count: 21
actual_replay_count: 21
estimated_unlockable_combo_count: 0
production_impact: NO_PRODUCTION_CHANGE
```

本卡不是直接跑中窗口，而是審核是否能把 baseline harness 擴到 60 ~ 120 個交易日。

## 要回答

```text
medium_window_review_status:
small_window_verified:
warning_profile_ok:
runtime_profile_ok:
date_coverage_candidate:
recommended_medium_window:
can_run_medium_window:
estimated_unlockable_combo_count:
next_action:
production_impact:
```

## 建議窗口

候選：

```text
60D: 2026-02-16 ~ 2026-05-15
100D: 2025-12-24 ~ 2026-05-15
120D: 2025-11-17 ~ 2026-05-15
```

Review 必須依據資料可用性與小窗口結果，選一個最小足夠窗口。

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准在 review 階段直接跑 60D / 100D / 120D replay。
- 不准跑 `202,176` 格 replay。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 medium-window review OK 視為全量解鎖。

## 請讀

- `docs/tasks/2026-06-18_WEEKEND-TRAINING-19_baseline_harness_medium_window_review.md`
- `artifacts/weekend_training/baseline_harness_small_window_replay_2026-06-18.json`
- `artifacts/weekend_training/baseline_harness_small_window_replay_verification_latest.json`
- `artifacts/backtest/production_baseline_harness_small_window/manifest.json`
- `scripts/run_baseline_harness_small_window_replay.py`
- `scripts/verify_baseline_harness_small_window_replay.py`

## 要做

新增 review builder：

```text
scripts/build_baseline_harness_medium_window_review.py
```

新增 verifier：

```text
scripts/verify_baseline_harness_medium_window_review.py
```

Builder 只做 review，不跑 replay。

必須輸出：

```text
medium_window_review_status: OK / BLOCKED
recommended_medium_window
recommended_start_date
recommended_end_date
reason
estimated_runtime_class
estimated_unlockable_combo_count: 0
next_action
```

Verifier 必須確認：

```text
small_window verification OK
recommended window <= 120 trading days
estimated_unlockable_combo_count == 0
target_production_path_created == false
production_impact == NO_PRODUCTION_CHANGE
no PROMOTION_READY
```

## 預期產物

- `artifacts/weekend_training/baseline_harness_medium_window_review_2026-06-18.json`
- `artifacts/weekend_training/baseline_harness_medium_window_review_2026-06-18.md`
- `artifacts/weekend_training/baseline_harness_medium_window_review_verification_latest.json`

## 完成後下一步

若 review BLOCKED：

```text
修小窗口 / warning / runtime blocker
```

若 review OK：

```text
WEEKEND-TRAINING-20_baseline_harness_medium_window_replay
```

只能跑 review 指定的 medium window，仍不得全量 replay。
