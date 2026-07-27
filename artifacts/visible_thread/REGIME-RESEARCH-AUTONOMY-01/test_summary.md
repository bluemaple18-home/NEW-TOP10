# Test Summary

## Phase 0 Red

- command: `.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py`
- baseline: `ebfffbd5b926b169dde353c6f1a888fe04fbd159`
- result: `6 failed`
- evidence: `red_evidence.md`

## Candidate Green

- card-specific and related regression:
  `57 passed in 1.07s`
- consolidated verifier:
  `26 checks / 0 failed`
- Python compile:
  `PASS`
- `git diff --check`:
  `PASS`

## Full Suite

- command: `.venv/bin/python -m pytest -q`
- result: `507 passed, 1 failed, 246 subtests passed, 4 warnings`
- failing test:
  `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
- failed check:
  existing `evidence_exists` references historical model experiment artifacts,
  `data/clean/features.parquet` and reference CSV files absent from this isolated worktree.
- baseline proof:
  the same test also fails from a pure `7efda43` archive in `/tmp`; no card diff is
  present there. This is a provisioning-only baseline blocker, not a regression caused
  by this candidate.

No test was skipped to claim completion.
