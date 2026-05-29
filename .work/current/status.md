# Current Status

狀態：主線 artifact / decision evidence 層已完成，進入 shadow feature / regime research review。

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

最新驗證：

- `scripts/verify_market_context_fetcher.py` 通過。
- `scripts/verify_decision_quality.py` 通過。
- `scripts/verify_feature_experiment_gate.py` 通過。

目前限制：

- 不直接改 `RankingPolicy`。
- 不直接改 `risk_adjusted_score`。
- 不把 shadow / research 結果直接升 production。
- runtime artifacts 在 `artifacts/`，預設不進 git。

下一步：

- review 遠端新增的 regime / weekend research matrix 腳本。
- 將可用 candidate 留在 shadow experiment，不開 production promotion。
