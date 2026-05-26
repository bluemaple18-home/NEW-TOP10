# REVIEW-MODEL-OPS-04 sealed OOS promotion gate

## 五行派工卡

任務ID：REVIEW-MODEL-OPS-04  
卡片類型｜派工對象：Model Ops Review｜Reviewer AI  
請讀：`docs/tasks/2026-05-26_MODEL-OPS-04_sealed_oos_gate.md`、`app/agent_b_modeling.py`、`app/modeling/sealed_oos.py`、`scripts/run_sealed_oos_gate.py`、`scripts/run_automation.py`、`app/model_monitor.py`  
任務目的：複查 sealed OOS 是否真的排除最近成熟標籤交易日於 train/tune/calibration 之外，gate 是否在 baseline/ranking/monitor 前阻斷不合格模型，且失敗時 model + baseline rollback  
證據路徑：`artifacts/sealed_oos_report_2026-05-26.json`、`artifacts/retrain_rollback_injection_2026-05-26.json`、`artifacts/model_group_acceptance_2026-05-26.json`

## Reviewer 注意

- 目前正式模型缺 `sealed_oos` metadata，所以 `run_sealed_oos_gate.py` 對它回 `FAILED` 是正確安全行為。
- 不要把 sealed metrics 不差誤判成 PASS；沒有 sealed training metadata 就不能證明沒有 leakage。
- 確認 baseline refresh 會依 `model.metadata.sealed_oos.train_end_date` 限縮來源。
