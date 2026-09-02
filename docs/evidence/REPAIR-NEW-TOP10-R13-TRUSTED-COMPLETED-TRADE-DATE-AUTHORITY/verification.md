# R13 trusted completed trade date authority verification

## Result

- Added completed trade date authority validation for forward ranking provenance capture.
- Historical and regime-shadow producers now require `--capture-authority-artifact` for `--forward-capture`.
- The authority artifact is snapshotted before and after generation and is written into receipt `strict_inputs` as `completed_trade_date_authority`.
- `REPLAY_GENERATED` remains admission-ineligible and does not require authority input.

## Verification

- `uv run pytest tests/test_ranking_provenance_receipt.py tests/test_historical_ranking_replay_set_lineage.py tests/test_regime_research_boundaries.py -q`
  - Result: `32 passed, 3 warnings`
  - Warnings: existing SHAP / matplotlib pending deprecations.
- `git diff --check`
  - Result: passed.

## Scope

- No production data, ranking artifact, config, workflow, scheduler, network fetch, push, merge, deploy, or real R13 capture was executed.

## Remaining risk

- The validator is intentionally bound to current local `automation-status.v1` shape: `steps[]` plus `metadata.data_freshness.datasets`. A future daily status schema change will fail closed until this validator is updated.
