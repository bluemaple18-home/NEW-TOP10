# Phase 0 Bounded Baseline

- captured_from: `ebfffbd5b926b169dde353c6f1a888fe04fbd159`
- fixture_scope: pure topic scoring and matrix replay argument wiring
- latest_autonomous_trace_in_worktree: `absent`
- baseline_fixture: `baseline_fixture.json`

## Observed Legacy Behavior

1. `shadow_rankings_regime_guard_recent` 因檔名關鍵字取得 28 分加權。
2. topic score 為 42，但 topic payload 沒有 current as-of regime identity。
3. `scripts/run_backtest_strategy_matrix.py::replay_args` 固定傳入
   `market_regime_history=None`，因此名稱含 regime 不代表資料有過濾。
4. 既有行為只保存為 bounded legacy diagnostic，不可作新契約通過證據。

## Production Baseline

- `models/latest_lgbm.pkl`:
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `models/baseline_stats.json`:
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`
- production comparison base: `7efda43641118f36b10261b4a04e0278bba941a2`

## Reproduction

```bash
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
```
