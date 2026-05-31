# Context Manifest

## 必讀檔案
- `scripts/verify_training_automation_readiness.py`
- `scripts/verify_model_group_acceptance.py`
- `scripts/generate_model_health_report.py`
- `scripts/verify_model_foundation.py`
- `scripts/build_model_experiment_result_report.py`
- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`

## 證據來源
- `artifacts/training_automation_readiness_2026-05-31.json`
- `artifacts/model_group_acceptance_2026-05-31.json`
- `artifacts/model_health_report_latest.json`
- `artifacts/model_experiments/model_exp_result_report_2026-05-31.json`
- `artifacts/model_experiments/half_year_walkforward_validation_2026-05-31.json`
- `artifacts/model_experiments/model_research_flow_2026-05-31.json`

## 相關前置卡
- `.work/REVIEW-20260531-half-year-no-hindsight/brief.md`

## 不可破壞
- `models/latest_lgbm.pkl` 不得被覆蓋。
- production ranking score 不得改變。
- auto retrain 不得被啟用。
- diagnostic-only 結果不得被拿來同輪 promotion。
- 缺資料不得靜默假裝完整。
