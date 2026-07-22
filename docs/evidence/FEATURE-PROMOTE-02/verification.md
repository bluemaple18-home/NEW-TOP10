# FEATURE-PROMOTE-02 Verification

Status: `NO_GO`

Base SHA: `b5a5e6394fa1bdb4f82124ffa5e1694844605f28`

The decision is fail-closed. The checkpoint PASS only unlocks this decision
card; it is not promotion approval. Theme flow and Graph diffusion remain
shadow-only and no RankingPolicy, model weight, production runtime, deploy
configuration, or daily production path was changed.

## Evidence decision

The deterministic builder reports these missing required evidence items:

- sealed OOS and time-split/walk-forward results;
- baseline/candidate comparison on the same universe, dates, and cost model;
- candidate leakage, stability, turnover, drawdown, concentration, and late-data
  behavior evidence;
- data manifest and candidate manifest containing reproducible code/data SHAs;
- formal FEATURE-PROMOTE-02 code review evidence.

Existing Theme/Graph acceptance and review evidence is recorded as supporting
shadow evidence only. It does not satisfy the missing promotion evidence.

Graph diffusion residual `tolerance > 1` is retained as a promotion risk. Theme
coverage is TWSE-only and TPEx is explicitly `KEEP_BLOCKED`; this is included in
the decision attribution and cannot be silently treated as full-market coverage.

## Reproducible commands

```text
<repo-root>/.venv/bin/python -m pytest tests/test_feature_promotion_decision.py tests/test_model_runtime_promotion.py tests/test_daily_v2_promotion.py
<repo-root>/.venv/bin/python scripts/verify_feature_experiment_gate.py
<repo-root>/.venv/bin/python scripts/build_model_promotion_review.py --help
<repo-root>/.venv/bin/python scripts/build_feature_promotion_decision.py --help
<repo-root>/.venv/bin/python scripts/verify_feature_promotion_decision.py --help
<repo-root>/.venv/bin/python scripts/verify_feature_promotion_decision.py --decision artifacts/feature_promotion_decision_FEATURE-PROMOTE-02.json
<repo-root>/.venv/bin/python -m py_compile scripts/build_feature_promotion_decision.py scripts/verify_feature_promotion_decision.py tests/test_feature_promotion_decision.py
git diff --check
```

The runtime artifact is intentionally under the ignored `artifacts/` directory;
the builder recomputes source hashes and the verifier recomputes the decision.
