---
card_id: REVIEW-TSKG-OSS-ADR-01
status: REVIEW_GO
reviewed_on: 2026-07-20
reviewer_thread_id: 019f7e98-826f-71a1-86ae-5ee6360b0f4d
reviewed_candidate: dfade37ba0c030d764f1f3b7181cead17a6b3756
reviewed_parent: ea5655efc5bf171f3584073ac04046699d0cc56e
review_card_commit: d0a4a8c319ad696e73ebc88c2321113710fb3ade
verdict: GO
---

# REVIEW-TSKG-OSS-ADR-01 independent review

## Verdict

`GO`

ADR candidate `dfade37ba0c030d764f1f3b7181cead17a6b3756` can be used as input for a future `TSKG-MFO-RM-01` card. This review does not approve any source, ingestion, live connector, API, UI, Top10 ranking mutation, merge, push, or implementation authorization.

## Preflight and lineage

- Review worktree: `PASS`；執行於平台配置的 independent detached worktree，非 main cwd。
- HEAD / review card: `d0a4a8c319ad696e73ebc88c2321113710fb3ade`。
- Review card parent / reviewed candidate: `dfade37ba0c030d764f1f3b7181cead17a6b3756`。
- Reviewed candidate parent: `ea5655efc5bf171f3584073ac04046699d0cc56e`。
- Candidate lineage: `ea5655efc5bf171f3584073ac04046699d0cc56e` is ancestor of `dfade37ba0c030d764f1f3b7181cead17a6b3756`。
- Review lineage: `dfade37ba0c030d764f1f3b7181cead17a6b3756` is ancestor of review card `d0a4a8c319ad696e73ebc88c2321113710fb3ade`。
- Clean pre-review state: worktree and index clean；`unrelated_dirty_paths=[]`。
- Index lock: absent。

## Findings

No P0-P2 findings.

- [P3] ADR verification evidence does not name the already integrated MFO-01 acceptance as a supporting artifact for the `SecurityFlowObservation` boundary.
  - Evidence: ADR line 61 cites the Tide handoff for `SecurityFlowObservation` reuse, while current repo-local MFO-01 documents show the raw synthetic contract is integrated, independently reviewed, and accepted. This does not block the ADR because the review card required checking the existing contract and the local contract supports the ADR boundary, but future acceptance notes should cite MFO-01 explicitly to reduce evidence-chasing.

## Decision Axis

`GO`

- Exactly one primary decision is present: `ADAPTER_FIRST_INTERNAL_PATTERNS`.
- The four required options are substantively compared: adapter-first selected, third-party dependency rejected, OSS stack adoption rejected, and wait-for-source-approval rejected as primary.
- The ADR does not smuggle in a second primary: external OSS remains reference-only or rejected, and live source approval remains blocked.
- Rejected alternatives are supported by fixed inputs: FinMind service/data rights are unresolved, TWSEMCPServer directness is not official endpoint authorization, and full waiting would block an offline projection slice that can be verified synthetically.

## Adoption Axis

`GO`

- Adoption matrix has 16 asset rows and exactly one allowed status per row.
- Repo FinMind fetcher/integrator/FetchStage are not treated as production-approved source ingestion.
- Direct T86 parser/status/offline verifier patterns are split correctly from direct endpoint approval: parser/status/verifier shapes can be reused internally, but direct source use stays blocked.
- TWSEMCPServer, FinMind service/code, twstock, twstocks-crawler, tsec, tsrtc, and the T86 issue discussion keep code license, data rights, endpoint authorization, and production approval separated.
- `SecurityFlowObservation` is limited to source-neutral synthetic/validated raw observation reuse; `ThemeFlowObservation` remains blocked on membership/source/aggregation edges.

## Boundary Axis

`GO`

- The responsibility chain is layered without jumping from source adapter to read model:

```text
source adapter
  -> raw snapshot / provenance
  -> source normalizer
  -> SecurityFlowObservation contract
  -> graph projection boundary
  -> Top10 / LLM read model
```

- `TSKG-MFO-RM-01` is the only named next implementation card and was not found as an existing repo file.
- The next-card shape is offline-verifiable: synthetic fixture, pure projection, contract/unit tests, offline verifier, external call count 0, and no runtime caller changes.
- It does not duplicate MFO-01: MFO-01 owns raw `SecurityFlowObservation` validation; the ADR's next frontier only consumes validated rows and produces a non-strategy read model.
- Top10 / LLM output excludes score, weight, signal, prediction, recommendation, expected return, buy/sell semantics, and ranking mutation.
- Source approval, live connector, rate/retention, late correction, Theme aggregation, graph diffusion, and UI radar remain deferred forks.

## Evidence Axis

`GO_WITH_P3`

- Candidate changed files are exactly the ADR card allowlist:
  - `docs/tasks/2026-07-20_TSKG-OSS-ADR-01_reference_adoption_decision.md`
  - `docs/adr/ADR-TSKG-OSS-01_reference_adoption.md`
  - `docs/evidence/TSKG-OSS-ADR-01/verification.md`
- Candidate `git diff --check` passes.
- ADR status remains `PROPOSED_CANDIDATE` and does not claim accepted, integrated, source-approved, or production-active status.
- Verification records 12 claim IDs, 16 matrix rows, one primary decision, one next card, and allowlist gates.
- Shared-file host-neutral scan found no actual local absolute path or file URI. The only matches are allowed placeholders such as `<repo-gitdir>` and `<local-only-worktree>`.
- P3 caveat: the ADR/verification claim ledger can be made clearer by explicitly referencing current MFO-01 acceptance for the already integrated `SecurityFlowObservation` contract, rather than relying on the Tide handoff plus review-time local cross-check.

## Commands and exit codes

| Command | Exit | Purpose |
|---|---:|---|
| `git rev-parse HEAD` | 0 | Confirm review card HEAD |
| `git status --porcelain=v1` | 0 | Confirm clean worktree and index |
| `test -e .git/index.lock` | 1 | Confirm no index lock exists |
| `git rev-parse d0a4a8c319ad696e73ebc88c2321113710fb3ade^` | 0 | Confirm review card parent is candidate |
| `git rev-parse dfade37ba0c030d764f1f3b7181cead17a6b3756^` | 0 | Confirm candidate parent |
| `git merge-base --is-ancestor ea5655efc5bf171f3584073ac04046699d0cc56e dfade37ba0c030d764f1f3b7181cead17a6b3756` | 0 | Confirm parent-to-candidate lineage |
| `git merge-base --is-ancestor dfade37ba0c030d764f1f3b7181cead17a6b3756 d0a4a8c319ad696e73ebc88c2321113710fb3ade` | 0 | Confirm candidate-to-review-card lineage |
| `git diff --name-only ea5655efc5bf171f3584073ac04046699d0cc56e dfade37ba0c030d764f1f3b7181cead17a6b3756` | 0 | Confirm candidate exact changed files |
| `git diff --check ea5655efc5bf171f3584073ac04046699d0cc56e dfade37ba0c030d764f1f3b7181cead17a6b3756` | 0 | Candidate whitespace gate |
| `find docs app tests data -name '*TSKG-MFO-RM-01*' -o -name '*MFO-RM*'` | 0 | Confirm next implementation card file absent |
| `rg -n '^\\| .+ \\| \`(REUSE_INTERNAL\|REFERENCE_ONLY\|DO_NOT_ADOPT\|BLOCKED_PENDING_SOURCE_APPROVAL)\` \\|' docs/adr/ADR-TSKG-OSS-01_reference_adoption.md` | 0 | Confirm 16 adoption matrix rows |
| `rg -n "Primary decision:\|PRIMARY / SELECTED\|Next implementation card:" docs/adr/ADR-TSKG-OSS-01_reference_adoption.md` | 0 | Confirm single primary marker and next card marker |
| `rg -n "<host-path-scan>" <shared-review-files>` | 1 | No actual host path or file URI match |
| `sed -n '1,220p' <fixed-input-doc>` | 0 | Read fixed inputs and supporting local contract docs |
| `nl -ba <candidate-or-contract-doc>` | 0 | Capture line references for review evidence |

Two reviewer command mistakes were excluded from candidate gates: one `find` invocation included a nonexistent top-level `tasks` path, and one matrix `rg` pattern used shell backticks incorrectly. Both were rerun with corrected local commands and did not indicate candidate defects.

## Remaining risks

- This review is architecture/document-only and did not execute implementation tests, financial endpoints, external research, dependency installs, or live source probes by design.
- The GO only makes the ADR suitable as input for drafting a future card; `TSKG-MFO-RM-01` still requires its own task card, implementation review, offline verifier, and mainline acceptance before any integration.
- Python runtime caveats from MFO-01 remain unchanged; this ADR review does not expand version-matrix acceptance.
- Source/compliance owner approval is still required for MOPS/TWSE/FinMind ingestion, retention, redistribution, and downstream Top10/LLM/API use.
