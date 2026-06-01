# AUTO-TRAINING-06 final small review

## 任務ID

`AUTO-TRAINING-06`

## 卡片類型｜派工對象

Small Review / Promotion Guard Check｜另一個 AI reviewer

## 請讀

- `docs/tasks/2026-06-01_AUTO-TRAINING-02_candidate_persistence_materializer.md`
- `docs/tasks/2026-06-01_AUTO-TRAINING-03_big_bull_ranking_replay.md`
- `docs/tasks/2026-06-01_AUTO-TRAINING-04_revenue_or_technical_lane.md`
- `docs/tasks/2026-06-01_AUTO-TRAINING-05_half_year_negative_fold_diagnostics.md`
- `scripts/research_big_bull_shadow_ranking.py`
- `scripts/build_technical_only_training_lane.py`
- `scripts/build_half_year_negative_fold_diagnostics.py`
- `scripts/verify_training_automation_readiness.py`
- `artifacts/model_experiments/technical_only_training_lane_2026-06-01.json`
- `artifacts/model_experiments/half_year_negative_fold_diagnostics_2026-06-01.json`
- `artifacts/model_experiments/model_experiment_ledger.json`
- `artifacts/training_automation_readiness_2026-06-01.json`

## 任務目的

做最後小範圍 review，確認這組 AUTO-TRAINING 卡已可收，但沒有任何 promotion 偷渡。

## 背景

本輪已分別通過三個 checkpoint：

- Checkpoint A：candidate persistence materializer / ablation / manifest / report。
- Checkpoint B：BIG_BULL ranking/replay follow-up，只進 ledger pending。
- Checkpoint C：technical-only lane，revenue 0% coverage 只允許 research/readiness。

最後 `AUTO-TRAINING-05` 新增 half-year negative fold diagnostics 與 4 個 ledger pending hypotheses。這一步只產生下一輪研究假設，不修改原 half-year artifact gate。

## 要看

- `half_year_negative_fold_diagnostics_2026-06-01.json` 是否仍是 diagnostic-only。
- 原 `half_year_walkforward_validation_2026-06-01.json` 是否仍維持 `MONITOR_ONLY`。
- ledger 新增的 half-year negative fold entries 是否都是 `pending`。
- `production_promotion_allowed` 是否全線維持 `false`。
- `training_launch_ready=true` 是否沒有被誤讀成 `promotion_ready=true`。
- 新增腳本是否只寫 research/backtest/model_experiments artifacts，不覆蓋 production model 或 production ranking。

## 不可做

- 不要求大 review。
- 不重新設計 promotion gate。
- 不把 BIG_BULL replay 好結果改成 promotion evidence。
- 不把 technical-only lane 當作 production feature drop。
- 不修改 `models/latest_lgbm.pkl`。
- 不修改 production ranking 或 `risk_adjusted_score`。

## 建議驗收

```bash
uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --artifact artifacts/model_experiments/half_year_walkforward_validation_2026-06-01.json
uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --self-test
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --date 2026-06-01 --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 回報格式

```text
AUTO-TRAINING-06 final small review:
status:
promotion guard:
half_year diagnostics:
ledger pending entries:
technical_only lane:
BIG_BULL follow-up:
training_launch_ready:
promotion_ready:
required fixes:
```
