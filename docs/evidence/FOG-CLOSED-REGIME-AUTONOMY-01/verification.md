# FOG-CLOSED-REGIME-AUTONOMY-01 Verification

## Status

`BLOCKED_RUNTIME_INTEGRATION`

Implementation and deterministic gates are green. Live circuit recovery and scheduler
cycles were not executed because the installed LaunchAgent points to the main checkout,
while this Executor is prohibited from merge/deploy.

## Red to green

Phase 0:

```text
.venv/bin/python -m pytest -q \
  tests/test_weekend_universe_inventory_snapshot.py::test_inventory_uses_research_map_processed_id_semantics_for_default_v2_rows \
  tests/test_fog_closed_regime_runtime.py

pre-fix: 3 failed, 3 passed
```

S-SEMANTICS:

```text
.venv/bin/python -m pytest -q \
  tests/test_weekend_universe_inventory_snapshot.py \
  tests/test_controlled_grid_host_runner_order.py

6 passed
```

S-WIRING checkpoint:

```text
.venv/bin/python -m pytest -q \
  tests/test_fog_closed_regime_runtime.py \
  tests/test_daily_research_quota_verifier.py \
  tests/test_weekend_universe_inventory_snapshot.py \
  tests/test_controlled_grid_host_runner_order.py \
  tests/test_regime_research_autonomy.py

70 passed
```

Shell gates:

```text
bash tests/test_fog_research_retry_circuit.sh
status: OK

bash tests/test_research_lock_contention.sh
status: OK

bash -n scripts/run_daily_research_quota.sh
status: OK

bash -n scripts/run_fog_research_worker.sh
status: OK
```

Compile:

```text
.venv/bin/python -m py_compile \
  scripts/build_weekend_universe_inventory.py \
  scripts/run_controlled_grid_drain_host_runner.py \
  scripts/run_autonomous_research.py \
  scripts/verify_closed_regime_runtime.py \
  scripts/verify_daily_research_quota.py \
  scripts/verify_processed_id_authority.py \
  scripts/verify_fog_closed_regime_recovery.py

status: OK
```

Full suite initially reproduced the known ignored-artifact provisioning debt:

```text
545 passed, 1 failed, 246 subtests passed
failed check: evidence_exists
```

After provisioning read-only symlinks to the main workspace's existing ignored evidence:

```text
546 passed, 4 warnings, 246 subtests passed
```

Diff hygiene:

```text
git diff --check
status: OK
```

## Processed-ID authority

Evidence:
`docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01/processed-id-authority.json`

```text
research_map_processed=33358
weekend_inventory_processed=33358
symmetric_difference=[]
pre_fix_inventory_minus_map_count=2
```

The two pre-fix IDs and their source rows are preserved in `phase0-red.md` and the JSON
receipt. No count tolerance is used.

## Closed-regime lineage

Evidence:

- `market_regime_history_2026-07-27.json`
- `closed-regime-runtime-receipt.json`

```text
history_schema=market-regime-history.v2
history_sha256=dae9cf0c97f8e0d286e5a0f5e63b71c53bd0088195bcac4e8702acda679088ba
contract_sha256=ea9d2618dfff8efbcbff452415999483a9b5771b4c4ff1aa41c60538aea6bd39
exact_regime=RISK_OFF|
closed_regime_research=true
production_impact=NO_PRODUCTION_CHANGE
```

Missing, future-only, transition, and `UNKNOWN` histories fail closed in targeted tests.
The public daily command test proves both closed-regime CLI arguments and receipt
materialization.

## Runtime blocker

Installed LaunchAgent:

```text
label=com.new-top10.fog-research-worker
program=<main-workspace>/scripts/run_fog_research_worker.sh
interval_seconds=900
```

Candidate worktree:

```text
<codex-managed-worktree>/TOP10new
```

The paths differ. Kickstarting the installed job would execute old main code. Copying,
merging, or deploying candidate code to the main checkout is outside Executor authority.
Consequently:

- live circuit state/context were not rotated;
- LaunchAgent was not kickstarted;
- three scheduler-cycle receipts were not generated;
- no live research execution claim is made.

## Production and circuit hashes

Before and after implementation verification are unchanged:

- model:
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- baseline:
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`
- ranking `ranking_2026-07-27.csv`:
  `21e3e28aef85da638f22a4b682f754eede09d0c8debf2d92135d9d6317391bc8`
- retry state:
  `27bf4bb57ef7923975c7a286af41c4590a7a1eaade6195e0cff643eefb976659`
- retry context:
  `f7f5abf4fb2e5ae5b0b0fef100d6b10e7cb7f1824f1a76b52f0f8f82da7c96ec`

No production artifact or live retry file was modified.
