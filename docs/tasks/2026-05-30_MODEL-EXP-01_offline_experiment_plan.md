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

## 執行前 manifest

`model_exp_plan` 只代表研究設計可成立；真正執行前還要跑：

```bash
uv run --with-requirements requirements.txt python scripts/build_model_experiment_run_manifest.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_run_manifest.py --artifact artifacts/model_experiments/model_exp_run_manifest_YYYY-MM-DD.json
```

`candidate_persistence` 必須先通過 prior-only materializer，才能進離線 ablation；不可直接把日報用 `candidate_persistence_YYYY-MM-DD.json` 混進訓練。

已補上的安全 materializer：

```bash
uv run --with-requirements requirements.txt python scripts/build_candidate_persistence_materialized_features.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_candidate_persistence_materialized_features.py --artifact artifacts/model_experiments/candidate_persistence_features_YYYY-MM-DD.parquet
uv run --with-requirements requirements.txt python scripts/research_candidate_persistence_materialized_ablation.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_candidate_persistence_materialized_ablation.py --artifact artifacts/model_experiments/candidate_persistence_materialized_ablation_YYYY-MM-DD.json
```

2026-05-30 測試結論：近期 window 的 `prior streak=1` 有正向跡象，但 extended window 不穩，暫列 `MONITOR_ONLY_NOT_STABLE`；它可以保留在訊息/UI 脈絡，不應直接進正式模型候選。

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
uv run --with-requirements requirements.txt python scripts/build_model_experiment_run_manifest.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_run_manifest.py --artifact artifacts/model_experiments/model_exp_run_manifest_YYYY-MM-DD.json
```

整條安全研究鏈可用：

```bash
uv run --with-requirements requirements.txt python scripts/run_model_research_flow.py --date YYYY-MM-DD
```
