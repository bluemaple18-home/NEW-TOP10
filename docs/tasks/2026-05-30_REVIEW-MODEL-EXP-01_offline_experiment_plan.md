# REVIEW-MODEL-EXP-01 Offline Experiment Plan

## 任務卡

任務ID：REVIEW-MODEL-EXP-01
卡片類型｜派工對象：Code Review / Model Experiment Flow｜Reviewer
請讀：`docs/tasks/2026-05-30_MODEL-EXP-01_offline_experiment_plan.md`、`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`、`scripts/build_shadow_feature_experiment.py`、`scripts/verify_shadow_feature_experiment.py`、`scripts/build_model_experiment_plan.py`、`scripts/verify_model_experiment_plan.py`、`scripts/run_model_research_flow.py`
任務目的：review `SHADOW-01 → MODEL-EXP-01` 是否只產研究 artifact 與離線實驗計畫，不會正式訓練、不會覆蓋 `models/latest_lgbm.pkl`、不會改 `risk_adjusted_score` 或 production ranking，並確認 blocked candidates 不會混入模型實驗。
證據路徑：`artifacts/shadow_feature_experiment_YYYY-MM-DD.json`、`artifacts/shadow_feature_experiment_verification_latest.json`、`artifacts/model_experiments/model_exp_plan_YYYY-MM-DD.json`、`artifacts/model_experiments/model_exp_plan_verification_latest.json`、`artifacts/model_experiments/model_research_flow_YYYY-MM-DD.json`

## Review 重點

- `run_model_research_flow.py` 只能串 feature gate、SHADOW-01、MODEL-EXP-01 plan 與 verifier，不得 fetch data、retrain、寫 model 或跑 production ranking。
- `build_model_experiment_plan.py` 只能讀 `shadow_feature_experiment_YYYY-MM-DD.json`，不得直接使用 blocked candidate 或自行放行 `market_context` / fundamentals / chip / industry rotation。
- `portfolio_risk_overlay` 必須維持 post-ranking overlay track，不可被當成 first-pass LightGBM feature 直接混入模型。
- `model_exp_combined_conservative` 必須等個別 experiment 通過後才可跑，不得一開始就混合特徵。
- 所有 contract 需明確保持：
  - `does_not_train_model=true`
  - `does_not_write_models_latest_lgbm=true`
  - `does_not_change_risk_adjusted_score=true`
  - `does_not_change_production_ranking=true`
  - `production_promotion_allowed=false`
- docs 不得再寫 `market_context` 已可開始測試，除非 feature gate artifact 實際放行。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile \
  scripts/build_shadow_feature_experiment.py \
  scripts/verify_shadow_feature_experiment.py \
  scripts/build_model_experiment_plan.py \
  scripts/verify_model_experiment_plan.py \
  scripts/run_model_research_flow.py

uv run --with-requirements requirements.txt python scripts/run_model_research_flow.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_shadow_feature_experiment.py --artifact artifacts/shadow_feature_experiment_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_plan.py --artifact artifacts/model_experiments/model_exp_plan_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --json
git diff --check -- \
  scripts/build_shadow_feature_experiment.py \
  scripts/verify_shadow_feature_experiment.py \
  scripts/build_model_experiment_plan.py \
  scripts/verify_model_experiment_plan.py \
  scripts/run_model_research_flow.py \
  docs/architecture/MODEL_IMPROVEMENT_LOOP.md \
  docs/tasks/2026-05-29_FEATURE-EXP-01_shadow_feature_promotion_gate.md \
  docs/tasks/2026-05-30_MODEL-EXP-01_offline_experiment_plan.md \
  docs/tasks/2026-05-30_REVIEW-MODEL-EXP-01_offline_experiment_plan.md
```

## 預期結論格式

- Findings：依 P0/P1/P2/P3 排序；若無阻塞，明確寫「未發現阻塞問題」。
- Testing Gaps：只列會影響 shadow/model experiment/promotion gate 判定的缺口。
- Merge Recommendation：`approve` / `approve_with_followups` / `block`。
