# AUTO-TRAINING-13 Sealed Split Policy / Ranking-Only Decision

## 目標

釐清 sealed split contract，並決定 `BIG_BULL family_only` 的正式研究定位：

- `RANKING_ONLY_CANDIDATE`
- `MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE`
- `MONITOR_ONLY`

本卡不是 promotion 卡，不以通過為目標。

## 背景

AUTO-TRAINING-12 已把 blocker 拆清楚：

- ledger traceability：`RESOLVED`
- rollback guard：`RESOLVED`
- sealed stability：`STILL_BLOCKED_MODEL_EVIDENCE`
- sealed OOS metadata：`STILL_BLOCKED_CONTRACT`

sealed OOS fixed split mismatch：

- model metadata split：`2026-01-22 / 2026-02-06 / 2026-05-15`
- current fixed split：`2026-01-23 / 2026-02-09 / 2026-05-18`

這不能用事後挑日期解決。必須先定 policy，再評估候選。

## 必讀輸入

- `artifacts/model_experiments/big_bull_blocker_resolution_2026-06-01.json`
- `artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json`
- `artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json`
- `app/modeling/sealed_oos.py`
- `scripts/run_sealed_oos_gate.py`
- `scripts/verify_sealed_oos_gate.py`
- `scripts/build_model_promotion_review.py`

## 任務範圍

1. sealed split policy：
   - 定義正式 fixed split 的來源。
   - 明確說明 split 是由模型 metadata、固定 config、或 artifact policy 決定。
   - 若兩者不一致，必須輸出 `SPLIT_POLICY_CONFLICT`，不得自動選較佳結果。
2. split mismatch resolution：
   - 若是 artifact 生成時間差造成 one-trading-day drift，補上 contract 說明。
   - 若是候選模型與 gate 使用不同 split，維持 blocked。
   - 不得修改歷史結果讓它看起來通過。
3. ranking-only decision：
   - 使用 AUTO-TRAINING-10 replay / portfolio evidence 判斷 `family_only` 是否可保留為 ranking-only。
   - 若 sealed stability 仍擋 model promotion，必須明確禁止它當 model promotion candidate。
   - 若 ranking evidence 也不足，降級 `MONITOR_ONLY`。
4. promotion adapter consistency：
   - promotion adapter 必須仍回 blocked。
   - 不得輸出 `PROMOTION_READY`。
5. 產出後續卡建議：
   - 若 ranking-only：下一張只做 shadow ranking / production-adjacent dry run。
   - 若 needs more evidence：下一張只補 sealed / replay evidence。
   - 若 monitor：停止該候選主線。

## 非目標

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不改 production ranking score。
- 不啟用 auto / scheduled retrain promotion。
- 不放寬 sealed stability gate。
- 不把 `HIGH_CHOPPY` 當 promotion evidence。
- 不讓 split policy 依結果好壞變動。

## 驗收標準

- sealed split policy 必須輸出：
  - `policy_source`
  - `metadata_split`
  - `fixed_split`
  - `policy_decision`
  - `no_hindsight_confirmation`
- `BIG_BULL family_only` 必須輸出三選一：
  - `RANKING_ONLY_CANDIDATE`
  - `MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE`
  - `MONITOR_ONLY`
- 若輸出 `RANKING_ONLY_CANDIDATE`，必須同時輸出：
  - 不可 model promotion。
  - 不可覆蓋模型。
  - 只能進 shadow ranking / dry-run。
- `promotion_ready` 必須為 false。
- `models/latest_lgbm.pkl` hash unchanged。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_sealed_oos_gate.py
uv run --with-requirements requirements.txt python scripts/build_model_promotion_review.py --date 2026-06-01
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 預期回報格式

```text
sealed_split_policy_status:
policy_source:
metadata_split:
fixed_split:
policy_decision:
big_bull_family_only_decision:
ranking_only_allowed:
model_promotion_allowed:
promotion_adapter_status:
promotion_ready:
models_latest_changed:
next_card:
errors:
```

## 執行結果

產出：

- `artifacts/model_experiments/big_bull_sealed_split_policy_ranking_only_decision_2026-06-01.json`
- `artifacts/model_experiments/big_bull_sealed_split_policy_ranking_only_decision_2026-06-01.md`
- `artifacts/model_experiments/model_promotion_review_big_bull_auto13_2026-06-01.json`

結論：

```text
sealed_split_policy_status: SPLIT_POLICY_CONFLICT
policy_source: artifact_policy: run_sealed_oos_gate builds the fixed split from retrain.sealed_oos config, model horizon/threshold, and the labeled trade-date calendar
metadata_split:
  train_end_date: 2026-01-22
  sealed_start_date: 2026-02-06
  sealed_end_date: 2026-05-15
  embargo_trade_days: 10
  sealed_trade_days: 60
fixed_split:
  train_start_date: 2023-06-02
  train_end_date: 2026-01-23
  embargo_start_date: 2026-01-26
  embargo_end_date: 2026-02-06
  sealed_start_date: 2026-02-09
  sealed_end_date: 2026-05-18
  latest_label_date: 2026-05-18
  embargo_trade_days: 10
  sealed_trade_days: 60
policy_decision: SPLIT_POLICY_CONFLICT
big_bull_family_only_decision: RANKING_ONLY_CANDIDATE
ranking_only_allowed: true
model_promotion_allowed: false
promotion_adapter_status: LEDGER_EVIDENCE_BLOCKED
promotion_ready: false
models_latest_changed: false
next_card: AUTO-TRAINING-14_big_bull_ranking_only_shadow_dry_run
errors: []
```

政策決定：

- 正式 sealed fixed split 來源是 gate artifact policy：`scripts/run_sealed_oos_gate.py` 依 `retrain.sealed_oos` config、model horizon / threshold、labeled trade-date calendar 產生 `split`。
- 模型 metadata split 只能作為候選 artifact 的一致性證據，不能反向決定 fixed split。
- 兩者不一致時輸出 `SPLIT_POLICY_CONFLICT`，不得依結果好壞自動選 split，也不得改歷史 artifact 讓它看起來通過。
- `no_hindsight_confirmation`：split 不由結果品質挑選；sealed period 不用於訓練、調參或校準；conflict 必須擋 model promotion。

定位決定：

- `BIG_BULL family_only` 保留為 `RANKING_ONLY_CANDIDATE`。
- 依據：AUTO-TRAINING-10 中 family_only 為 best ranking follow-up；D+1 top10 portfolio `total_return=0.110633`、`hit_rate=0.608696`、`max_drawdown=-0.062694`。
- 限制：D+2 / D+3 entry sensitivity 轉弱，last12 window 只小幅正報酬；因此下一步只能走 shadow ranking / dry-run，不可 production score。
- 禁止：sealed stability 仍 `MODEL_PROMOTION_BLOCKED`，且 split policy conflict 未解，不能當 model promotion candidate，不能覆蓋 `models/latest_lgbm.pkl`。

下一張建議：

```text
AUTO-TRAINING-14_big_bull_ranking_only_shadow_dry_run
```
