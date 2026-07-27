# FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2 Evidence

## Status

`DELIVERED_REPAIR_2_CANDIDATE`

Fixed repair base:
`394b90feae0a5c11a75a578ea4e721b44bb3893d`.

The candidate SHA is delivered by the final commit receipt. A commit cannot contain its
own SHA without changing that SHA.

No live retry state/context, queue, LaunchAgent, production artifact, merge, push,
kickstart or runtime acceptance action was performed.

## Authority closure

### Canonical protected role-path contract

- `scripts/fog_authority_contracts.py` is the tracked, versioned authority outside the
  baseline payload.
- protected roles are exactly model, baseline, ranking, weights and promotion.
- each role maps to a fixed repo-relative path; ranking is the fixed
  `artifacts/ranking_{run_date}.csv` template.
- canonical baseline output is fixed to
  `artifacts/autonomous_research/fog_production_hash_baseline_{run_date}.json`.
- baseline schema v2 binds:
  - canonical contract hash;
  - source commit;
  - run date;
  - timezone-aware creation boundary;
  - current protected artifact hashes.
- create-once uses exclusive file creation and rejects an existing file, alternate
  output path, missing canonical artifacts and path escape.
- recovery verification always recomputes the canonical role paths from the tracked
  contract. It never derives paths from baseline entries.
- Fog worker ignores attacker-supplied baseline env paths and only reads the canonical
  baseline. It has no create/update/overwrite path.

The explicit pre-recovery create command is implemented but was not executed:

```bash
<main-repo>/.venv/bin/python scripts/verify_fog_closed_regime_recovery.py \
  --create-production-hash-baseline \
  --run-date YYYY-MM-DD \
  --production-hash-baseline \
  artifacts/autonomous_research/fog_production_hash_baseline_YYYY-MM-DD.json
```

It must run after mainline integration and before any recovery/worker mutation.

### Recomputed exact regime and fixed freshness

- daily verification first binds the real history path, schema and SHA-256.
- it then calls the accepted `current_regime_context()` authority with the artifact run
  date.
- expected base regime, sorted family tags, identity ID and source trade date are
  recomputed and compared exactly.
- `generated_at` must be timezone-aware RFC3339, normalize to the run date, not be in
  the future and be no older than the verifier-fixed 24-hour lifecycle window.
- receipt and environment payloads cannot change the freshness policy.

### Canonical source roles, paths and hashes

- research-map source roles are exactly:
  `topic_registry`, `run_history`.
- weekend-inventory source roles are exactly:
  `research_map`, `topic_registry`, `run_history`.
- both builders emit `fog-source-lineage.v1` with the tracked contract hash, exact
  repo-relative paths and SHA-256 values.
- the verifier rejects schema/contract drift, role-set additions/removals, path drift,
  missing files, hash drift, `..` escape and symlink escape.
- hashes are recomputed from the canonical files; legacy arbitrary 64-character digest
  mappings are no longer an authority.

## Canonical contract hashes

| Contract | SHA-256 |
|---|---|
| protected roles/paths | `746738190aeb9063f5b37ba42b4f50ed9df3952e251bcde180ab0c75d9281917` |
| research-map source roles/paths | `6e2997a68b3e215cda201488e41a2387b56badd0ae52024b05df6a350ed7e3f1` |
| weekend-inventory source roles/paths | `e924d55c67766ce26053ce873172c3b4297efaadb8ef431f14d009ab02116348` |

## Verification

Trusted runtime:
`<main-repo>/.venv/bin/python`; cwd and `PYTHONPATH` were this worktree.

Hostile red-to-green evidence:
`phase0-red.md`.

Final hostile replay:

```text
10 passed in 2.03s
```

Targeted and directly affected tests:

```text
tests/test_weekend_universe_inventory_snapshot.py
tests/test_daily_research_quota_verifier.py
tests/test_fog_closed_regime_runtime.py
tests/test_research_fog_map_refactor.py

34 passed in 2.42s
```

Shell and syntax gates:

```text
bash tests/test_fog_research_retry_circuit.sh: PASS
bash tests/test_research_lock_contention.sh: PASS
bash -n scripts/run_daily_research_quota.sh: PASS
bash -n scripts/run_fog_research_worker.sh: PASS
bash -n tests/test_fog_research_retry_circuit.sh: PASS
py_compile changed Python authority/builder/verifier files: PASS
```

Full suite without ignored historical fixtures reproduced the known clean-worktree
provisioning gap:

```text
560 passed, 1 failed, 4 warnings, 246 subtests passed in 59.43s
failure: research_component_ledger evidence_exists
```

After temporary read-only symlinks to the main repo's existing gitignored historical
evidence/reference fixtures:

```text
561 passed, 4 warnings, 246 subtests passed in 59.54s
```

All 12 temporary symlinks were removed immediately after the run. This provisioning is
not candidate functionality.

## Protected hashes

Tracked protected files are byte-identical to the fixed Repair-2 base:

| Role | Path | SHA-256 before/after |
|---|---|---|
| model | `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| baseline | `models/baseline_stats.json` | `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7` |
| weights | `config/signals.yaml` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` |
| promotion | `app/modeling/model_runtime_promotion.py` | `2add0872011c47640f8acafc6e594f4186a33eb15a8640c8b4aa46924f78d9b1` |

The ignored production ranking artifact is absent from this isolated worktree. Its
fixed-base evidence hash remains
`21e3e28aef85da638f22a4b682f754eede09d0c8debf2d92135d9d6317391bc8`.
This repair did not read or modify live production ranking state.

## Changed-files allowlist

Preflight-only additions retained from `394b90f..ee4204d`:

- `docs/evidence/REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/review.md`
- `docs/tasks/2026-07-27_FOG-CLOSED-REGIME-AUTONOMY-01_REPAIR-2_final_authority_closure.md`

Repair implementation/evidence:

- `scripts/fog_authority_contracts.py`
- `scripts/build_research_fog_map.py`
- `scripts/build_weekend_universe_inventory.py`
- `scripts/run_fog_research_worker.sh`
- `scripts/verify_daily_research_quota.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_processed_id_authority.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_fog_research_retry_circuit.sh`
- `tests/test_research_fog_map_refactor.py`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2/**`
- Repair-2 task status

`scripts/build_research_fog_map.py` is the direct producer seam required to make the
research-map artifact declare canonical source hashes. No research policy, ranking,
model, weight, promotion, API, UI or external-data behavior changed.

## Acceptance mapping

- `SC-R2-01`: PASS in candidate tests. Protected paths come only from the tracked
  contract; canonical baseline creation is create-once and recovery is read-only.
- `SC-R2-02`: PASS in candidate tests. Exact regime is recomputed from the bound history
  and RFC3339 freshness is fixed by verifier policy.
- `SC-R2-03`: PASS in candidate tests. Both artifact families require canonical source
  roles/paths, no escape and recomputed SHA-256 equality.
- `SC-R2-04`: PASS for candidate verification. Hostile, targeted, shell and full suite
  are green; protected tracked hashes are unchanged.

Independent re-review remains mandatory. This evidence does not grant runtime
acceptance or production recovery authority.
