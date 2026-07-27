# FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1 Phase 0 Red

## Boundary

- repair base candidate: `5e1de6aa170f7c2446e5da76fadfa75a88495e54`
- starting HEAD: `f87f0f60d4e0bd6539f2d1aaab68d7909d12192f`
- starting diff from candidate: Repair-1 card only
- runtime: trusted main-repo Python at `<main-repo>/.venv/bin/python`
- test cwd and `PYTHONPATH`: this repair worktree
- live state, LaunchAgent, queue and production artifacts: not accessed or modified

## Red-capable command

```bash
PYTHONPATH=<repair-worktree> <main-repo>/.venv/bin/python -m pytest -q \
  tests/test_fog_closed_regime_runtime.py::test_processed_id_verifier_rejects_forged_inventory_id \
  tests/test_fog_closed_regime_runtime.py::test_daily_verifier_rejects_stale_forged_incomplete_runtime_receipt \
  tests/test_fog_closed_regime_runtime.py::test_production_hash_gate_rejects_drift_against_trusted_baseline
```

Pre-fix result:

```text
FFF
3 failed in 27.58s
```

## Attack results

1. Forged inventory ID:
   - map IDs: `processed-a`, `processed-b`
   - inventory IDs: `processed-a`, `forged-id`
   - both artifact counts: `2`
   - old result: `status=OK`
   - expected: `FAILED`, `map_only=["processed-b"]`,
     `inventory_only=["forged-id"]`
2. Stale/forged/incomplete runtime receipt:
   - receipt date: `1999-01-01`
   - expected run date: `2099-01-05`
   - queue owner and runner identity: forged
   - `state_transition`: missing
   - old result: `COMPLETED`
   - expected: `BLOCKED` with field-specific failed checks
3. Production hash drift:
   - baseline saved for five protected roles
   - model fixture changed after baseline
   - old result: no trusted-baseline comparison seam
   - observed red: `AttributeError` for the absent baseline builder/comparator
   - expected: recovery denial with `hash_drift=["model"]`

## Green replay

The unchanged command after repair:

```text
3 passed in 2.06s
```
