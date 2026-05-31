# Result

## 目前結果
已完成。half-year walk-forward / no-hindsight governance / readiness gate 已具備可機器驗證的收尾條件。

## 已知狀態
- half-year decision 目前為 `MONITOR_ONLY`。
- 這張卡只審查正式訓練前準備與治理閘門，不代表模型可 promotion。
- readiness 驗證需用 `uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py ...`；裸 `uv run python ...` 可能因缺 `yaml` / `PyYAML` 誤報環境錯誤。
- diagnostic-only variants 只能作下一輪研究輸入，不可同輪作 promotion gate。
- artifact contract 明確禁止 production promotion、覆蓋 `models/latest_lgbm.pkl`、改 `risk_adjusted_score`、改 production ranking。

## 證據
- `uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --self-test`：OK。
- `uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --artifact artifacts/model_experiments/half_year_walkforward_validation_2026-05-31.json`：OK。
- `uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900`：OK，輸出 `PREPARED_WITH_BLOCKERS`，且 half-year decision 為標準值 `MONITOR_ONLY`。
- `python3 -m py_compile scripts/verify_training_automation_readiness.py scripts/verify_half_year_walkforward_no_hindsight.py scripts/research_regime_feature_offline_ablation.py`：OK。
- `git diff --check`：OK。
