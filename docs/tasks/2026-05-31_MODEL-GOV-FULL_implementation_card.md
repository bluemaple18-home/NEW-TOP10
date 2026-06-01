# MODEL-GOV-FULL full implementation card

## 任務ID

`MODEL-GOV-FULL`

## 卡片類型｜派工對象

Full Feature Implementation / Model Governance｜Codex

## 請先讀

- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`
- `docs/tasks/2026-05-31_MODEL-GOV-00_experiment_ledger_cards.md`
- `docs/tasks/2026-05-31_MODEL-GOV-01_experiment_ledger_schema.md`
- `docs/tasks/2026-05-31_MODEL-GOV-02_experiment_ledger_cli.md`
- `docs/tasks/2026-05-31_MODEL-GOV-03_experiment_ledger_verifier.md`
- `docs/tasks/2026-05-31_MODEL-GOV-04_research_flow_integration.md`
- `docs/tasks/2026-05-31_MODEL-GOV-05_result_report_acceptance.md`
- `docs/tasks/2026-05-31_MODEL-GOV-06_governance_surfacing.md`
- `docs/tasks/2026-05-31_MODEL-GOV-07_backfill_migration.md`
- `docs/tasks/2026-05-31_MODEL-GOV-08_promotion_review_contract.md`

## 任務目的

把 `MODEL-GOV 00~08` 收斂成一套完整、可驗證、可長期營運的 model experiment ledger 系統。

Ledger 的定位是長期狀態記憶層與 evidence adapter，只回答：

- 實驗假設是什麼。
- baseline / decision policy / trigger 是否預先固定。
- 到期後 result report 的 verdict 是什麼。
- 候選模型是否能追溯到已驗收的研究證據。

Ledger 不得成為新的 gate、acceptance engine、promotion engine 或第二套 model experiment pipeline。

## 最高邊界

- 不取代 sealed OOS。
- 不取代 replay / portfolio replay。
- 不取代 rollback verifier。
- 不取代 model group acceptance。
- 不取代 human review。
- 不輸出 `PROMOTION_READY`。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不修改 production ranking。
- 不新增第二套 acceptance report。
- 不讓 ledger verdict 自動升版模型。

Promotion evidence adapter 只能輸出：

- `MISSING_LEDGER_EVIDENCE`
- `LEDGER_EVIDENCE_BLOCKED`
- `LEDGER_EVIDENCE_OK`

其中 `LEDGER_EVIDENCE_OK` 只代表研究假設可追溯且已驗收，不代表模型可上線。

## 系統分層

```text
model_exp_plan_*.json
        ↓
model_exp_run_manifest_*.json
        ↓
model_exp_result_report_*.json   ← result source of truth
        ↓
model_experiment_ledger.json     ← long-term state memory
        ↓
model_promotion_review_*.json    ← evidence adapter only

sealed OOS / replay / rollback / model group acceptance
        ↓
正式升版 gate，ledger 不取代
```

## 交付範圍

### 1. Ledger schema

新增：

- `docs/architecture/MODEL_EXPERIMENT_LEDGER.md`

固定：

- ledger path：`artifacts/model_experiments/model_experiment_ledger.json`
- schema version：`model-experiment-ledger.v1`
- ledger role：`state_memory`
- experiment id：`<type>:<candidate>:<slug>`
- status：`pending`、`passed`、`failed`、`partial`、`expired`、`stale`、`superseded`
- type：`feature`、`label`、`horizon`、`universe`、`overlay`、`training_policy`

必要欄位：

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

### 2. Ledger CLI

新增：

- `scripts/model_experiment_ledger.py`

子命令：

- `add`
- `list`
- `due`
- `resolve`
- `reschedule`
- `supersede`
- `stats`
- `validate`

要求：

- deterministic output。
- atomic write。
- 支援 `--ledger`。
- 支援 `--asof YYYY-MM-DD`。
- repo-relative path only。
- 同 id 不同 hypothesis 必須 collision fail-fast。
- `due` 可把超過寬限期的 pending 標成 `expired`。

### 3. Ledger verifier

新增：

- `scripts/verify_model_experiment_ledger.py`

只檢查 ledger integrity：

- schema version。
- ledger role。
- id 唯一。
- status 合法。
- pending 有 trigger。
- resolved 有 history verdict。
- baseline 不可空。
- decision policy 有 pass/fail/partial 規則。
- source artifacts 必須是 repo-relative path。
- history append-only 語意。
- 不允許 `promotion_ready=true`。
- 不允許 `production_promotion_allowed=true`。

明確不檢查：

- no-hindsight。
- sealed OOS 是否通過。
- replay 是否通過。
- rollback 是否通過。
- production promotion 是否可放行。

### 4. Research flow integration

修改：

- `scripts/run_model_research_flow.py`
- `scripts/build_model_experiment_plan.py`
- `scripts/build_model_experiment_run_manifest.py`
- `scripts/verify_model_research_flow.py`
- `scripts/verify_model_experiment_plan.py`
- `scripts/verify_model_experiment_run_manifest.py`

要求：

- plan 每個 experiment 可映射 stable `ledger_id`。
- run manifest 保留 `ledger_id`。
- research flow default-on 登錄 ledger，但只寫 research artifact。
- ledger collision 必須 fail-fast。
- flow summary 輸出：
  - `ledger_updates`
  - `ledger_pending_count`
  - `ledger_collisions`
  - `ledger_verification_status`

不得：

- 觸發正式 retrain。
- 修改 `models/latest_lgbm.pkl`。
- 修改 production ranking。

### 5. Result report resolver

新增或擴充薄 adapter：

- `scripts/build_model_experiment_result_report.py`
- `scripts/verify_model_experiment_result_report.py`

Result report 是 verdict source of truth。Ledger resolver 只同步狀態，不重新計算 pass/fail。

Result report 需可提供：

- `ledger_id`
- `hypothesis`
- `baseline`
- `decision_policy`
- `actual_metrics`
- `verdict`
- `next_action`
- `promotion_allowed=false`

狀態映射：

- `passed`：主要 metric 達標，風險 metric 未破壞，必要 evidence 完整。
- `failed`：主要 metric 未達標，或風險 metric 明確破壞。
- `partial`：主要 metric 有改善但 evidence 不完整，或不同 window 結論衝突。
- `expired`：到期後超過設定天數仍未有可驗收 evidence。

### 6. Governance surfacing

新增：

- `scripts/build_model_experiment_ledger_stats.py`

修改：

- `scripts/generate_daily_report.py`
- `scripts/build_weekend_research_decision_report.py`

輸出摘要即可，不塞完整 ledger：

- pending due soon。
- failed / partial since last run。
- expired count。
- candidate hit rate。
- repeated failed hypothesis family。
- next research priorities。
- blocked promotion reasons。

### 7. Backfill migration

新增：

- `scripts/backfill_model_experiment_ledger.py`

來源：

- `artifacts/model_experiments/feature_experiment_gate_*.json`
- `artifacts/model_experiments/shadow_feature_experiment_*.json`
- `artifacts/model_experiments/model_exp_plan_*.json`
- `artifacts/model_experiments/model_exp_run_manifest_*.json`
- `artifacts/model_experiments/model_exp_result_report_*.json`

要求：

- dry-run 支援。
- 不修改舊 artifact。
- 舊資料缺 verdict 時標 `stale` 或 `partial`。
- 不把 monitor-only 舊結論升級成 passed。
- 輸出 backfill summary。

### 8. Promotion evidence adapter

新增：

- `scripts/build_model_promotion_review.py`
- 如已有可延伸腳本，保持薄 adapter，不接管正式升版。

輸出：

- `artifacts/model_experiments/model_promotion_review_YYYY-MM-DD.json`

檢查：

- candidate model 對應 ledger entry 存在。
- ledger status 是 `passed`，或存在明確 manual override reason。
- 無 unresolved collision。
- 無 expired required experiment。
- source artifacts 可追溯到 result report / run manifest。

只允許輸出：

- `MISSING_LEDGER_EVIDENCE`
- `LEDGER_EVIDENCE_BLOCKED`
- `LEDGER_EVIDENCE_OK`

不得輸出：

- `PROMOTION_READY`
- `AUTO_PROMOTE`
- `MODEL_APPROVED`

## 建議實作順序

### Checkpoint A：ledger core

1. `docs/architecture/MODEL_EXPERIMENT_LEDGER.md`
2. `scripts/model_experiment_ledger.py`
3. `scripts/verify_model_experiment_ledger.py`

完成後必跑：

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/model_experiment_ledger.py scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --self-test
uv run --with-requirements requirements.txt python scripts/model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json validate
git diff --check
```

### Checkpoint B：research flow + resolver

1. `build_model_experiment_plan.py`
2. `build_model_experiment_run_manifest.py`
3. `run_model_research_flow.py`
4. `build_model_experiment_result_report.py`
5. result report → ledger resolver

完成後必跑：

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/run_model_research_flow.py scripts/build_model_experiment_plan.py scripts/build_model_experiment_run_manifest.py scripts/build_model_experiment_result_report.py scripts/verify_model_research_flow.py scripts/verify_model_experiment_plan.py scripts/verify_model_experiment_run_manifest.py scripts/verify_model_experiment_result_report.py
uv run --with-requirements requirements.txt python scripts/run_model_research_flow.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_research_flow.py --artifact artifacts/model_experiments/model_research_flow_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check
```

### Checkpoint C：surfacing + backfill + promotion evidence

1. `build_model_experiment_ledger_stats.py`
2. report surfacing
3. `backfill_model_experiment_ledger.py`
4. `build_model_promotion_review.py`

完成後必跑：

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/build_model_experiment_ledger_stats.py scripts/backfill_model_experiment_ledger.py scripts/build_model_promotion_review.py scripts/generate_daily_report.py scripts/build_weekend_research_decision_report.py
uv run --with-requirements requirements.txt python scripts/build_model_experiment_ledger_stats.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/backfill_model_experiment_ledger.py --date YYYY-MM-DD --dry-run
uv run --with-requirements requirements.txt python scripts/build_model_promotion_review.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check
```

## 回報格式

完成後請回報：

```text
MODEL-GOV-FULL status:
checkpoint A:
checkpoint B:
checkpoint C:
ledger path:
ledger entries:
pending:
passed:
failed:
partial:
expired:
stale:
promotion adapter status:
forbidden outputs present: yes/no
sealed/replay/rollback replaced: yes/no
artifacts:
tests:
errors:
```

## 最終驗收

- `MODEL-GOV 00~08` 均有對應實作或明確薄 adapter。
- Ledger 可新增、列出、到期、驗收、改期、取代、統計、驗證。
- Ledger verifier self-test 會擋壞資料。
- Research flow 可自動登錄 ledger id。
- Result report 可同步 verdict 回 ledger。
- Daily/weekend/research report 可露出 ledger summary。
- Backfill 可 dry-run 並建立歷史治理基線。
- Promotion evidence adapter 可追溯 ledger evidence，但不得輸出 `PROMOTION_READY`。
- 所有命令與文件使用 repo-relative path。
- `git diff --check` 通過。
