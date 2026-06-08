# AUTO-TRAINING-12 BIG_BULL Blocker Resolution

## 目標

收斂 AUTO-TRAINING-11 擋下 `BIG_BULL family_only` 的三個 blocker，判斷哪些是模型穩定性問題，哪些是治理 / metadata contract 問題。

本卡只做 blocker resolution，不做 production promotion。

## 背景

AUTO-TRAINING-11 正確輸出 `BLOCKED`：

- candidate：`BIG_BULL family_only`
- baseline：`global_baseline`
- sealed window：`2025-12-10 ~ 2026-05-15`，100 trade days
- rollback guard：OK
- promotion adapter：`LEDGER_EVIDENCE_BLOCKED`
- `models/latest_lgbm.pkl`：未變

硬 blocker：

1. regime family sealed stability blocks model promotion。
2. current model sealed OOS gate failed fixed split metadata check。
3. BIG_BULL ledger entries do not trace to AUTO-TRAINING-10 artifact。

## 任務範圍

1. sealed stability 診斷：
   - 保留既有 sealed stability gate，不放寬門檻。
   - 拆出是 AUC 穩定性問題、TopN 問題、window 問題，還是 candidate 不適合 model promotion。
   - 若只適合 ranking follow-up，明確維持 `RANKING_FOLLOWUP_CANDIDATE`，不得升級。
2. sealed OOS metadata contract 修正：
   - 查 fixed split metadata check failed 的欄位缺口。
   - 補 artifact 生成或 verifier contract，讓 metadata 足以驗證 no-hindsight split。
   - 不得用補假欄位讓 gate 通過；必須能追到實際 train / validation / sealed 切分。
3. BIG_BULL ledger traceability 補鏈：
   - ledger entry 必須追到 AUTO-TRAINING-10 artifact。
   - `BIG_BULL family_only`、`blended_rerank`、`HIGH_CHOPPY MONITOR_ONLY` 的 lineage 必須分清楚。
   - 若候選仍 blocked，promotion adapter 必須繼續回 blocked 狀態。
4. rollback guard 回歸：
   - 確認 blocker resolution 不會讓 rollback guard 退化。
   - `models/latest_lgbm.pkl` hash before / after 必須不變。

## 非目標

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不輸出 `PROMOTION_READY`。
- 不放寬 sealed stability gate。
- 不用 metadata 修正掩蓋模型穩定性不足。
- 不讓 `blended_rerank` 或 `HIGH_CHOPPY` 偷渡 promotion。
- 不改 production ranking score。
- 不啟用 auto / scheduled retrain promotion。

## 驗收標準

- 三個 blocker 必須逐一輸出狀態：
  - `RESOLVED`
  - `STILL_BLOCKED_MODEL_EVIDENCE`
  - `STILL_BLOCKED_CONTRACT`
  - `NOT_APPLICABLE`
- sealed stability 若仍擋 promotion，必須明確說是模型證據不足，不可被 ledger / metadata 修正覆蓋。
- sealed OOS metadata 修正後，verifier 必須能說明使用哪個 fixed split，不得只回 OK。
- ledger traceability 修正後，promotion adapter 仍不得輸出 promotion-ready。
- readiness 可以回到 training launch ready，但 promotion 必須維持 false。
- `models/latest_lgbm.pkl` hash unchanged。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
uv run --with-requirements requirements.txt python scripts/verify_sealed_oos_gate.py
uv run --with-requirements requirements.txt python scripts/verify_retrain_rollback.py
uv run --with-requirements requirements.txt python scripts/build_model_promotion_review.py --date 2026-06-01
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 預期回報格式

```text
sealed_stability_blocker:
sealed_oos_metadata_blocker:
ledger_traceability_blocker:
rollback_guard:
training_launch_ready:
promotion_ready:
promotion_adapter_status:
models_latest_changed:
next_gate:
errors:
```

## 執行結果

產出：

- `artifacts/model_experiments/big_bull_blocker_resolution_2026-06-01.json`
- `artifacts/model_experiments/big_bull_blocker_resolution_2026-06-01.md`
- `artifacts/sealed_oos_report_auto12_2026-06-01.json`
- `artifacts/model_experiments/model_promotion_review_big_bull_auto12_2026-06-01.json`
- `artifacts/model_experiments/model_promotion_review_big_bull_ranking_followup_auto12_2026-06-01.json`

結論：

```text
sealed_stability_blocker: STILL_BLOCKED_MODEL_EVIDENCE
sealed_oos_metadata_blocker: STILL_BLOCKED_CONTRACT
ledger_traceability_blocker: RESOLVED
rollback_guard: RESOLVED
training_launch_ready: false
promotion_ready: false
promotion_adapter_status: BLOCKED
models_latest_changed: false
next_gate: STILL_BLOCKED_MODEL_EVIDENCE
errors:
  - sealed_stability_blocker: STILL_BLOCKED_MODEL_EVIDENCE
  - sealed_oos_metadata_blocker: STILL_BLOCKED_CONTRACT
```

診斷摘要：

- sealed stability：維持 `MODEL_PROMOTION_BLOCKED` / `RANKING_FOLLOWUP_CANDIDATE`。AUC delta 在 40d / 60d / 80d / 100d sealed windows 全部為負，TopN 整體有 uplift 但 40d window 落後 baseline；這是模型證據不足，不能被 ledger 或 metadata 修正覆蓋。
- sealed OOS metadata：verifier 已輸出結構化 `actual` / `expected` 與 fixed split path。metadata 存在且 `no_train_overlap` OK，但目前模型 payload 的 `train_end_date=2026-01-22`、`sealed_start_date=2026-02-06`、`sealed_end_date=2026-05-15`，與 fixed split `2026-01-23`、`2026-02-09`、`2026-05-18` 不一致；仍是 contract blocker，沒有用假欄位讓 gate 通過。
- ledger traceability：`training_policy:BIG_BULL:ranking-replay-followup` 已補鏈到 AUTO-TRAINING-10 extension artifact，狀態仍為 `pending`，不構成 promotion evidence。
- lineage：`BIG_BULL family_only` 是主 ranking follow-up candidate；`blended_rerank` 僅 comparison；`HIGH_CHOPPY rolling context` 僅 soft feature + stratified diagnostic，`soft_feature_decision=MONITOR_ONLY`，不影響 promotion qualification。
- promotion adapter：AUTO12 兩份 review 仍為 `LEDGER_EVIDENCE_BLOCKED`，符合不得 promotion 的邊界。
- `models/latest_lgbm.pkl` hash 前後皆為 `76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675`。

驗證：

```text
python -m py_compile: OK
verify_model_experiment_ledger: OK
verify_sealed_oos_gate: OK
verify_retrain_rollback: OK
run_sealed_oos_gate auto12: SEALED_OOS_GATE_FAILED（預期；fixed split metadata mismatch）
build_model_promotion_review BIG_BULL: LEDGER_EVIDENCE_BLOCKED
build_model_promotion_review ranking-followup: LEDGER_EVIDENCE_BLOCKED
verify_training_automation_readiness: FAILED（預期；model.group_acceptance）
```
