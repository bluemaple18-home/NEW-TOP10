# C0 Phase 2 — C1 Prerequisites and Admission Blockers

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-2`
- Candidate parent: `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`
- Canonical source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0 Phase 1 fixed SHA: `d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`
- C0 Phase 1 fixed SHA: `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`
- Observed at: `2026-09-01T05:47:34Z`
- Boundary: blocker recommendation only。不得自行 admit C1/B1、不得 merge/push/deploy、不得 Issue write。

## Recommendation

`C1_ADMISSION_BLOCKED`

C0 Phase 2 has enough evidence to define the measured gaps, but not enough to admit C1. The recommended next decision is `REQUEST_BOUNDED_RESEARCH_REPAIR_OR_DESIGN_CARD_FOR_C1_PREREQS`, not implementation.

## C1 prerequisite checklist

| Prerequisite | Required evidence | Current status |
|---|---|---|
| B0 fully accepted | B0/B2 or equivalent must fix CandidateDecision → explicit admission → Canonical TrialSpec | BLOCKED |
| Canonical 720 generator/path | generate/dedupe/identity/partition/rank/unrank path for TrialSpec identities | NOT PROVEN / B1 NOT ADMITTED |
| Direct TrialSpec runner seam | runner accepts immutable TrialSpec ID/path as execution authority | MISSING |
| Queue references | queue references canonical TrialSpec identity only; no topic-only fallback for admitted execution | MISSING |
| Claim/lease | durable item claim, lease expiry, renewal, adoption, stale handling | MISSING |
| Retry/orphan | retry count/backoff/poison state bound to claim and terminal receipt; orphan does not infer unknown facts | PARTIAL CONTRACT, POLICY MISSING |
| Capacity | representative E3 benchmark with wall time, candidate/sec, CPU, peak RSS, I/O, bytes/files, cleanup | UNMEASURED |
| E2 reuse | semantic correctness and performance proof for reusable path-dependent intermediate | NOT PROVEN |
| E4 cadence | direct TrialSpec-to-forward-shadow observation path and calendar cadence | UNCHARACTERIZED |
| A6 cutover | bridge-by-bridge live activity, parity, rollback, removal gates | NOT READY |
| Prior art/dependency | explicit reject/adapt/adopt decision with license/ops review if dependency added | REJECT_EXTERNAL_RUNTIME_FOR_NOW |
| Verification environment | project `.venv` or approved uv environment available without unbounded repo writes | MISSING_IN_THIS_WORKTREE |

## Stop rules for C1

- Stop if a candidate needs production invocation, external write, scheduler change, publish path, live canary, bridge removal, or dual-write without explicit admission.
- Stop if it tries to convert topic queue, runner defaults, validation profile, or compatibility `combo_id` into canonical TrialSpec authority.
- Stop if it reports capacity from verifier pass, source inspection, historical native evidence canary, or non-representative synthetic sample.
- Stop if orphan handling invents executed facts or marks unknown lineage/dataset/result as success.

## Claim ledger

### Claim C0P2-C1-001

```yaml
claim_id: C0P2-C1-001
claim: C1 must wait for B0 fully accepted and for CandidateDecision → explicit admission → Canonical TrialSpec to be fixed by B2 or equivalent future card.
classification: GOVERNING_PHASE_GATE
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: lines 408-425
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: admitting C1 immediately after C0 Phase 2 evidence.
implication: This candidate can recommend blockers but cannot admit C1.
open_question: future B2/equivalent admission path remains unresolved.
owner: Mainline Integrator / Owner
```

### Claim C0P2-C1-002

```yaml
claim_id: C0P2-C1-002
claim: C0 Phase 1 established that direct TrialSpec runner input is absent, queue is topic-oriented rather than TrialSpec-ID-only, and claim/lease is absent at per-TrialSpec or per-queue-item granularity.
classification: PRIOR_C0_FIXED_EVIDENCE
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-1/01-execution-authority-and-runner-seam.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-1/02-queue-and-bridge-reader-writer-inventory.md
source_range_or_section: 01 lines 12-38,40-54; 02 lines 26-51,78-334
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: treating current manager/fog locks as C1 execution control.
implication: Direct seam and item claim/lease must be future implementation prerequisites.
open_question: exact C1 slice size remains to be designed.
owner: Future C1 owner
```

### Claim C0P2-C1-003

```yaml
claim_id: C0P2-C1-003
claim: B0 fixed evidence states canonical 720-spec generation/dedupe/identity/partition path is not proven, E2 is not proven, E3 is current evaluator, E4 is required but uncharacterized, and throughput remains unmeasured.
classification: PRIOR_B0_FIXED_EVIDENCE
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/03-e1-e4-initial-cost-classification.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md
source_range_or_section: 03 lines 3-25,27-141; 04 lines 17-35,153-170
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: moving to C1 with no benchmark or canonical generation path.
implication: C1 should be blocked until these B0-derived prerequisites are satisfied or explicitly scoped out by Owner.
open_question: B1/B2/equivalent future card contents remain not admitted.
owner: Mainline Integrator / future B1-B2 owners
```

### Claim C0P2-C1-004

```yaml
claim_id: C0P2-C1-004
claim: A6 bridge metadata and tests exist, but consumer parity, live activity, rollback drill, and safe removal evidence are not proven in this candidate.
classification: A6_CUTOVER_BLOCKER
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/a6_closure.py; tests/test_research_spine_a6_bridge_removals.py; docs/evidence/CARD-NEW-TOP10-RESEARCH-A6-DEPRECATION-REBUILD-AND-BRIDGE-REMOVAL-GATES/closure_receipt.json
source_range_or_section: a6_closure.py lines 98-287; tests lines 1-64; closure_receipt.json lines 14-72
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: bridge removal or cutover from metadata-only evidence.
implication: Bridge cutover/removal must be a later gated step, not part of C1 admission by default.
open_question: exact live consumers and semantic parity comparator remain missing.
owner: Future cutover owner / A6 reviewer
```

### Claim C0P2-C1-005

```yaml
claim_id: C0P2-C1-005
claim: The recommended C1 verdict is BLOCKED because all major implementation preconditions remain missing or unmeasured, even though Phase 2 evidence clarified the gap list.
classification: WORKER_RECOMMENDATION
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba; d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98
source_path_or_official_url: this phase-2 evidence set; docs/tasks/2026-09-01_DISPATCH-NEW-TOP10-C0-PHASE-2-CAPACITY-AND-CUTOVER-DESIGN.md
source_range_or_section: phase-2 files 05-10; dispatch card lines 1-20
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: admitting C1 from evidence-only design.
implication: Mainline should request narrower C1 prerequisite cards or bounded repair/review rather than implementation admission.
open_question: independent reviewer GO/NO-GO on this candidate.
owner: C0 Phase 2 worker / Mainline Integrator
```
