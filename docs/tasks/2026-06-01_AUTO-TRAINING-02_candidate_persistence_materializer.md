# AUTO-TRAINING-02 candidate persistence materializer

## 任務ID

`AUTO-TRAINING-02`

## 卡片類型｜派工對象

Feature Materialization / Model Experiment｜Codex

## 請讀

- `scripts/build_candidate_persistence_materialized_features.py`
- `scripts/research_candidate_persistence_materialized_ablation.py`
- `scripts/build_model_experiment_run_manifest.py`
- `scripts/build_model_experiment_result_report.py`
- `artifacts/model_experiments/model_exp_run_manifest_2026-06-01.json`

## 任務目的

補齊 `candidate_persistence` materializer，解除 `model_exp_candidate_persistence_only` 的 `BLOCKED_MISSING_MATERIALIZER`，讓該 experiment 能進入正式 research artifact 驗證。

## 背景

目前 readiness 已可啟動訓練候選，但 `candidate_persistence` 仍 blocked。這會讓 `model_exp_combined_conservative` 持續 waiting，因為 combined experiment 必須等個別候選通過後才可跑。

## 要做

- 確認 candidate persistence 需要的 historical ranking input。
- 產出 materialized feature artifact。
- 讓 run manifest 不再把 `model_exp_candidate_persistence_only` 標為 missing materializer。
- 重建 result report，讓 ledger resolver 正確同步。
- 保持 research-only，不改 production ranking。

## 不可做

- 不把入榜天數直接變成 production 權重。
- 不修改 `risk_adjusted_score`。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不把單次 ablation 結果直接 promotion。

## 驗收

```bash
uv run --with-requirements requirements.txt python scripts/build_candidate_persistence_materialized_features.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/research_candidate_persistence_materialized_ablation.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/build_model_experiment_run_manifest.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/build_model_experiment_result_report.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_result_report.py --artifact artifacts/model_experiments/model_exp_result_report_YYYY-MM-DD.json
git diff --check
```

## 回報格式

```text
AUTO-TRAINING-02 status:
materializer artifact:
ablation artifact:
run_manifest status:
candidate_persistence status:
ledger resolver:
errors:
```
