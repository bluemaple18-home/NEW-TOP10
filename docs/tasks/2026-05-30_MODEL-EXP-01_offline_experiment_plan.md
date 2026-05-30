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

2026-05-30 後續測試結論：

- `portfolio_risk_overlay`：recent 與 extended tail strategy matrix 都通過，已產 `portfolio_overlay_promotion_review_2026-05-30.json`，狀態 `READY_FOR_HUMAN_REVIEW`。它仍是 post-ranking overlay，不是 LightGBM feature；正式接入 production 前必須另開 review diff 與 rollback/default-off gate。
- `regime_feature_group_ablation`：IC / shadow evidence 有訊號，但 offline model ablation 顯示 AUC 只增加 `+0.000513`，Top10 proxy return 反而下降 `-0.004747`，暫列 `MONITOR_ONLY_WEAK_MODEL_UPLIFT`。
- `candidate_persistence`：暫列 `MONITOR_ONLY_NOT_STABLE`。
- `model_exp_combined_conservative`：維持 `WAIT_FOR_INDIVIDUAL_PASS`，不可混合兩個已降級觀察的特徵候選。

2026-05-30 default-off production scaffold：

- 新增 `app/trading/portfolio_risk_overlay.py`，同時提供 score overlay 與 sizing overlay，但 `config/signals.yaml` 預設 `enabled=false`。
- `RankingPolicy` / `PortfolioPolicy` 已接入 overlay 物件；default-off 時不新增欄位、不改排序、不改權重。
- 驗證：`scripts/verify_portfolio_risk_overlay_default_off.py` 確認 default-off exact match，且 enabled synthetic case 才會新增 overlay score / regime 並套用 panic selling gross cap。
- 仍未啟用 production promotion；正式開關前需要另跑 daily dry-run diff、production path replay 與 rollback/config flag review。

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
