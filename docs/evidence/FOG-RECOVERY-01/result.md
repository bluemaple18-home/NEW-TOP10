# FOG-RECOVERY-01 Result

## Summary

Candidate implementation completed.

- `scripts/build_weekend_universe_inventory.py` now treats the fog map counts and generated inventory counts as one bounded snapshot contract.
- If the source snapshot advances during inventory construction, the builder retries once from a fresh snapshot.
- If the counts are still inconsistent after the bounded rebuild, the builder fails loud instead of writing an apparently OK inventory.
- `scripts/verify_weekend_universe_inventory.py` remains fail-closed; stale or inconsistent counts still fail verification.
- `scripts/run_fog_research_worker.sh` now keeps an open retry circuit closed by default and only rotates old retry state/context when `TOP10_FOG_RESEARCH_RECOVER_CIRCUIT=1` and weekend inventory verification passes.
- A new failure after verified recovery is not swallowed; it is fingerprinted and counted as a fresh failure.

## Changed Files

- `scripts/build_weekend_universe_inventory.py`
- `scripts/run_fog_research_worker.sh`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `tests/test_fog_research_retry_circuit.sh`
- `docs/evidence/FOG-RECOVERY-01/verification.md`
- `docs/evidence/FOG-RECOVERY-01/result.md`

## Red To Green Evidence

- The new snapshot regression encodes the prior race: first build attempt has `current_processed_count` ahead of `map_expanded_processed`; the fixed builder performs a bounded rebuild and returns a consistent snapshot.
- Under the previous single-pass builder, that test would have returned the stale source count and failed the assertion that inventory/source counts both equal the rebuilt snapshot.
- The stale snapshot verifier test confirms fail-closed behavior still rejects the same class of inconsistency.
- The retry circuit shell regression confirms recovery is blocked until verifier success and that old fingerprints are rotated rather than silently reused.

## Recovery Flow

The safe recovery action is explicit:

```text
TOP10_FOG_RESEARCH_RECOVER_CIRCUIT=1 bash scripts/run_fog_research_worker.sh
```

When an open circuit exists, the worker first runs:

```text
scripts/verify_weekend_universe_inventory.py --date "$RUN_DATE" --output logs/fog_research_retry_${RUN_DATE//-/}.recovery_verification_<stamp>.json
```

Only if that verifier exits OK does it rotate:

```text
logs/fog_research_retry_<date>.state -> logs/fog_research_retry_<date>.state.recovered.<stamp>
logs/fog_research_retry_<date>.context.log -> logs/fog_research_retry_<date>.context.log.recovered.<stamp>
```

If verifier fails, the circuit remains open and the worker exits without running research.

## Remaining Risk

- Full pytest has one unrelated artifact-evidence failure in `tests/test_research_component_ledger.py`; see `verification.md`.
- This candidate does not execute production recovery, publish, replay drain, model training, or promotion.
