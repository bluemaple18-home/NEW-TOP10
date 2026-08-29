# S1 fresh rerun acceptance — Issue #10 production recovery

Date: 2026-08-29  
Independent review: `S1_ACCEPT`  
Decision: `S1_ACCEPTED_FOR_NON_PRODUCTION_REPRESENTATIVE_VALIDATION`  
Production decision: `NOT_PRODUCTION_READY`

## Evidence

- rerun receipt path: `.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/s1_fresh_rerun_20260829/bounded_observer_receipt.json`
- rerun receipt SHA256: `49cc62094fbb07f787a92e90cb9bb8cd22cf86ebe056dfa3af47764d4935032b`
- verdict: `BOUNDED_ACCEPTABLE`
- explanations: `["both cycles completed within bounded criteria"]`
- `fresh_s1=true`
- `supersedes_run2=false`
- `production_candidate_policy_sha=a788e7aea32f0ffd901d87c89cddbd67cc90e3f516a6984ffff9a44e80b4588e`
- `source_code_policy_identity_unchanged=true`
- `source_snapshot_unchanged=true`
- `source_policy_unchanged=true`
- `observer_unchanged=true`

## Scope

```json
{"git_operation": false, "network_send": false, "production_policy_changed": false, "production_run": false, "restart_marker_cleared": false, "validation_only": true}
```

This acceptance is for non-production representative validation only. It is not marker clear, production daily, send, launchd, commit, push, merge, or deploy authorization.

## Fresh preflight headroom

- observed free: `38021488 KiB`
- target free: `38001527 KiB`
- verdict: `PASS`

Interpretation: the rerun started with just enough headroom above the target. This supports S1 rerun execution, but does not create durable production headroom evidence.

## Cold cycle metrics

- exit code: `0`
- guard status: `OK`
- child status: `OK`
- elapsed seconds: `66.85811519622803`
- sample count: `4`
- live sample count: `2`
- peak live RSS bytes: `1815642112`
- peak RSS interpretation: approximately `1.816GB`
- peak swap growth bytes: `28311552`
- max swap growth bytes: `28311552`
- min host free ratio: `0.15726567289806337`
- project bytes delta: `344722608`
- project file count delta: `21`
- artifacts complete: `true`
- source identity unchanged: `true`
- unknown writes: `[]`
- final process group quiescent: `true`
- warning path exercised: `false`

## Warm cycle metrics

- exit code: `0`
- guard status: `OK`
- child status: `OK`
- elapsed seconds: `57.56995701789856`
- sample count: `3`
- live sample count: `1`
- peak live RSS bytes: `4063232`
- peak RSS interpretation: approximately `4MB`
- peak swap growth bytes: `446305403`
- max swap growth bytes: `446305403`
- min host free ratio: `0.15676474229279427`
- project bytes delta: `132090445`
- project file count delta: `2`
- artifacts complete: `true`
- source identity unchanged: `true`
- unknown writes: `[]`
- final process group quiescent: `true`
- warning path exercised: `false`

## Acceptance mapping

- Two-cycle validation completed: PASS
- Both cycles exit `0`: PASS
- Both guard receipts status `OK`: PASS
- Both child receipts status `OK`: PASS
- Required artifacts complete in both child receipts: PASS
- Source identity unchanged: PASS
- Unknown writes empty: PASS
- Final process group quiescent: PASS
- Scope remains validation-only: PASS

## Remaining risks

- Warm cycle ran for approximately `57.57s` and had only `1` live sample; its `4063232` byte peak RSS is a weak peak-memory signal and must not be treated as strong peak evidence.
- The warm peak RSS is only around `4MB`; this is accepted under the established S1 warm contract, but not promoted into a production peak-memory claim.
- Cold has stronger runtime evidence: `2` live samples and peak RSS approximately `1.816GB`.
- Neither cold nor warm crossed the 2GiB `SOFT_SWAP_WARNING` threshold. Therefore warning cadence live evidence is still missing and must not be claimed as verified.
- S1 acceptance does not equal production ready. Policy remains `launch_verified=false`, restart marker remains untouched, and production canary capability gate still needs separate repair.

## Decision

`S1_ACCEPT`

This accepts fresh S1 as bounded representative validation evidence under the existing S1 warm contract. It does not authorize S3 marker clear, S4 one-shot production, S5 send, or S6 launchd/control-plane recovery.

## Next step

Move the execution frontier to `SLICE-ISS10-RECOVERY-S2` formal-entry capability repair only. S3 and later remain blocked until S2 evidence and explicit Owner checkpoints exist.
