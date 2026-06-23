# WEEKEND-TRAINING-18 baseline harness small-window replay

## 任務目的

承接 `WEEKEND-TRAINING-17`：

```text
replay_smoke_status: OK
runner_can_read_baseline: true
ranking_file_count: 3
actual_replay_count: 3
estimated_unlockable_combo_count: 0
production_impact: NO_PRODUCTION_CHANGE
```

本卡只把 baseline harness 從 3 天 smoke 擴到小窗口 replay。

目標是確認：

```text
production baseline harness 可以穩定產生與 replay 約 20 個交易日。
```

這仍不是全量 replay，不解鎖 `202,176` 格。

## 建議窗口

優先使用：

```text
2026-04-16 ~ 2026-05-15
```

若實際可交易日不是 20 天，允許以 harness 產出的 ranking file count 為準，但必須在 artifact 中說明。

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准跑 `202,176` 格 replay。
- 不准跑超過小窗口。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把小窗口 OK 視為全量解鎖。

## 請讀

- `docs/tasks/2026-06-18_WEEKEND-TRAINING-18_baseline_harness_small_window_replay.md`
- `artifacts/weekend_training/baseline_harness_minimal_replay_smoke_2026-06-18.json`
- `scripts/build_production_baseline_harness.py`
- `scripts/verify_production_baseline_harness.py`
- `scripts/run_baseline_harness_minimal_replay_smoke.py`
- `scripts/verify_baseline_harness_minimal_replay_smoke.py`

## 要做

新增或擴充 runner：

```text
scripts/run_baseline_harness_small_window_replay.py
```

新增 verifier：

```text
scripts/verify_baseline_harness_small_window_replay.py
```

Runner 必須：

- 透過 production baseline harness 產小窗口 staging baseline。
- materialize 到 research-only small-window path，例如：

```text
artifacts/backtest/production_baseline_harness_small_window
```

- 跑小窗口 replay smoke。
- 輸出 artifact，不更新正式 weekend universe progress。

Verifier 必須確認：

```text
small_window_status: OK / BLOCKED
ranking_file_count >= 10
actual_replay_count >= 10
input_baseline_path == artifacts/backtest/production_baseline_harness_small_window
target_production_path_created == false
estimated_unlockable_combo_count == 0
production_impact == NO_PRODUCTION_CHANGE
no PROMOTION_READY
```

## 預期產物

- `artifacts/backtest/production_baseline_harness_small_window/manifest.json`
- `artifacts/weekend_training/baseline_harness_small_window_replay_2026-06-18.json`
- `artifacts/weekend_training/baseline_harness_small_window_replay_2026-06-18.md`
- `artifacts/weekend_training/baseline_harness_small_window_replay_verification_latest.json`

## 驗收標準

```text
small_window_status: OK
runner_can_read_baseline: true
ranking_file_count >= 10
actual_replay_count >= 10
estimated_unlockable_combo_count: 0
target_production_path_created: false
production_impact: NO_PRODUCTION_CHANGE
```

## 完成後下一步

若 OK：

開 `WEEKEND-TRAINING-19_baseline_harness_medium_window_review`。

它可以評估是否擴到 60 ~ 120 個交易日，但仍必須先 review，不直接全量跑。
