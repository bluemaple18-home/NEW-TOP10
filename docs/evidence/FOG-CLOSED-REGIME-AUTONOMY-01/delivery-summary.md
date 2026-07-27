# FOG-CLOSED-REGIME-AUTONOMY-01 Delivery Summary

## Current state

`BLOCKED_RUNTIME_INTEGRATION`

The candidate implementation is complete and all local deterministic gates pass, but the
card's live three-cycle condition cannot be executed without first integrating the
candidate into the checkout used by the installed LaunchAgent. Executor authority
explicitly forbids that integration action.

## Implemented

- Weekend inventory now reuses the research-map completion predicate, removing the two
  default-coordinate overcounts.
- A bounded processed-ID verifier preserves the pre-fix two IDs and proves the candidate
  symmetric difference is empty.
- Daily public research always enables closed-regime mode and supplies a verified
  `market-regime-history.v2` artifact.
- Runtime receipt includes history hash, contract hash, exact regime, state transition,
  topic-run linkage through the daily artifact, and production-impact declaration.
- Missing/future/transition/`UNKNOWN` history fails closed without legacy fallback.
- Explicit circuit recovery now invokes a bounded gate covering processed IDs, map,
  inventory, closed-regime runtime, targeted tests, queue ownership, and production
  hashes before state rotation.
- PM harness queue ownership remains unchanged; only `fog_worker` owns mutation.

## Changed-files allowlist

- `scripts/build_weekend_universe_inventory.py`
- `scripts/run_daily_research_quota.sh`
- `scripts/run_fog_research_worker.sh`
- `scripts/verify_daily_research_quota.py`
- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_processed_id_authority.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_fog_research_retry_circuit.sh`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01/**`

All paths are within the task allowlist.

## Required follow-up authority

Mainline must integrate the candidate, then independently run:

1. production hash capture;
2. bounded recovery gate;
3. explicit circuit recovery;
4. LaunchAgent kickstart;
5. three consecutive 900-second scheduler cycles with quota `5`;
6. post-cycle production/circuit hash comparison and independent Review.

Until those receipts exist, status must not be changed to `DELIVERED_CANDIDATE` or
accepted.
