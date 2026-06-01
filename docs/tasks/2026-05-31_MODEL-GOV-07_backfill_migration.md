# MODEL-GOV-07 backfill migration

## 任務卡

任務ID：MODEL-GOV-07
卡片類型｜派工對象：Migration / Model Governance｜Codex
請讀：`docs/tasks/2026-05-30_MODEL-EXP-01_offline_experiment_plan.md`、`artifacts/model_experiments/`、`scripts/model_experiment_ledger.py`、`scripts/verify_model_experiment_ledger.py`
任務目的：把既有 model experiment / shadow feature / promotion gate artifacts 回填到 experiment ledger，建立正式上線前的歷史治理基線。
證據路徑：`artifacts/model_experiments/model_experiment_ledger_backfill_YYYY-MM-DD.json`、`artifacts/model_experiments/model_experiment_ledger.json`

## 交付內容

- 新增 `scripts/backfill_model_experiment_ledger.py`。
- 從既有 artifacts 推導 ledger entries：
  - `feature_experiment_gate_YYYY-MM-DD.json`
  - `shadow_feature_experiment_YYYY-MM-DD.json`
  - `model_exp_plan_YYYY-MM-DD.json`
  - `model_exp_run_manifest_YYYY-MM-DD.json`
  - `model_exp_result_report_YYYY-MM-DD.json`
- Backfill 必須保留 `source_artifacts`，並標記 `source=backfill`。
- 無法完整判斷 verdict 的舊資料，標成 `stale` 或 `partial`，不得補假 passed。
- 產生 backfill summary：新增幾筆、跳過幾筆、碰撞幾筆、需要人工判讀幾筆。

## 不可做

- 不修改舊 artifact。
- 不把舊 artifact 的 monitor-only 結論升級成 passed。
- 不重跑任何模型實驗。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/backfill_model_experiment_ledger.py scripts/model_experiment_ledger.py scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/backfill_model_experiment_ledger.py --date YYYY-MM-DD --dry-run
uv run --with-requirements requirements.txt python scripts/backfill_model_experiment_ledger.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check -- scripts/backfill_model_experiment_ledger.py docs/tasks/2026-05-31_MODEL-GOV-07_backfill_migration.md
```

## TDD Loop

- RED：用 synthetic old artifacts 測 backfill 對 missing field、monitor-only、collision 的處理。
- GREEN：完成 dry-run 與正式寫入。
- Refactor：把 artifact parser 分成小函式，便於後續支援新 artifact。
