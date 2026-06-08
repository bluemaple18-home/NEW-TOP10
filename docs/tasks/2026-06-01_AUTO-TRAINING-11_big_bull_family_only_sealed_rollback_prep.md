# AUTO-TRAINING-11 BIG_BULL Family-Only Sealed / Rollback Prep

## 目標

把 AUTO-TRAINING-10 的最佳候選 `BIG_BULL family_only` 推進 sealed OOS / rollback gate 前置驗證。

本卡只做 promotion 前的證據準備，不做 production promotion，不覆蓋正式模型。

## 背景

AUTO-TRAINING-10 已收斂：

- `family_only` 是最佳候選。
- `blended_rerank` 表現接近，保留作對照。
- `blended_score` 已淘汰。
- `HIGH_CHOPPY rolling context` 已納入主訓練評估，但 soft feature comparison 為 `MONITOR_ONLY`。
- `HIGH_CHOPPY` 分層診斷保留，不作 promotion evidence。

目前可往下一關，但只能是 sealed / rollback 前置驗證，不能直接升正式模型。

## 必讀輸入

- `artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json`
- `artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.md`
- `artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json`
- `artifacts/model_experiments/model_experiment_ledger.json`
- `scripts/run_sealed_oos_gate.py`
- `scripts/verify_sealed_oos_gate.py`
- `scripts/verify_retrain_rollback.py`
- `scripts/build_model_promotion_review.py`

## 任務範圍

1. 建立 sealed OOS 前置檢查：
   - 使用固定 sealed window，不得用結果回頭挑日期。
   - 明確列出 train / validation / sealed 切分。
   - 確認 `BIG_BULL family_only` 在 sealed window 仍能和 baseline 比較。
2. 建立 rollback gate 前置檢查：
   - 確認候選失敗時不會覆蓋 `models/latest_lgbm.pkl`。
   - 確認 promotion guard 仍會阻擋未通過候選。
   - 確認 automation readiness 仍只允許 training review，不允許 promotion。
3. 建立候選追溯：
   - ledger id 必須能連到 AUTO-TRAINING-10 artifact。
   - promotion adapter 若缺 evidence，必須維持 `MISSING_LEDGER_EVIDENCE` 或 blocked 狀態。
4. 保留對照：
   - `blended_rerank` 只作 fallback / comparison。
   - 若 `family_only` sealed 表現不穩，不得用 `blended_rerank` 偷渡 promotion。
5. 輸出下一階段判斷：
   - `READY_FOR_SEALED_OOS_REVIEW`
   - `NEEDS_MORE_REPLAY`
   - `MONITOR_ONLY`
   - 或 `BLOCKED`

## 非目標

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不產出 `PROMOTION_READY`。
- 不啟用 scheduled / auto retrain promotion。
- 不恢復 `blended_score`。
- 不讓 `HIGH_CHOPPY` 成為 promotion evidence。
- 不新增正式 base regime 或 family tag。
- 不改 production ranking score。

## 驗收標準

- sealed OOS 前置 artifact 明確輸出：
  - candidate。
  - baseline。
  - sealed window。
  - no-hindsight policy。
  - pass / fail / blocked reason。
- rollback 前置驗證明確輸出：
  - `models/latest_lgbm.pkl` hash before / after。
  - promotion guard status。
  - rollback readiness。
- ledger / promotion review 明確顯示候選仍不可 production promotion。
- `training_launch_ready` 可維持 true，但 `promotion_ready` 必須為 false。
- 若任何必要證據缺失，本卡必須標 `BLOCKED`，不可用 warning 帶過。

## 2026-06-01 執行結果

```text
candidate: BIG_BULL family_only
baseline: global_baseline
sealed_oos_prep_status: BLOCKED
sealed_window: 2025-12-10 ~ 2026-05-15 / 100 trade days
rollback_prep_status: OK
ledger_traceability: BLOCKED
promotion_adapter_status: LEDGER_EVIDENCE_BLOCKED
training_launch_ready: false
promotion_ready: false
models_latest_changed: false
next_gate: BLOCKED
errors:
- regime family sealed stability blocks model promotion
- current model sealed OOS gate failed fixed split metadata check
- BIG_BULL ledger entries do not trace to AUTO-TRAINING-10 artifact
```

關鍵判定：

- `BIG_BULL family_only` 仍只保留 `RANKING_FOLLOWUP_CANDIDATE`，不得進 production promotion。
- 固定 100d regime-family sealed replay 驗證通過，但 sealed stability 為 `MODEL_PROMOTION_BLOCKED`。
- 正式 sealed OOS gate 對 current model 產出 `FAILED`：模型 metadata 的 sealed split 日期與目前固定 split 不一致。
- rollback injection 通過，且 `models/latest_lgbm.pkl` hash 前後一致：`76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675`。
- promotion adapter 對 `BIG_BULL` / `training_policy:BIG_BULL:ranking-replay-followup` 均維持 `LEDGER_EVIDENCE_BLOCKED`。
- ledger 目前沒有 BIG_BULL entry 追溯到 AUTO-TRAINING-10 artifact，因此本卡必須 `BLOCKED`，不可用 warning 帶過。
- `HIGH_CHOPPY rolling context` 保留分層診斷，不作 promotion evidence。

主要證據：

- `artifacts/model_experiments/big_bull_family_only_sealed_rollback_prep_2026-06-01.json`
- `artifacts/model_experiments/big_bull_family_only_sealed_rollback_prep_2026-06-01.md`
- `artifacts/model_experiments/regime_family_sealed_replay_big_bull_100d_2026-06-01.json`
- `artifacts/model_experiments/regime_family_sealed_replay_big_bull_100d_verification_latest.json`
- `artifacts/sealed_oos_report_auto11_2026-06-01.json`
- `artifacts/retrain_rollback_injection_2026-06-01.json`
- `artifacts/model_experiments/model_promotion_review_big_bull_auto11_2026-06-01.json`
- `artifacts/model_experiments/model_promotion_review_big_bull_ranking_followup_auto11_2026-06-01.json`
- `artifacts/training_automation_readiness_2026-06-01.json`

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
uv run --with-requirements requirements.txt python scripts/build_model_promotion_review.py --date 2026-06-01
git diff --check
```

若要跑 rollback injection，必須先確認它不會修改正式模型檔；若腳本會建立暫存備份，也必須回報 hash before / after。

## 預期回報格式

```text
candidate:
baseline:
sealed_oos_prep_status:
sealed_window:
rollback_prep_status:
ledger_traceability:
promotion_adapter_status:
training_launch_ready:
promotion_ready:
models_latest_changed:
next_gate:
errors:
```
