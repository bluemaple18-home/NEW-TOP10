# REVIEW-MODEL-OPS-03-FIX model-bound PSI baseline

## 五行派工卡

任務ID：REVIEW-MODEL-OPS-03-FIX  
卡片類型｜派工對象：Model Ops Review｜Reviewer AI  
請讀：`docs/tasks/2026-05-26_MODEL-OPS-03_model_bound_psi_baseline.md`、`app/model_monitor.py`、`scripts/generate_model_health_report.py`、`scripts/refresh_model_baseline.py`、`models/baseline_stats.json`  
任務目的：複查 MODEL-OPS-03 P2 是否已修掉：baseline 覆蓋缺口必須揭露為 skipped empty model features，health report 必須對 84/86 coverage 標 WARN，且不得啟用 auto retrain  
證據路徑：`models/baseline_stats.json`、`artifacts/psi_report.json`、`artifacts/model_health_report_2026-05-26.json`、`artifacts/model_group_acceptance_2026-05-26.json`、`artifacts/retrain_rollback_injection_2026-05-26.json`

## Reviewer 注意

- `revenue_yoy` / `revenue_mom` 在 M4 frame 全空，因此 baseline 分佈數是 84，不是 86。
- 正確行為不是硬補空分佈，而是 metadata 揭露 `skipped_empty_model_features`，並讓 health report 標 WARN。
- `artifacts/psi_report.json` 可為 OK，但整體 model health 仍應是 WARN。
- auto retrain readiness 仍應維持 BLOCKED。
