# WEEKEND-TRAINING-17 baseline harness minimal replay smoke

## 任務目的

承接 `WEEKEND-TRAINING-16`：

```text
materialization_status: OK
research_only: true
ranking_file_count: 3
dates: 2026-05-13, 2026-05-14, 2026-05-15
target_production_path_created: false
estimated_unlockable_combo_count: 0
production_impact: NO_PRODUCTION_CHANGE
```

本卡只做最小 replay smoke，確認 research-only baseline 可以被 replay runner 正確讀取。

這不是全量 replay，不解鎖 202,176 格。

## 允許輸入

Baseline：

```text
artifacts/backtest/production_baseline_harness_smoke
```

允許日期：

```text
2026-05-13
2026-05-14
2026-05-15
```

## 明確禁止

- 不准建立 `artifacts/backtest/production`。
- 不准跑超過這 3 天。
- 不准跑 `202,176` 格 replay。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准把 replay smoke OK 視為全量解鎖。

## 請讀

- `docs/tasks/2026-06-18_WEEKEND-TRAINING-17_baseline_harness_minimal_replay_smoke.md`
- `artifacts/backtest/production_baseline_harness_smoke/manifest.json`
- `artifacts/weekend_training/research_only_baseline_materialization_smoke_2026-06-18.json`
- `scripts/run_capital_aware_replay.py`
- `scripts/materialize_research_only_production_baseline_smoke.py`
- `scripts/verify_research_only_production_baseline_smoke.py`

## 要做

新增 minimal replay smoke builder：

```text
scripts/run_baseline_harness_minimal_replay_smoke.py
```

新增 verifier：

```text
scripts/verify_baseline_harness_minimal_replay_smoke.py
```

Builder 必須：

- 讀 research-only baseline manifest。
- 確認只有 3 天 ranking。
- 對 replay runner 做最小 smoke。
- 若缺 outcome / price data，必須輸出 `BLOCKED_DATA_GAP`，不得補假資料。
- 輸出 replay smoke artifact。

Verifier 必須確認：

```text
replay_smoke_status: OK / BLOCKED_DATA_GAP
input_baseline_path == artifacts/backtest/production_baseline_harness_smoke
ranking_file_count == 3
date_range == 2026-05-13 ~ 2026-05-15
target_production_path_created == false
estimated_unlockable_combo_count == 0
production_impact == NO_PRODUCTION_CHANGE
no PROMOTION_READY
```

## 預期產物

- `artifacts/weekend_training/baseline_harness_minimal_replay_smoke_2026-06-18.json`
- `artifacts/weekend_training/baseline_harness_minimal_replay_smoke_2026-06-18.md`
- `artifacts/weekend_training/baseline_harness_minimal_replay_smoke_verification_latest.json`

## 驗收標準

```text
replay_smoke_status: OK / BLOCKED_DATA_GAP
runner_can_read_baseline: true
ranking_file_count: 3
actual_replay_count <= 3
estimated_unlockable_combo_count: 0
target_production_path_created: false
production_impact: NO_PRODUCTION_CHANGE
```

## 完成後下一步

若 `BLOCKED_DATA_GAP`：

```text
補 replay 所需資料契約，不跑全量。
```

若 `OK`：

```text
WEEKEND-TRAINING-18_baseline_harness_small_window_replay
```

只允許擴到小窗口，例如 20 個交易日；仍不准直接跑 202,176 格。
