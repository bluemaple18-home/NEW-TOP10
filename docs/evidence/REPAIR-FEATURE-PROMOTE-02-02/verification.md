# REPAIR-FEATURE-PROMOTE-02-02 Verification

## Result

Repair 2 closes the builder freshness P1. `decision_as_of` is an explicit
UTC ISO-date field in the decision artifact and is SHA-256 bound. Builder and
verifier apply the same fixed per-kind freshness contract: one-day maximum
age and a 365-day evidence date window. Exact boundaries pass; future, stale,
invalid, reversed, and over-window dates fail closed.

- actual decision: `NO_GO`
- missing evidence: all 12 required rows
- retained attribution: Graph `RISK`; TPEx `KEEP_BLOCKED`
- actual artifact: `.work/REPAIR-FEATURE-PROMOTE-02-02/actual_no_go.json`
- actual artifact SHA-256: `5edf187317d034288124c7a8378301b10e4591ef276a50e8bdb48c203b013d87`
- decision_as_of: `2026-07-22`

## RED to GREEN

- fresh probe before repair: builder returned `GO` for `as_of=2999-01-01`
- fresh probe after repair: `all_pass: true`; builder returns `NO_GO`
- original Repair 1 adversarial probes: `all_pass: true`
- affected promotion tests: `8 passed`
- builder/verifier actual artifact: `NO_GO` / typed `OK`
- `py_compile`: passed
- `git diff --check`: passed

Only the allowlisted builder, verifier, promotion tests, and this Repair 2
evidence were changed. No ranking, model, runtime, daily, deploy, or prior
review/Repair 1 evidence was modified.
