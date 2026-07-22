# TSKG-MFO-THEME-01 Acceptance

Status: "ACCEPTED"

## Lineage

- base: `b79fed679df53d498945b352e69e611a27679513`
- original candidate: `04f1380d7390609bea854afd354f7f0859f1d3e0`
- initial independent review: `NO_GO` at `69282b53763b61c7f44e6685ec25ac6845b7d524`
- repair candidate: `71c02aa8a4f9106364e97da97ffefb887db0833e`
- original Reviewer re-review: `GO` at `ca077d987d1b1dbc653026848454b5ee9e8fa5bd`

The repair canonicalizes membership rows before hashing/storage and rejects overlapping inclusive effective intervals for a security/theme pair. The re-review confirmed distinct-theme denominators and source-net mass conservation.

The candidate implements a versioned, evidence-located Theme membership snapshot and deterministic institutional-flow aggregation for the approved offline fixture. It reports institutional buy, sell, net, coverage, missing count, stale count, and freshness per Theme.

The contract is TWSE-only. TPEx remains "KEEP_BLOCKED"; no TPEx endpoint, adapter, credential, secure payload, or external source was accessed.

No price, return, prediction, recommendation, rank, score, or ranking mutation was introduced.

Mainline acceptance reruns the Theme/MFO regression suite, the Theme verifier, Python compilation, allowlist/privacy checks recorded by the Reviewer, and `git diff --check` before push.
