# Context Manifest

## 必讀

- `AGENTS.md`：專案規範。
- `.work/current/status.md`：目前狀態。
- `.work/current/handoff.md`：接手摘要。
- `docs/architecture/TRADING_DECISION_LAYER.md`：decision quality / reference annotation 邊界。
- `docs/tasks/2026-05-29_MARKET-CONTEXT-02-TW_fetcher.md`：market context 實作卡。
- `docs/tasks/2026-05-29_FEATURE-EXP-01_shadow_feature_promotion_gate.md`：shadow feature gate。

## 主線程式

- `app/market_context_fetcher.py`
- `scripts/verify_market_context_fetcher.py`
- `scripts/build_decision_quality.py`
- `scripts/verify_decision_quality.py`
- `scripts/build_feature_experiment_gate.py`
- `scripts/verify_feature_experiment_gate.py`
- `scripts/run_automation.py`
- `config/automation.yaml`

## 目前要 review 的研究線

- `scripts/build_market_regime_history.py`
- `scripts/research_regime_shadow_ranking.py`
- `scripts/research_feature_group_ablation_by_regime.py`
- `scripts/run_weekend_research_matrix.py`
- `scripts/audit_research_dataset_coverage.py`

## 邊界

- `artifacts/` 是 runtime evidence，預設不進 git。
- reference annotation 只讀 `data/reference`，不改 model / ranking score。
- regime / market context / persistence / portfolio risk 目前都只能走 shadow 或 read-only evidence。
