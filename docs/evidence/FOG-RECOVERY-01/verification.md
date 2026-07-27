# FOG-RECOVERY-01 Verification

## Scope

- Worktree: detached Codex worktree, not the main checkout.
- Production impact: none. No ranking, model, weight, promotion, publish, Discord, or trading writes were executed.
- Runtime artifacts/logs/retry state: not deleted or overwritten during verification.

## Preflight

```text
bash ${AI_CORE_DIR:-$HOME/ai-core}/scripts/worktree_capability_preflight.sh --check --root .
status: OK
python_tests: needs_prepare
codegraph: degraded:fallback_rg
```

```text
bash ${AI_CORE_DIR:-$HOME/ai-core}/scripts/worktree_capability_preflight.sh --prepare --require-python-tests --root .
status: OK
python_tests: ready
```

## Targeted Regression

```text
.venv/bin/python -m pytest -q tests/test_weekend_universe_inventory_snapshot.py
... [100%]
3 passed in 0.03s
```

Coverage:

- Rebuilds inventory when the source snapshot advances during build.
- Fails loud after a bounded rebuild when source snapshot counts remain inconsistent.
- Keeps `verify_weekend_universe_inventory.py` fail-closed for stale inventory snapshot counts.

```text
bash tests/test_fog_research_retry_circuit.sh
status: OK
```

Coverage:

- Circuit-open state is not cleared without explicit recovery mode.
- Explicit recovery mode does not clear state when inventory verification fails.
- Explicit recovery mode rotates old state/context only after verifier success; a later new failure gets a new fingerprint and opens a fresh circuit when retries are exhausted.

```text
bash tests/test_research_failure_fingerprint.sh
status: OK
```

Coverage:

- Existing fingerprint isolation still ignores stale prior-batch handoff failures.

```text
.venv/bin/python scripts/verify_pm_research_harness_loop.py
status: OK
fog_worker_boundary: true
```

## Required Gates

```text
bash -n scripts/run_fog_research_worker.sh
status: OK
```

```text
git diff --check
status: OK
```

```text
.venv/bin/python -m pytest -q
result: FAILED
passed: 471
failed: 1
warnings: 4
subtests passed: 246
```

Failure is outside this card's allowed implementation surface:

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
failed check: evidence_exists
missing evidence paths include artifacts/model_experiments/*, data/reference/*, and data/clean/features.parquet
```

The same test fails when run alone, so it is recorded as a pre-existing/environment artifact gap rather than a regression from this card.

