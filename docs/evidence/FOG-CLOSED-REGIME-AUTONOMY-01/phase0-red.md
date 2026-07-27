# FOG-CLOSED-REGIME-AUTONOMY-01 Phase 0 Red Evidence

## Preflight

- source SHA: `f59e781c5742ec995206b3c3ec6aefe346670818`
- starting HEAD: `c2ed61956524385779bd9383cb9faa0c5beaa099`
- branch: detached HEAD
- cwd/worktree: `<codex-managed-worktree>/TOP10new`
- worktree registered: `true`
- initial worktree clean: `true`
- `.git/index.lock`: absent
- Python capability: `ready`
- CodeGraph: `degraded:fallback_rg`

`f59e781c5742ec995206b3c3ec6aefe346670818` is an ancestor of starting HEAD.
The only intervening diff is this task card.

## Immutable source diagnosis

Read-only source fixture:

- `<main-workspace>/artifacts/autonomous_research/run_history.jsonl`
- SHA-256: `f0e51976e54cadcfd5d7b356f1f457659b8bb2eebf6cc89c3f343693239e7941`

Deterministic recompute:

```text
base_ids=9564
completed_v2=23794
research_map_processed=33358
latest_v2=23796
weekend_inventory_processed=33360
inventory_minus_map=2
map_minus_inventory=0
```

The two `inventory_minus_map` IDs are:

1. `artifacts-backtest-liquidity_quality_candidate_universe_shadow_rankings_2026-06--514eedec:long_horizon|horizon_3|stop_none|take_profit_0.15|group_exposure_none|regime_gate_ALL|risk_guard_NONE|entry_filter_TOPIC_DEFAULT`
   - source line: `23977`
   - source: `weekend_representative_replay`
   - status: `completed`
   - artifact: `artifacts/weekend_training/weekend_representative_replay_2026-07-21.json`
2. `artifacts-backtest-liquidity_quality_candidate_universe_shadow_rankings_2026-06--514eedec:long_horizon|horizon_3|stop_none|take_profit_0.25|group_exposure_none|regime_gate_ALL|risk_guard_NONE|entry_filter_TOPIC_DEFAULT`
   - source line: `23985`
   - source: `weekend_representative_replay`
   - status: `completed`
   - artifact: `artifacts/weekend_training/weekend_representative_replay_2026-07-21.json`

Classification reason: both rows declare the v2 schema but all three v2 expansion
coordinates are defaults (`ALL`, `NONE`, `TOPIC_DEFAULT`). Research-map expansion
authority therefore excludes them, while weekend inventory currently treats any latest
row as processed. The immutable fixture reproduces the difference, so `H-RACE` is
rejected and `H-SEMANTICS` is confirmed.

## Red-capable command

```text
.venv/bin/python -m pytest -q \
  tests/test_weekend_universe_inventory_snapshot.py::test_inventory_uses_research_map_processed_id_semantics_for_default_v2_rows \
  tests/test_fog_closed_regime_runtime.py
```

Pre-fix result:

```text
3 failed, 3 passed
```

Expected red failures:

- inventory returns the two default-coordinate IDs instead of `[]`;
- daily public path does not contain `--closed-regime-research`;
- initial missing-history assertion used a stricter exception type than the existing
  fail-closed behavior and was corrected to assert the existing deterministic
  `ValueError`.

The future-only, transition, and `UNKNOWN` mutation cases already fail closed before
public wiring. They are retained as regression gates.

## Circuit and production before hashes

- retry state SHA-256:
  `27bf4bb57ef7923975c7a286af41c4590a7a1eaade6195e0cff643eefb976659`
- retry context SHA-256:
  `f7f5abf4fb2e5ae5b0b0fef100d6b10e7cb7f1824f1a76b52f0f8f82da7c96ec`
- production model SHA-256:
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- production baseline SHA-256:
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`
- production ranking `ranking_2026-07-27.csv` SHA-256:
  `21e3e28aef85da638f22a4b682f754eede09d0c8debf2d92135d9d6317391bc8`

No retry state/context or production artifact was modified during Phase 0.
