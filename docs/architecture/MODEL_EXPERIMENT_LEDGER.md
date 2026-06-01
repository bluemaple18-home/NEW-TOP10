# Model Experiment Ledger

## 定位

`model_experiment_ledger` 是模型研究的長期狀態記憶層與 promotion evidence adapter。它記錄每個預註冊模型實驗的假設、baseline、驗收條件、到期日、最後 verdict 與來源 artifact。

它不是新的模型升版 gate，不取代 sealed OOS、replay、rollback verifier、model group acceptance 或 human review，也不得輸出 `PROMOTION_READY`。

## 儲存位置

- Ledger：`artifacts/model_experiments/model_experiment_ledger.json`
- Schema version：`model-experiment-ledger.v1`
- Ledger role：`state_memory`

## Experiment ID

格式固定：

```text
<type>:<candidate>:<slug>
```

範例：

```text
feature:candidate_persistence:persistence-only
overlay:portfolio_risk_overlay:risk-overlay-only
training_policy:combined_conservative:candidate-persistence-regime-combined
```

同一個 id 只能代表同一個 hypothesis。若同 id 出現不同 hypothesis，工具必須 fail-fast，不得靜默覆蓋或改 slug。

## 狀態

- `pending`：已預註冊，等待驗收 evidence。
- `passed`：result report 判定主要 metric 達標、風險 metric 未破壞、必要 evidence 完整。
- `failed`：result report 判定主要 metric 未達標，或風險 metric 明確破壞。
- `partial`：有部分改善但 evidence 不完整，或不同 window 結論衝突。
- `expired`：到期超過寬限期仍無可驗收 evidence。
- `stale`：歷史 artifact 可追溯但缺少完整 verdict，需人工判讀。
- `superseded`：已被新 id 或新假設取代。

## 類型

- `feature`
- `label`
- `horizon`
- `universe`
- `overlay`
- `training_policy`

## Ledger 結構

```json
{
  "schema_version": "model-experiment-ledger.v1",
  "ledger_role": "state_memory",
  "production_promotion_allowed": false,
  "updated": "YYYY-MM-DDTHH:MM:SS+00:00",
  "experiments": []
}
```

## Entry 必要欄位

- `id`
- `type`
- `candidate`
- `slug`
- `hypothesis`
- `falsification`
- `baseline`
- `target_metrics`
- `risk_metrics`
- `decision_policy`
- `evidence_requirements`
- `trigger`
- `status`
- `created`
- `updated`
- `source_artifacts`
- `history`
- `production_promotion_allowed=false`

`decision_policy` 必須包含 `pass`、`fail`、`partial` 三組預註冊規則。`source_artifacts` 必須只使用 repo-relative path。

## Source of Truth 分工

```text
model_exp_plan_*.json
        ↓
model_exp_run_manifest_*.json
        ↓
model_exp_result_report_*.json   ← result verdict source of truth
        ↓
model_experiment_ledger.json     ← long-term state memory
        ↓
model_promotion_review_*.json    ← evidence adapter only

sealed OOS / replay / rollback / model group acceptance
        ↓
正式升版 gate，ledger 不取代
```

Ledger resolver 只能同步 result report 的 verdict，不重新計算 pass/fail，也不能把 `passed` 轉成 production promotion 授權。

## Promotion Evidence Adapter

Adapter 只能輸出：

- `MISSING_LEDGER_EVIDENCE`
- `LEDGER_EVIDENCE_BLOCKED`
- `LEDGER_EVIDENCE_OK`

`LEDGER_EVIDENCE_OK` 只代表候選模型可追溯到已驗收的研究假設，不代表模型可上線。

禁止輸出：

- `PROMOTION_READY`
- `AUTO_PROMOTE`
- `MODEL_APPROVED`
