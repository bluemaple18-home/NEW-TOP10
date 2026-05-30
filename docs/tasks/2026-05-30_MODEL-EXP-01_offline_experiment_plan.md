# MODEL-EXP-01 Offline Experiment Plan

## 任務卡

任務ID：MODEL-EXP-01
卡片類型｜派工對象：Offline Model Experiment Plan｜Codex
請讀：`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`、`artifacts/shadow_feature_experiment_YYYY-MM-DD.json`、`scripts/build_model_experiment_plan.py`
任務目的：把 SHADOW-01 放行的候選特徵整理成離線實驗矩陣；只產計畫 artifact，不正式訓練、不覆蓋 `models/latest_lgbm.pkl`、不改 `risk_adjusted_score`、不改 production ranking。
證據路徑：`artifacts/model_experiments/model_exp_plan_YYYY-MM-DD.json`、`artifacts/model_experiments/model_exp_plan_verification_latest.json`

## 目前實驗矩陣

- `model_exp_candidate_persistence_only`
- `model_exp_portfolio_risk_overlay_only`
- `model_exp_regime_feature_group_ablation`
- `model_exp_combined_conservative`

`model_exp_combined_conservative` 必須等個別實驗通過後才可跑，不可一開始就混合特徵。

## 不可做

- 不跑正式 retrain。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不把 shadow 結果直接轉成 `RankingPolicy` 權重。
- 不把 blocked candidate 放進模型實驗。
- 不用單一近期 replay 結果宣稱可 promote。

## 驗證

```bash
uv run --with-requirements requirements.txt python scripts/build_shadow_feature_experiment.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_shadow_feature_experiment.py --artifact artifacts/shadow_feature_experiment_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/build_model_experiment_plan.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_plan.py --artifact artifacts/model_experiments/model_exp_plan_YYYY-MM-DD.json
```
