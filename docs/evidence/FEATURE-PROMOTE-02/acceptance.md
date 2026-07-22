# FEATURE-PROMOTE-02 Mainline Acceptance

Status: `ACCEPTED_NO_GO`

The fail-closed decision contract is accepted after two bounded Repair rounds
and original-Reviewer final re-review GO. The promotion decision itself remains
NO_GO because all 12 required evidence rows are missing. This distinction is
intentional: implementation acceptance does not imply feature promotion.

## Lineage

- base: `b5a5e6394fa1bdb4f82124ffa5e1694844605f28`
- original candidate: `e057ff9e5256091c7825251c7a9e7e43ed324ebe`
- initial Review NO_GO: `86ec0e2`
- Repair 1: `0079370cf4e6d46fe718579de4a78fb3c5c3ac73`
- Repair 1 re-review NO_GO: `76b066bfd02ff1e1cd88d55da1553562f29adece`
- Repair 2: `1a08f38550a73dfbf680de7ff441e5b6f82baa89`
- final re-review GO: `6f92520047abbd73d1ba6875a9c75440316cec28`

The accepted contract binds evidence semantics, verdict, base/candidate/data
identity, source hashes, portable real-file paths, freshness and an explicit
decision_as_of. Placeholder, tampered, stale, future, duplicate, symlink and
out-of-repo evidence fail closed. The actual artifact hash is
`5edf187317d034288124c7a8378301b10e4591ef276a50e8bdb48c203b013d87`.

Graph tolerance risk and TPEx KEEP_BLOCKED remain explicit. RankingPolicy,
weights, runtime, daily path and deploy configuration are unchanged.
