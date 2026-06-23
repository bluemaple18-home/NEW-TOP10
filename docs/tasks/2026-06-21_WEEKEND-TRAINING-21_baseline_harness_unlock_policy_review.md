# WEEKEND-TRAINING-21 baseline harness unlock policy review

## 任務目的

承接 `WEEKEND-TRAINING-20`：

```text
medium_window_status: OK
runner_can_read_baseline: true
ranking_file_count: 90
actual_replay_count: 90
estimated_unlockable_combo_count: 0
production_impact: NO_PRODUCTION_CHANGE
```

本卡把 baseline harness 從「手動可跑」推進到「host runner 可自己跑受控任務」。

## 允許範圍

只允許自跑 review 指定的 medium-window bounded replay：

```text
2025-12-24 ~ 2026-05-15
artifacts/backtest/production_baseline_harness_medium_window
scripts/run_baseline_harness_medium_window_replay.py
scripts/verify_baseline_harness_medium_window_replay.py
```

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准跑 `202,176` 格 replay。
- 不准自動擴到 120D / 半年 / 三年 / full universe。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 medium replay OK 視為全量解鎖。

## 要做

新增 policy review：

```text
scripts/build_baseline_harness_unlock_policy_review.py
scripts/verify_baseline_harness_unlock_policy_review.py
```

新增 host runner：

```text
scripts/run_baseline_harness_host_runner.py
scripts/verify_baseline_harness_host_runner.py
scripts/run_baseline_harness_host_runner.sh
scripts/com.new-top10.baseline-harness.plist
```

host runner 必須：

- 讀 policy artifact。
- 只執行 allowlist action。
- 執行 runner 後立刻執行 verifier。
- 寫入 host runner status / summary。
- 有 lockfile、timeout、production guard。

## 預期產物

- `artifacts/weekend_training/baseline_harness_unlock_policy_review_YYYY-MM-DD.json`
- `artifacts/weekend_training/baseline_harness_unlock_policy_review_verification_latest.json`
- `artifacts/host_runner/YYYY-MM-DD/baseline_harness_host_runner_status_YYYY-MM-DD.json`
- `artifacts/host_runner/YYYY-MM-DD/baseline_harness_host_runner_summary_YYYY-MM-DD.json`

## 完成後下一步

若 host runner 驗證 OK，即可安裝 launchd 讓 baseline harness 自跑受控 smoke。
