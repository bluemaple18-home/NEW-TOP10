# MODEL-GOV-01 experiment ledger schema

## 任務卡

任務ID：MODEL-GOV-01
卡片類型｜派工對象：Data Contract / Model Governance｜Codex
請讀：`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`、`docs/tasks/2026-05-31_MODEL-GOV-00_experiment_ledger_cards.md`、`scripts/build_model_experiment_plan.py`、`scripts/build_model_experiment_run_manifest.py`
任務目的：定義 TOP10new 的 `model_experiment_ledger` schema，涵蓋 feature / label / horizon / universe / overlay 實驗的預註冊假設、驗收條件、狀態與歷史紀錄。
證據路徑：`docs/tasks/2026-05-31_MODEL-GOV-01_experiment_ledger_schema.md`、`docs/architecture/MODEL_EXPERIMENT_LEDGER.md`

## 交付內容

- 新增 `docs/architecture/MODEL_EXPERIMENT_LEDGER.md`。
- 定義 ledger 儲存位置：`artifacts/model_experiments/model_experiment_ledger.json`。
- 定義 schema version：`model-experiment-ledger.v1`。
- 定義 experiment id：`<layer>:<candidate>:<slug>`，例如 `feature:candidate_persistence:streak_20d_top10`.
- 定義 status：`pending`、`passed`、`failed`、`partial`、`expired`、`stale`、`superseded`。
- 定義 experiment type：`feature`、`label`、`horizon`、`universe`、`overlay`、`training_policy`。
- 定義必要欄位：
  - `id`
  - `type`
  - `candidate`
  - `hypothesis`
  - `falsification`
  - `baseline`
  - `target_metrics`
  - `decision_policy`
  - `evidence_requirements`
  - `trigger`
  - `status`
  - `created`
  - `updated`
  - `source_artifacts`
  - `history`

## Schema 原則

- `hypothesis` 必須是一句可驗證命題，不可寫「看起來更好」。
- `decision_policy` 必須在實驗前固定，不得從實驗結果倒推門檻。
- `baseline` 必須指到 artifact 或已命名 baseline；不得只寫「current」。
- `target_metrics` 至少包含一個主要 metric 與一個風險 metric。
- `evidence_requirements` 必須標明是否需要 sealed OOS、production replay、walk-forward、portfolio replay。
- `history` 只 append，不覆蓋。

## 不可做

- 不實作 CLI。
- 不寫 verifier。
- 不接 `run_model_research_flow.py`。
- 不改既有 experiment artifact schema，除非另開相容性卡。

## 驗證

```bash
git diff --check -- docs/architecture/MODEL_EXPERIMENT_LEDGER.md docs/tasks/2026-05-31_MODEL-GOV-01_experiment_ledger_schema.md
```

## TDD 備註

本卡是文件契約，不跑 TDD；下一卡開始將 schema 轉成可測 CLI 與 verifier。
