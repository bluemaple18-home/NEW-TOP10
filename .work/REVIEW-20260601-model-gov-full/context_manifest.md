# Context Manifest

## 必讀檔案
- `docs/tasks/2026-05-31_MODEL-GOV-FULL_implementation_card.md`
- `docs/architecture/MODEL_EXPERIMENT_LEDGER.md`
- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`
- `scripts/model_experiment_ledger.py`
- `scripts/verify_model_experiment_ledger.py`
- `scripts/run_model_research_flow.py`
- `scripts/build_model_experiment_plan.py`
- `scripts/build_model_experiment_run_manifest.py`
- `scripts/build_model_experiment_result_report.py`
- `scripts/verify_model_experiment_result_report.py`
- `scripts/build_model_experiment_ledger_stats.py`
- `scripts/backfill_model_experiment_ledger.py`
- `scripts/build_model_promotion_review.py`
- `scripts/generate_daily_report.py`
- `scripts/build_weekend_research_decision_report.py`

## 證據來源
- `artifacts/model_experiments/model_experiment_ledger.json`
- `artifacts/model_experiments/model_experiment_ledger_verification_latest.json`
- `artifacts/model_experiments/model_experiment_ledger_stats_*.json`
- `artifacts/model_experiments/model_research_flow_*.json`
- `artifacts/model_experiments/model_exp_result_report_*.json`
- `artifacts/model_experiments/model_experiment_ledger_backfill_*.json`
- `artifacts/model_experiments/model_promotion_review_*.json`
- `artifacts/weekend_research_decision_report_*.json`

## 不可破壞
- Ledger 不得輸出 `PROMOTION_READY`、`AUTO_PROMOTE`、`MODEL_APPROVED`。
- Ledger 不得取代 sealed OOS / replay / rollback / model group acceptance。
- `models/latest_lgbm.pkl` 不得被覆蓋。
- Production ranking 與 `risk_adjusted_score` 不得被修改。
- Result report 必須維持 verdict source of truth。
- Ledger history 必須 append-only。
- Shared docs / task cards / commands 必須使用 repo-relative path 或 `<repo-root>`，不得寫本機絕對路徑作跨機命令。

## 已知非阻塞缺口
- `artifacts/ranking_2026-05-31.csv` 缺失導致 daily report 實跑無法產出；這是資料/artifact 缺口，不是 `MODEL-GOV-FULL` governance 主線失敗。
