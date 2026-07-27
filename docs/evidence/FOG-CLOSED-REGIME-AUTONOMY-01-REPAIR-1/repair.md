# FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1 Evidence

## Status

`DELIVERED_REPAIR_1_CANDIDATE`

Fixed repair base:
`5e1de6aa170f7c2446e5da76fadfa75a88495e54`.

No live retry state/context, LaunchAgent, queue, production model, ranking, weights,
promotion, merge, push, kickstart or acceptance action was performed.

## Implemented trust boundaries

### Processed IDs

- Research-map and weekend-inventory processed sets now come from separate artifact
  representations.
- The map authority reads completed map scenarios plus its declared run-history
  lineage; the inventory stores a compact independent `processed_records` snapshot.
- Both sets use the same normalized completion requirements and reject missing IDs,
  duplicate IDs, missing artifacts, schema/contract/date/source-hash failures, count
  mismatch, missing/unexpected IDs and forged IDs.
- The receipt stores both artifact paths, content hashes, schemas, source hashes,
  processed counts and a bounded symmetric-difference sample.

### Runtime receipt

- Receipt schema advanced to `closed-regime-runtime-receipt.v2`.
- The final receipt is generated only after the daily artifact exists and binds:
  run date, queue owner, runner identity, exact schema with no unknown fields,
  history path/schema/hash/source date, contract path/hash, exact regime,
  state transition, daily artifact path/schema/hash/date, topic-run identities and
  digest, and `NO_PRODUCTION_CHANGE`.
- Recovery validates the stored final receipt through the daily verifier; it no longer
  overwrites the receipt with a fresh self-reported canary.

### Production baseline

- Recovery now requires a separate `fog-production-hash-baseline.v1` receipt.
- The baseline must contain exactly five roles: model, baseline, ranking, weights and
  promotion, each with canonical path and content hash.
- Verification recomputes every current hash and rejects missing roles/files, path-set
  drift, hash drift, schema drift and source-identity drift.
- Expected source identity comes from the verifier checkout's actual `git rev-parse
  HEAD`; it is not accepted from runtime payload or environment input.
- The recovery worker fails closed when no trusted baseline path is supplied.

## Red to green

Evidence: `phase0-red.md`.

```text
attack command before repair: 3 failed in 27.58s
same command after repair:     3 passed in 2.06s
```

Additional legitimate and mutation coverage is included in:

- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `tests/test_fog_research_retry_circuit.sh`

## Verification

Trusted runtime:
`<main-repo>/.venv/bin/python`; cwd and `PYTHONPATH` were this repair worktree.

Targeted:

```text
tests/test_weekend_universe_inventory_snapshot.py
tests/test_daily_research_quota_verifier.py
tests/test_fog_closed_regime_runtime.py

21 passed in 2.51s
```

Shell/compile gates:

```text
bash tests/test_fog_research_retry_circuit.sh: PASS
bash tests/test_research_lock_contention.sh: PASS
bash -n scripts/run_daily_research_quota.sh: PASS
bash -n scripts/run_fog_research_worker.sh: PASS
py_compile changed Python verifier/builder files: PASS
```

Full suite first exposed the known clean-worktree ignored-evidence provisioning gap:

```text
549 passed, 1 failed, 246 subtests passed
failed check: research_component_ledger evidence_exists
```

After temporary read-only symlinks to the main repo's existing ignored historical
evidence/reference fixtures, the isolated worktree full suite passed:

```text
551 passed, 4 warnings, 246 subtests passed in 64.65s
```

All temporary symlinks were removed immediately after the run.

## Protected hashes

Tracked protected files are byte-identical to the repair base candidate:

| Role | Path | SHA-256 before/after |
|---|---|---|
| model | `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| baseline | `models/baseline_stats.json` | `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7` |
| weights | `config/signals.yaml` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` |
| promotion contract | `app/modeling/model_runtime_promotion.py` | `2add0872011c47640f8acafc6e594f4186a33eb15a8640c8b4aa46924f78d9b1` |

The ignored production ranking artifact is intentionally absent from the isolated
worktree. Its last trusted candidate evidence hash remains
`21e3e28aef85da638f22a4b682f754eede09d0c8debf2d92135d9d6317391bc8`;
the repair diff contains no ranking artifact path and did not read or modify live
production ranking state.

## Changed-files allowlist

- `scripts/build_weekend_universe_inventory.py`
- `scripts/run_daily_research_quota.sh`
- `scripts/run_fog_research_worker.sh`
- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_daily_research_quota.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_processed_id_authority.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_fog_research_retry_circuit.sh`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/**`
- `docs/tasks/2026-07-27_FOG-CLOSED-REGIME-AUTONOMY-01_REPAIR-1_verifier_trust_boundaries.md`

Final candidate SHA is reported by the commit delivery receipt.
