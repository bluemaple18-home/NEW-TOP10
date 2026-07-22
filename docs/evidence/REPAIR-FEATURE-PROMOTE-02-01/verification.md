# REPAIR-FEATURE-PROMOTE-02-01 Verification

## Result

The repaired builder and verifier recompute the repository decision as `NO_GO`.
The artifact is kept under the repair work area and is not promotion evidence.

- base SHA: `b5a5e6394fa1bdb4f82124ffa5e1694844605f28`
- candidate SHA: `e057ff9e5256091c7825251c7a9e7e43ed324ebe`
- artifact: `.work/REPAIR-FEATURE-PROMOTE-02-01/tmp/actual_no_go.json`
- SHA-256: `f12d7c38d27d41e969416f9e9bf94a3b122c0f16a6d62ab059ddb733e31a1890`
- missing evidence: all 12 required rows
- retained attribution: Graph residual `RISK`; TPEx `KEEP_BLOCKED`

## RED to GREEN

- original reviewer probes: all required fail-closed cases passed
- original and affected tests: `23 passed, 4 subtests passed`
- synthetic complete GO positive control: passed only in the test's ephemeral temporary directory
- builder/verifier: `NO_GO` / typed `OK` verification
- `py_compile`: passed
- `git diff --check`: passed

The contract now binds the fixed review range, versioned closed evidence
schema, evidence kind/verdict/identity, universe/date/cost identity, metrics
and thresholds, freshness/as-of, source hashes, deterministic manifest and
decision recomputation. Paths must be portable in-repository regular files;
absolute, traversal, out-of-repo and symlink paths fail closed.
