# REPAIR-FOG-RECOVERY-01-02 Repair Evidence

## Scope

- Finding: `FOG-RECOVERY-R02`.
- Start HEAD: `b381e769a0beb644cdc897ab88555f03c4697c89`.
- Lineage confirmed: `58ff346` candidate, `2e6ef66` review, `9ce4d80` Repair-1, `b381e76` re-review.
- Production impact: none. No replay, training, ranking, promotion, publish, push, external service, live circuit cleanup, or runtime artifact cleanup was executed.

## Change

- `scripts/run_controlled_grid_drain_host_runner.py` now runs a fail-closed pre-inventory refresh sequence:
  - `build_research_campaign_progress.py`
  - `build_research_fog_map.py`
  - `verify_research_fog_map.py`
- Weekend inventory build/verify and bounded frontier verification now run only after that pre-inventory fog verifier passes.
- If the pre-inventory refresh or verifier fails, the runner writes FAILED status/gates without rebuilding inventory or producing a false OK.
- Post-inventory rollup still performs a final research progress / fog map / fog verifier refresh so linkage artifacts remain current after rollup.

## Red To Green Evidence

- Added `tests/test_controlled_grid_host_runner_order.py`.
- The first test models fresh run history at `33360` while the stale fog map remains at `33358`; inventory build fails unless the runner first rebuilds and verifies the fog map.
- The old order would call `build_inventory_and_bounded_frontier_queue` before `verify_fog_map_before_inventory`, tripping the fake stale-map failure.
- The new order is:
  - `build_research_progress_before_inventory`
  - `build_fog_map_before_inventory`
  - `verify_fog_map_before_inventory`
  - `build_inventory_and_bounded_frontier_queue`
- The second test proves a failed pre-inventory fog verifier stops before inventory build.

## Verification Commands

```text
uv run python -m pytest -q tests/test_controlled_grid_host_runner_order.py tests/test_weekend_universe_inventory_snapshot.py
```

Result:

```text
5 passed in 0.03s
```

```text
.venv/bin/python -m py_compile scripts/run_controlled_grid_drain_host_runner.py
```

Result: `OK`.

```text
bash -n tests/test_fog_research_retry_circuit.sh
bash -n tests/test_research_failure_fingerprint.sh
```

Result: `OK`.

```text
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_research_failure_fingerprint.sh
```

Result: `OK`.

```text
git diff --check
```

Result: `OK`.

```text
.venv/bin/python -m pytest -q
```

Result:

```text
473 passed, 1 failed, 4 warnings, 246 subtests passed in 102.98s
```

Remaining failure:

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
failed check: evidence_exists
missing evidence paths include artifacts/model_experiments/*, data/reference/*, and data/clean/features.parquet
```

This is the existing artifact-evidence gap already recorded in `docs/evidence/FOG-RECOVERY-01/verification.md`; it is outside this repair's allowed implementation surface.

## Remaining Risk

- Full pytest is not completely green in this worktree because required historical evidence/data artifacts are absent.
- `FOG-RECOVERY-R02` itself is closed by targeted red-capable order tests and preserved fail-closed behavior.
