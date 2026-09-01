# C0 Phase 1 — BC Checkpoint Input

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-1`
- NEW-TOP10 source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- AI Core source SHA: `21801303adff285268f7646df94dc53da31a835f`
- Observed at: `2026-09-01T03:30:48Z`
- Boundary: checkpoint input only. This file does not approve BC-CP1, Phase 2, C1, implementation, benchmark, canary, cutover, rollback, bridge removal, queue mutation, or runtime mutation.

## BC-CP1 candidate input

| Question | C0 Phase 1 input |
|---|---|
| Can runner directly accept canonical TrialSpec? | No. TrialSpec/receipt contracts exist, but execution input still comes from topic/scenario/profile CLI and adapter-generated specs. |
| Smallest exact runner gap | Add a direct immutable TrialSpec input seam; validate TrialSpec/dataset/ranking authority; map only existing executable fields into replay; preserve requested-vs-executed terminal receipt; do not change backtest math. |
| Queue authority | Current queue is topic-oriented manager state and projection, not canonical TrialSpec-ID-only admission. |
| Claim/lease authority | Missing at per-TrialSpec / per-queue-item level. Existing locks are process/owner mutual exclusion only. |
| Retry authority | Present as topic rerun and fog-worker batch retry circuit; missing as canonical claim retry. |
| A6 bridge state | Source-declared active/historical/recovery-only inventory exists with tests; several active surfaces remain live-activity-unverified by Phase 1 source-only evidence. |
| Capacity | Must wait for B0 matrix size and E1–E4 facts. |
| Benchmark readiness | Candidate safe checks can be listed, but no benchmark was run and no operational command was invoked. |
| Stop-rule result | No authority contradiction, identity-boundary impossibility, terminal-boundary impossibility, runtime-mutation requirement, external side effect, or operational interference was encountered. |

## Recommended BC checkpoint decision framing

- `BC-CP1 input status`: `READY_FOR_REVIEW` after repair coverage of Issue #14 minimum source surfaces (`receipt_store.py`, `observation_ingest.py`, `batch_owner.py`, and `run_controlled_grid_drain_host_runner.py`)
- `Phase 2 admission`: `NOT_ADMITTED_BY_THIS_EVIDENCE`
- `C1 admission`: `NOT_ADMITTED_BY_THIS_EVIDENCE`
- `Cutover readiness`: `NO`
- `Direct TrialSpec execution readiness`: `NO`
- `Capacity readiness`: `WAIT_FOR_B0`
- `Bridge removal readiness`: `NO`

## Minimum follow-up candidates, if BC admits later work

These are candidate inputs only, not approvals:

1. Direct TrialSpec seam spike limited to contract validation and parameter translation, with no backtest math change.
2. Queue-reference gap card to convert topic-oriented queue admission into canonical TrialSpec identity references.
3. Claim/lease/retry gap card after queue-reference authority is admitted.
4. Capacity benchmark design only after B0 matrix size and E1–E4 facts are available.
5. Bridge runtime-activity verification plan that separates source-declared active bridges from actual live invocation evidence.

## Claim ledger

### Claim C0-P1-BC-001

- claim_id: `C0-P1-BC-001`
- claim: `The BC checkpoint can use this Phase 1 evidence as read-only input, but cannot infer Phase 2 or C1 admission from it.`
- classification: `CONTRACT`
- source_repo: `GitHub Issue; NEW-TOP10`
- source_sha_or_version: `#14 updated_at=2026-09-01T02:26:05Z; 35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `https://github.com/bluemaple18-home/NEW-TOP10/issues/14; docs/RESEARCH_SPINE_BACKLOG.md`
- source_range_or_section: `Issue #14 Acceptance / Not admitted; docs/RESEARCH_SPINE_BACKLOG.md L325-L397`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `BC-CP1 may review evidence and decide later gates, but this worker must not grant those gates.`
- open_question: `BC-CP1 decision itself remains outside this worker.`
- owner: `Issue #14 / canonical backlog`

### Claim C0-P1-BC-002

- claim_id: `C0-P1-BC-002`
- claim: `Card A canonical spine expects canonical execution specs, authorization/eligibility evidence, execution intent, immutable execution receipt, observation, ledger, and projections; raw/canonical truth excludes rebuildable projections and legacy bridge state.`
- classification: `CONTRACT`
- source_repo: `GitHub Issue`
- source_sha_or_version: `#1 updated_at=2026-08-31T17:55:56Z`
- source_path_or_official_url: `https://github.com/bluemaple18-home/NEW-TOP10/issues/1`
- source_range_or_section: `Canonical spine / Truth and derived state / Hard contracts / Card C end state`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `BC should treat direct TrialSpec execution and queue identity references as canonical-spine alignment, while keeping projections/bridges rebuildable or temporary.`
- open_question: `None for Phase 1; implementation sequencing remains later.`
- owner: `Card A contract`

### Claim C0-P1-BC-003

- claim_id: `C0-P1-BC-003`
- claim: `Card A end state says the runner should accept canonical immutable execution spec directly and the queue should reference spec identity only, removing topic-only interpretation, permanent adapters, dual paths, and legacy history authority.`
- classification: `CONTRACT`
- source_repo: `GitHub Issue`
- source_sha_or_version: `#1 updated_at=2026-08-31T17:55:56Z`
- source_path_or_official_url: `https://github.com/bluemaple18-home/NEW-TOP10/issues/1`
- source_range_or_section: `Card C end state`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `Current runner and queue source inventory in C0-P1-EXE-004/C0-P1-QBI-002`
- implication: `The direct TrialSpec and queue-reference gaps are real alignment gaps, not optional polish.`
- open_question: `Phase 2 must be separately admitted before closing those gaps.`
- owner: `Card A contract`

### Claim C0-P1-BC-004

- claim_id: `C0-P1-BC-004`
- claim: `A6 requires every compatibility bridge to have owner, removal condition, removal test, and target removal stage, and states legacy run history should no longer be required for new-run truth.`
- classification: `CONTRACT`
- source_repo: `GitHub Issue`
- source_sha_or_version: `#8 updated_at=2026-08-31T17:34:03Z`
- source_path_or_official_url: `https://github.com/bluemaple18-home/NEW-TOP10/issues/8`
- source_range_or_section: `Goal / Scope / Acceptance`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `BC should treat bridge inventory as temporary-bridge control evidence, not as permission to remove or cut over bridges in Phase 1.`
- open_question: `Runtime activity and removal readiness remain future evidence questions.`
- owner: `A6 contract`

### Claim C0-P1-BC-005

- claim_id: `C0-P1-BC-005`
- claim: `Stop-rule review found no source-level authority contradiction and no need for runtime mutation or external side effect to complete Phase 1; TrialSpec identity and terminal receipt boundaries were establishable from source contracts.`
- classification: `WORKER_FINDING`
- source_repo: `NEW-TOP10; ai-core`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070; 21801303adff285268f7646df94dc53da31a835f`
- source_path_or_official_url: `app/research/contracts.py; app/research/run_receipts.py; app/research/receipt_store.py; app/research/observation_ingest.py; app/research/batch_owner.py; scripts/run_controlled_grid_drain_host_runner.py; docs/ai-core-backlog.md; rules/24-storage-capacity-safety.md; rules/25-production-canary-readiness.md`
- source_range_or_section: `app/research/contracts.py L281-L321, L638-L934; app/research/run_receipts.py L278-L424, L520-L953; app/research/receipt_store.py L16-L18, L34-L82, L84-L90; app/research/observation_ingest.py L1-L43, L1060-L1234, L1276-L1395; app/research/batch_owner.py L22-L34, L167-L239, L385-L456; scripts/run_controlled_grid_drain_host_runner.py L1-L6, L81-L119, L191-L235, L244-L293; docs/ai-core-backlog.md L25-L29, L144-L151; rules/24-storage-capacity-safety.md L1-L18; rules/25-production-canary-readiness.md L1-L41`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `MEDIUM_HIGH`
- conflict_with: `None observed in allowed source set`
- implication: `Phase 1 can be handed to BC as evidence input rather than stopped as blocked.`
- open_question: `Runtime live-state claims remain unverified because production/runtime invocation was forbidden.`
- owner: `C0 Phase 1 worker`

### Claim C0-P1-BC-006

- claim_id: `C0-P1-BC-006`
- claim: `Repair coverage now includes Issue #14 minimum-source boundary evidence for immutable store identity, terminal receipt/ledger projection, batch-owner authority, and controlled-grid operational linkage boundary, while preserving READY_FOR_REVIEW only as checkpoint input and not as Phase 2/C1 admission.`
- classification: `REPAIR_COVERAGE`
- source_repo: `NEW-TOP10; GitHub Issue`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070; #14 updated_at=2026-09-01T02:26:05Z`
- source_path_or_official_url: `app/research/receipt_store.py; app/research/observation_ingest.py; app/research/batch_owner.py; scripts/run_controlled_grid_drain_host_runner.py; https://github.com/bluemaple18-home/NEW-TOP10/issues/14`
- source_range_or_section: `app/research/receipt_store.py L16-L18, L34-L82, L84-L90, L93-L153; app/research/observation_ingest.py L1-L43, L397-L419, L1060-L1234, L1276-L1395; app/research/batch_owner.py L22-L34, L66-L87, L143-L164, L167-L239, L385-L456; scripts/run_controlled_grid_drain_host_runner.py L1-L6, L19-L22, L81-L119, L122-L178, L191-L235, L238-L293; Issue #14 Minimum inspect paths / Acceptance`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `Previous candidate lacked source-backed claims for these minimum inspect surfaces`
- implication: `BC-CP1 can review the four evidence files with the required minimum-source coverage included.`
- open_question: `This does not answer B0 matrix sizing, live bridge invocation, benchmark results, or Phase 2/C1 approval.`
- owner: `C0 Phase 1 repair worker`
