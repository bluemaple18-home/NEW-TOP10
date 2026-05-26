# MODEL-OPS-04 sealed OOS promotion gate

## 卡片

任務ID：MODEL-OPS-04  
卡片類型｜派工對象：Model Ops / Sealed OOS｜Codex  
請讀：`app/agent_b_modeling.py`、`app/modeling/sealed_oos.py`、`scripts/run_sealed_oos_gate.py`、`scripts/run_automation.py`、`scripts/verify_sealed_oos_gate.py`、`scripts/verify_retrain_rollback.py`  
任務目的：在手動/自動重訓流程加入封閉 OOS 視窗，確保最近成熟標籤交易日不進 train/tune/calibration；新模型必須通過 sealed OOS gate 才能繼續 baseline/ranking/monitor，失敗時 rollback  
證據路徑：`artifacts/sealed_oos_report_YYYY-MM-DD.json`、`artifacts/sealed_oos_report_latest.json`、`artifacts/retrain_rollback_injection_YYYY-MM-DD.json`、`artifacts/model_group_acceptance_YYYY-MM-DD.json`

## 邊界

- 不開 auto retrain。
- 不改 ranking score。
- 不改 production threshold。
- 不把 sealed period 用於訓練、調參、校準或 PSI baseline。
- 不因舊正式模型缺 sealed metadata 而補假 metadata。

## 設計

- `LightGBMTrainer` 在訓練前建立 `development / embargo / sealed` 三段。
- `development` 可用於 optuna、walk-forward 與 final train。
- `embargo` 與 `sealed` 不可用於 train/tune/calibration。
- 新模型 metadata 寫入 `sealed_oos` split metadata。
- `scripts/run_sealed_oos_gate.py` 重新載入完整 labeled frame，使用 sealed window 評估候選模型。
- `scripts/run_automation.py` 在 `model.validate` 後、baseline refresh 前執行 `model.sealed_oos`；失敗進 rollback。
- `ModelMonitor.save_baseline()` 會依模型 metadata 的 `sealed_oos.train_end_date` 過濾 baseline source，避免 PSI baseline 吃到 sealed window。

## 驗收

- sealed split 必須有 train / embargo / sealed 日期與 row count metadata。
- unit regression 必須驗證 development 不含 embargo / sealed。
- gate 必須拒絕缺少 sealed_oos metadata 的模型。
- retrain rollback injection 必須包含 `sealed_oos` failure case，且 model + baseline 都 rollback。
- model group acceptance 必須包含 `sealed_oos.unit`。

## 本地驗證

- `uv run --with-requirements requirements.txt python scripts/verify_sealed_oos_gate.py` 通過，輸出 `SEALED_OOS_VERIFY_OK`。
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile app/modeling/sealed_oos.py app/agent_b_modeling.py app/model_monitor.py scripts/run_sealed_oos_gate.py scripts/verify_sealed_oos_gate.py scripts/run_automation.py scripts/verify_retrain_rollback.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_retrain_rollback.py` 通過，`sealed_oos` injected failure 會 `model.rollback=OK`、`model.baseline.rollback=OK`。
- `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py` 通過，`sealed_oos.unit=OK`、整體 `model_health_status=WARN`、`auto_retrain_readiness=BLOCKED`。
- `uv run --with-requirements requirements.txt python scripts/run_sealed_oos_gate.py` 對目前舊正式模型輸出 `SEALED_OOS_GATE_FAILED`，原因為 `model metadata 缺少 sealed_oos`；這是正確安全行為。

## 現場 sealed OOS 報告

- `status=FAILED`
- failure：`model metadata 缺少 sealed_oos`
- split：development `2023-05-26` ~ `2026-01-16`，embargo `2026-01-19` ~ `2026-01-30`，sealed `2026-02-02` ~ `2026-05-11`
- sealed rows：`51840`
- sealed AUC：`0.6778`
- top10 return uplift：`0.0330`
- 判讀：舊正式模型雖然 sealed 指標尚可，但不是用新 sealed training flow 產出的模型，所以不得自動視為 promotion-ready。
