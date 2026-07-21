# Current Status

狀態：`REVIEW-REGIME-RESEARCH-01` 已完成，裁決為 `GO_SHADOW_ONLY`。

已確認完成：

- `MARKET-CONTEXT-02-TW`
  - `app/market_context_fetcher.py`
  - `scripts/verify_market_context_fetcher.py`
  - `docs/tasks/2026-05-29_MARKET-CONTEXT-02-TW_fetcher.md`
- `DECISION-QUALITY-01`
  - `scripts/build_decision_quality.py`
  - `scripts/verify_decision_quality.py`
  - `docs/architecture/TRADING_DECISION_LAYER.md`
- `FEATURE-EXP-01`
  - `scripts/build_feature_experiment_gate.py`
  - `scripts/verify_feature_experiment_gate.py`
- `REVIEW-REGIME-RESEARCH-01`
  - 五支 regime／weekend research 腳本與直接 caller 完成 production-boundary review。
  - `research_regime_shadow_ranking.py` 已限制只能寫入 `artifacts/backtest/` 子目錄。
  - `tests/test_regime_research_boundaries.py` 已補 production output 隔離與 command graph 回歸。

最新驗證：

- `scripts/verify_market_context_fetcher.py` 通過。
- `scripts/verify_decision_quality.py` 通過。
- `scripts/verify_feature_experiment_gate.py` 通過。
- regime research 相關測試共 25 項通過。
- `scripts/verify_feature_group_ablation_by_regime.py` 通過。

目前限制：

- 不直接改 `RankingPolicy`。
- 不直接改 `risk_adjusted_score`。
- 不把 shadow / research 結果直接升 production。
- runtime artifacts 在 `artifacts/`，預設不進 git。
- `BROAD_RISK_ON`、`CHOPPY_RANGE` 目前只有 generic fallback，不得宣稱為專屬 regime candidate。
- `run_weekend_research_matrix.py --skip-heavy` 只可證明 audit／compare，不代表 strategy matrix 已重跑。

下一步：若要開 candidate，只能走 sealed OOS／成熟樣本／replay／portfolio risk 的獨立 shadow 實驗卡；目前沒有可直接升 production 的項目。
