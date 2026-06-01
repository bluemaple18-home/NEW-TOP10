# Context Manifest

## 必讀檔案
- `scripts/build_market_regime_history.py`
- `scripts/research_regime_family_training_candidates.py`
- `scripts/verify_regime_family_training_candidates.py`
- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`

## 證據來源
- `artifacts/market_regime_history_2026-05-31.json`
- `artifacts/model_experiments/regime_family_training_candidates_2026-05-31.json`
- `artifacts/model_experiments/regime_family_training_candidates_verification_latest.json`

## 不可破壞
- `models/latest_lgbm.pkl` 不得被覆蓋。
- production ranking score 不得改變。
- 樣本不足不得 promotion。
- diagnostic 結果不得同輪變成 filter。
