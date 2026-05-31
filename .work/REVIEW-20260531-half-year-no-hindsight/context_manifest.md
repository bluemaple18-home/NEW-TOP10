# Context Manifest

## 必讀檔案
- `scripts/research_regime_feature_offline_ablation.py`
- `scripts/verify_half_year_walkforward_no_hindsight.py`
- `scripts/verify_training_automation_readiness.py`
- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`

## 證據來源
- `artifacts/model_experiments/half_year_walkforward_validation_2026-05-31.json`
- `artifacts/model_experiments/half_year_walkforward_validation_2026-05-31.md`
- `artifacts/training_automation_readiness_2026-05-31.json`

## 不可破壞
- `models/latest_lgbm.pkl` 不得被覆蓋。
- production ranking score 不得因這張 review 改變。
- diagnostic-only variants 不得成為同一輪 promotion gate。
- 新增 filter / regime rule 必須進下一輪 walk-forward，不得回頭修同一份歷史結果。
- 研究腳本只能輸出 artifact，不得寫 production daily artifact 或通知訊息。
