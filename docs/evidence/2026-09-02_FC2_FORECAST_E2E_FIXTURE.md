# FC2 Forecast E2E Fixture Evidence

Status: IMPLEMENTATION_COMPLETE_PENDING_REVIEW

Scope:
- Added a deterministic vendor-neutral forecast fixture harness.
- Uses existing FC1 forecast dataset bundle, trial spec, artifact receipt, and evaluation observation contracts.
- Writes and validates existing Research Spine lifecycle artifacts: `research-trial-spec.v1`,
  `research-intent.v1`, `research-run-attempt-started.v1`, and `research-run-receipt.v1`.
- Does not add FC1 schema fields.
- Does not download models, call network, or introduce TimesFM-specific names.
- Does not touch queue, runner, ranking, M4-M7, production, or eligibility policy.

Executed verification:
- CodeGraph-first attempted; project CodeGraph index was not initialized in this worktree, so source lookup used bounded `rg`/file reads.
- `.venv/bin/python -m pytest tests/test_forecast_fixture.py tests/test_forecast_contracts.py` -> 31 passed.
- `.venv/bin/python -m pytest tests/test_research_dataset_bundle.py tests/test_research_spine_contracts.py tests/test_research_ledger.py tests/test_research_eligibility_failure.py` -> 95 passed.
- Changed-file allowlist relative to `9abc1592c54e6e34f95cba347f5d61f080a098cd` stayed within
  `app/research/forecast_fixture.py`, `tests/test_forecast_fixture.py`,
  `docs/tasks/2026-09-02_CARD-NEW-TOP10-FC2-VENDOR-NEUTRAL-FORECAST-END-TO-END-FIXTURE.md`,
  and this evidence file.
- `git diff --check` -> passed.

Acceptance notes:
- Positive path rebuilds identical dataset bundle, forecast trial spec, existing lifecycle intent/attempt/run receipt,
  point/quantile artifact receipt, and evaluation observation identities.
- Run receipt links back to the forecast trial spec, dataset bundle, point/quantile artifacts, forecast artifact receipt,
  and forecast evaluation observation through deterministic CAS artifacts and existing lifecycle validators.
- Negative path rejects bundle/spec mismatch, artifact byte tampering, artifact digest swaps, missing lifecycle attempt,
  tampered lifecycle attempt linkage, missing forecast artifact receipt lifecycle linkage, production-like usage status,
  available_at leakage, and strategy observation identity admission.
- Forecast lifecycle can ingest into the existing Research Ledger without creating strategy observations; eligibility projection
  emits no eligible observation decision and assigns zero evidence weight.
- Artifact bytes are written only to pytest tmp directories.
