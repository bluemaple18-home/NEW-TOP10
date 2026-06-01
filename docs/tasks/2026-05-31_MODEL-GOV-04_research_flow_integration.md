# MODEL-GOV-04 research flow integration

## 任務卡

任務ID：MODEL-GOV-04
卡片類型｜派工對象：Pipeline Integration / Model Governance｜Codex
請讀：`scripts/run_model_research_flow.py`、`scripts/build_model_experiment_plan.py`、`scripts/build_model_experiment_run_manifest.py`、`scripts/model_experiment_ledger.py`
任務目的：把 experiment ledger 接到 model research flow，使預註冊 experiment 在產生 plan / run manifest / result report 時自動登錄、更新或標記待驗收。
證據路徑：`artifacts/model_experiments/model_research_flow_YYYY-MM-DD.json`、`artifacts/model_experiments/model_experiment_ledger.json`

## 交付內容

- `run_model_research_flow.py` 增加 default-on 的 ledger integration，但只寫研究 artifact。
- `build_model_experiment_plan.py` 產出的每個 experiment 必須可映射到 ledger id。
- `build_model_experiment_run_manifest.py` 必須保留 `ledger_id`。
- 若 `model_experiment_ledger.py add` 回 collision，flow 必須 fail-fast，不可改 slug 靜默繼續。
- Flow summary 必須輸出：
  - `ledger_updates`
  - `ledger_pending_count`
  - `ledger_collisions`
  - `ledger_verification_status`

## 行為要求

- 初次看到 experiment：登錄 `pending`。
- 同一 experiment policy 更新且 hypothesis 相似：更新 trigger / source artifact。
- 同一 id 但 hypothesis 不同：fail。
- 既有 resolved experiment 被重新跑：必須另開 slug 或走 supersede，不可覆蓋歷史。

## 不可做

- 不讓 ledger integration 觸發正式 retrain。
- 不用 ledger 自動放行 blocked candidate。
- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking output。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/run_model_research_flow.py scripts/build_model_experiment_plan.py scripts/build_model_experiment_run_manifest.py scripts/model_experiment_ledger.py scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/run_model_research_flow.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_research_flow.py --artifact artifacts/model_experiments/model_research_flow_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check -- scripts/run_model_research_flow.py scripts/build_model_experiment_plan.py scripts/build_model_experiment_run_manifest.py docs/tasks/2026-05-31_MODEL-GOV-04_research_flow_integration.md
```

## TDD Loop

- RED：用 synthetic plan/manifest 測 `ledger_id` 缺失、collision、resolved overwrite。
- GREEN：串接 CLI 並讓 flow fail-fast。
- Refactor：把 ledger 呼叫包成小 helper，避免每個 script 重複 shell out。
