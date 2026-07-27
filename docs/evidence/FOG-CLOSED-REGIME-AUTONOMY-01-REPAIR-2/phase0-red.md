# FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2 Phase 0 Red

## Boundary

- fixed repair base: `394b90feae0a5c11a75a578ea4e721b44bb3893d`
- starting HEAD: `ee4204d54afc761d2a84a17b07f513997d8f1cdf`
- base-to-starting-HEAD additions:
  - Repair-1 formal `NO_GO` review evidence
  - Repair-2 task card
- starting worktree: clean
- runtime: trusted main-repo Python at `<main-repo>/.venv/bin/python`
- live state, queue, LaunchAgent, production artifacts, merge, push, kickstart and
  acceptance: not accessed or executed

## Red-capable command

```bash
PYTHONPATH=<repo-root> <main-repo>/.venv/bin/python -m pytest -q \
  tests/test_fog_closed_regime_runtime.py::test_production_baseline_uses_canonical_contract_and_is_create_once \
  tests/test_fog_closed_regime_runtime.py::test_daily_verifier_rejects_unfresh_or_forged_exact_regime \
  tests/test_fog_closed_regime_runtime.py::test_processed_source_lineage_rejects_hostile_paths_and_sets
```

Pre-fix Repair-1 candidate result:

```text
FFFFFFFFFF
10 failed in 2.20s
```

## Bypass evidence

### Production baseline authority

- canonical protected-path and create-once seam did not exist.
- old candidate failed the hostile test with:
  `AttributeError: canonical_protected_paths`.
- the test covers:
  - model drift followed by attempted baseline rebuild;
  - existing baseline overwrite;
  - arbitrary attacker-controlled five-file protected set;
  - alternate baseline output path.

### Runtime receipt freshness and exact regime

The Repair-1 candidate returned `COMPLETED` for all four attacks:

- `generated_at=1999-01-01T00:00:00+00:00`;
- `generated_at=2199-01-01T00:00:00+00:00`;
- timezone-naive `generated_at=2099-01-05T00:00:00`;
- forged base regime, family tags and identity ID.

### Processed source lineage

The Repair-1 candidate returned `OK` for all five attacks:

- missing canonical source;
- source-role set addition;
- source-role set removal;
- `../` path escape;
- canonical-looking symlink escape outside the repo root.

The old verifier accepted the unrelated `source_hashes` mapping because each digest was
merely 64 characters.

## Green replay

The unchanged command after Repair-2:

```text
..........                                                               [100%]
10 passed in 2.03s
```
