# Verification

## Commands

```bash
.venv/bin/python -m py_compile \
  app/modeling/sealed_oos.py \
  scripts/build_market_regime_history.py \
  scripts/compare_strategy_matrices.py \
  scripts/run_autonomous_research.py \
  scripts/run_backtest_strategy_matrix.py \
  scripts/verify_regime_research_autonomy.py

.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_pm_research_harness_loop.py \
  tests/test_shadow_research_campaign.py \
  tests/test_feature_promotion_decision.py \
  tests/test_regime_research_autonomy.py

.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --output artifacts/visible_thread/REGIME-RESEARCH-AUTONOMY-01/verifier_report.json

.venv/bin/python -m pytest -q
git diff --check
```

## Result

- affected tests: `57 passed`
- verifier: `OK`, 26 checks, 0 failed
- full suite: `507 passed`, 1 provisioning-only baseline failure
- diff check: `PASS`
- debug markers: none
- production model hashes: unchanged

## Production Hashes

- `models/latest_lgbm.pkl`:
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `models/baseline_stats.json`:
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`

## Verifier Coverage

每一類都有正例與合成反例：

1. parameter universe
2. as-of regime rows
3. exact-match dataset
4. full-episode split / embargo
5. immutable pre-registration
6. sealed reuse contamination
7. cross-experiment composition
8. append-only funnel transition
9. coverage closure
10. topic score reproducibility
11. multiple testing / robustness
12. universal gate
13. production no-change
