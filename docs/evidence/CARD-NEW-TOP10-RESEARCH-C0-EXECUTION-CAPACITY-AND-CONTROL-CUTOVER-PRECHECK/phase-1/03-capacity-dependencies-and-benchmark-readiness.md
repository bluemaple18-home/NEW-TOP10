# C0 Phase 1 — Capacity Dependencies and Benchmark Readiness

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-1`
- NEW-TOP10 source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- AI Core source SHA: `21801303adff285268f7646df94dc53da31a835f`
- Observed at: `2026-09-01T03:30:48Z`
- Boundary: characterize dependencies and benchmark readiness only. This file does not run benchmarks, mutate runtime state, set capacity, size worker pools, admit canary, or define cutover/rollback.

## Capacity conclusion

Capacity cannot be finalized in C0 Phase 1. The current source can identify runner surfaces, parameter catalog dimensions, existing quota wiring, and safe verification candidates. The actual capacity envelope must wait for B0 matrix size and E1–E4 facts: number of admitted CandidateDecisions, TrialSpecs per decision, executable-vs-coverage splits, data/artifact availability, queue depth, and representative benchmark sample selection.

## What must wait for B0

| Capacity question | Why it waits |
|---|---|
| Full daily TrialSpec count | Requires B0 candidate matrix size and canonical TrialSpec expansion rules. |
| E1–E4 execution class mix | Requires B0 classification of cheap deterministic checks, existing-artifact reuse, expensive replay, and blocked/missing-data work. |
| Benchmark sample | Must be selected from admitted B0 cases, not from C0-inferred topic order or runner defaults. |
| Daily quota or worker concurrency | Requires benchmark results and operational envelope; Phase 1 may not mutate scheduler/runner. |
| Claim/lease/retry capacity impact | Claim/lease/retry design is explicitly not admitted in Phase 1. |
| Bridge cutover/removal capacity impact | Bridge switch/removal is explicitly not admitted in Phase 1. |

## Bounded capacity benchmark readiness inventory

Current Phase 1 evidence is not a benchmark plan and did not run any benchmark. A future admitted benchmark must provide all of the following before any timing/capacity number can be trusted:

| Requirement | Phase 1 status | Notes |
|---|---|---|
| Fixed immutable input candidates | `PARTIAL` | Existing docs/evidence intermediates are inspectable; current isolated worktree lacks live `artifacts/autonomous_research/research_spine`, `data/research/research_ledger.duckdb`, and canonical queue artifacts. |
| B0 representative sample | `UNAVAILABLE` | Must come from B0 matrix size and E1–E4 facts, not queue order, topic order, or runner defaults. |
| Temporary output boundary | `REQUIRED_NOT_SELECTED` | Must be a predeclared isolated output root with no production, scheduler, queue, model, ranking, publish, or bridge-removal writes. |
| Measurement fields | `DEFINED_FOR_FUTURE_USE` | Required fields: input candidate ID/path/hash, B0 class, TrialSpec count, run/intent/receipt IDs if produced, terminal status, identity match status, wall time, exit status, bytes/files before-after, CAS/ledger deltas, protected surface parity, command argv hash, failure reason. |
| Reusable intermediate candidates | `PARTIAL` | Native replay bundle and adaptive shadow queue evidence can inform sample design, but cannot replace B0 capacity facts. |

## Fixed immutable / reusable input candidates

| Candidate | Path | Status | Reusable intermediate? | Capacity use |
|---|---|---|---|---|
| Native evidence replay bundle manifest | `docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/manifest.json` | `PROVEN_PRESENT` | `PROVEN` | Has two isolated cycles, capacity PASS, parity unchanged; usable as historical bounded-evidence reference only. |
| Native evidence replay bundle | `docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json` | `PROVEN_PRESENT` | `PROVEN` | Immutable-ish committed bundle input for adaptive projection verification; not a B0 representative matrix. |
| Adaptive shadow queue projection / receipt | `docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1/adaptive_shadow_queue_projection.json`; `adaptive_shadow_queue_receipt.json` | `PROVEN_PRESENT` | `PROVEN` | Projection readiness input; not canonical execution capacity. |
| Shadow research plan proposal | `docs/evidence/CARD-NEW-TOP10-SHADOW-RESEARCH-PLAN-PROPOSAL-V1/shadow_research_plan_proposal.json` | `PROVEN_PRESENT` | `PROVEN` | Proposal intermediate; not runner benchmark input. |
| Isolated shadow plan replay result | `docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/result.json`; `post_execution_verification.json` | `PROVEN_PRESENT_BUT_NO_GO` | `NOT_PROVEN_FOR_CAPACITY` | Result status is `NO-GO_EVIDENCE_UNAVAILABLE`; cannot certify capacity readiness even if local capacity subfield is present. |
| Current isolated worktree canonical queue / research spine / ledger | `artifacts/autonomous_research/next_action_queue.json`; `artifacts/autonomous_research/research_spine`; `data/research/research_ledger.duckdb` | `UNAVAILABLE_IN_ISOLATED_WORKTREE` | `NOT_PROVEN` | Cannot be used as fixed benchmark input without creating or importing immutable inputs, which Phase 1 did not do. |
| B0 CandidateDecision / E1–E4 matrix | B0 output | `UNAVAILABLE` | `NOT_PROVEN` | Required before representative benchmark sample selection. |

## Bounded representative sample requirements

Any future admitted benchmark sample must be:

1. Fixed by B0 output identity, not selected by C0 from topic/queue/ranking order.
2. Stratified across E1–E4 classes if B0 defines them.
3. Bounded by explicit maximum TrialSpec count, dataset/ranking artifact identity, and command count.
4. Run only in an isolated output root with protected-surface parity checks before/after.
5. Report failure and duplicate behavior without retrying through operational workers.

## Temporary output boundary requirements

The output boundary for any future admitted benchmark must explicitly exclude:

- `artifacts/autonomous_research/next_action_queue.json`
- scheduler plist or launchd state
- production ranking/model/signal files
- legacy bridge removal/switch paths
- publish, Discord, external service, or production handoff paths

The output boundary must include:

- benchmark output root identity and hash
- command argv hash
- input corpus / TrialSpec IDs
- receipt IDs if terminal receipts are created
- protected-surface before/after hashes
- bytes/file-count deltas
- cleanup status

## Validation commands are not benchmark commands

Safe bounded commands for a future admitted benchmark plan should be restricted to isolated verification or small characterization commands that do not invoke production scheduler paths, external side effects, dual execution, Discord/publish flows, or cutover. Candidate examples to validate in that future plan:

- `git diff --check`
- `.venv/bin/python scripts/verify_autonomous_research.py`
- `.venv/bin/python scripts/verify_backtest_strategy_matrix.py`
- `.venv/bin/python scripts/verify_research_spine_batch.py`
- `.venv/bin/python scripts/verify_daily_research_quota.py`
- `.venv/bin/python scripts/verify_adaptive_shadow_queue.py`
- `.venv/bin/pytest -q tests/test_research_spine_contracts.py tests/test_research_receipt_store.py tests/test_research_batch_owner.py tests/test_autonomous_research_receipts.py tests/test_research_spine_a6_bridge_removals.py`

Forbidden for this Phase 1 worker and for any future benchmark unless separately admitted:

- `bash scripts/run_fog_research_worker.sh`
- `bash scripts/run_daily_research_quota.sh`
- `python scripts/run_top10_fog_map_handoff.py` in a mode that runs quota/refresh side effects
- `python scripts/run_autonomous_research.py --execute`
- `python scripts/run_backtest_strategy_matrix.py` against production artifacts or full matrix output
- Any launchd/plist scheduling, production invocation, external publishing/Discord/send path, dual execution, cutover, canary, rollback, or bridge removal command

## Claim ledger

### Claim C0-P1-CAP-001

- claim_id: `C0-P1-CAP-001`
- claim: `Issue #14 and the canonical backlog explicitly prohibit C0 Phase 1 from finalizing capacity, claim/lease/retry, canary, rollback, bridge removal, or C1 before B0 matrix size and E1–E4 facts exist.`
- classification: `CONTRACT`
- source_repo: `GitHub Issue; NEW-TOP10`
- source_sha_or_version: `#14 updated_at=2026-09-01T02:26:05Z; 35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `https://github.com/bluemaple18-home/NEW-TOP10/issues/14; docs/RESEARCH_SPINE_BACKLOG.md`
- source_range_or_section: `Issue #14 Phase 1/Not admitted/C1 dependencies; docs/RESEARCH_SPINE_BACKLOG.md L87-L117, L325-L397, L560-L666`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `This file can list dependencies and readiness only; no capacity number is authorized.`
- open_question: `B0 matrix size and E1–E4 facts remain required inputs.`
- owner: `Issue #14 / canonical backlog`

### Claim C0-P1-CAP-002

- claim_id: `C0-P1-CAP-002`
- claim: `The parameter catalog declares executable dimensions for horizon, stop loss, take profit, and max group exposure, while regime gate, risk guard, and entry filter are coverage-only / contract-dependent fields.`
- classification: `OBSERVED_CONFIG`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `config/research_parameter_catalog.json`
- source_range_or_section: `L1-L5, L6-L125, L127-L188`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `A future benchmark can bound executable replay dimensions, but coverage-only fields must not be silently promoted to executable runner knobs.`
- open_question: `B0 must specify which admitted TrialSpecs use which executable dimension combinations.`
- owner: `Research parameter catalog`

### Claim C0-P1-CAP-003

- claim_id: `C0-P1-CAP-003`
- claim: `The autonomous runner can summarize legal parameter combinations and statistical-family size, while the matrix runner expands validation-profile combinations into scenarios before replay.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_autonomous_research.py; scripts/run_backtest_strategy_matrix.py`
- source_range_or_section: `scripts/run_autonomous_research.py L543-L608; scripts/run_backtest_strategy_matrix.py L580-L623`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `The source has characterization hooks, but current scenario expansion is not the same as B0-admitted canonical TrialSpec matrix size.`
- open_question: `B0 must provide the admitted candidate/spec population before capacity is sized.`
- owner: `Autonomous research manager / matrix runner`

### Claim C0-P1-CAP-004

- claim_id: `C0-P1-CAP-004`
- claim: `Daily quota entrypoint is an operational script that runs quota execution and writes/validates outputs; executing it would exceed Phase 1 inventory scope.`
- classification: `BOUNDARY`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_daily_research_quota.sh`
- source_range_or_section: `L46-L63, L73-L103, L137-L180, L183-L249`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Phase 1 may inspect but must not invoke daily quota as a benchmark.`
- open_question: `Future benchmark admission must isolate output paths and prove no external or production side effect.`
- owner: `Daily research quota entrypoint`

### Claim C0-P1-CAP-005

- claim_id: `C0-P1-CAP-005`
- claim: `AI Core storage-capacity and production-canary gates require measured growth/safety evidence and capability receipts; lack of such evidence is a NO-GO for recurring/deploy/canary claims.`
- classification: `AUTHORITY_CHECK`
- source_repo: `ai-core`
- source_sha_or_version: `21801303adff285268f7646df94dc53da31a835f`
- source_path_or_official_url: `rules/24-storage-capacity-safety.md; rules/25-production-canary-readiness.md`
- source_range_or_section: `rules/24-storage-capacity-safety.md L1-L18, L47-L52; rules/25-production-canary-readiness.md L1-L41`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `C0 Phase 1 cannot certify production canary, recurring capacity, deployment readiness, or rollback readiness.`
- open_question: `Future admitted work must collect measured evidence under those gates.`
- owner: `AI Core safety rules`

### Claim C0-P1-CAP-006

- claim_id: `C0-P1-CAP-006`
- claim: `CodeGraph was not initialized for the isolated worktree, so source inspection fell back to bounded read-only repository search and targeted file ranges.`
- classification: `VERIFICATION_CONTEXT`
- source_repo: `Local tool context`
- source_sha_or_version: `CodeGraph status error observed on 2026-09-01T03:30:48Z`
- source_path_or_official_url: `<isolated-worktree>`
- source_range_or_section: `codegraph_status/codegraph_context/codegraph_files returned: CodeGraph not initialized in project`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `AGENTS.md CodeGraph-first preference`
- implication: `The worker satisfied CodeGraph-first by attempting it, then used bounded rg/read because initializing the index would create non-evidence artifacts.`
- open_question: `None for Phase 1; a future author may initialize CodeGraph outside an evidence-only write boundary if authorized.`
- owner: `C0 Phase 1 worker`

### Claim C0-P1-CAP-007

- claim_id: `C0-P1-CAP-007`
- claim: `Native evidence replay bundle source uses a temporary root, runs two isolated development cycles, checks per-cycle capacity limits, verifies bundle determinism twice, checks protected-surface parity before/after cycles and cleanup, removes the isolated root, and writes a manifest with capacity observed_cycles and parity status.`
- classification: `BENCHMARK_READINESS_SOURCE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/native_evidence_replay_bundle.py`
- source_range_or_section: `L34-L46, L77-L83, L188-L330, L333-L429`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `This is a reusable intermediate pattern for isolated measurement fields, but Phase 1 did not run it and it does not replace B0 representative sample selection.`
- open_question: `Whether this pattern is admitted for C0/C capacity benchmark remains a future checkpoint decision.`
- owner: `Native evidence replay bundle`

### Claim C0-P1-CAP-008

- claim_id: `C0-P1-CAP-008`
- claim: `Committed native evidence replay manifest is present and reports PASS with two observed cycles and protected-surface parity unchanged, while adaptive shadow queue projection/receipt and shadow research proposal artifacts are present as projection/proposal intermediates.`
- classification: `IMMUTABLE_INPUT_CANDIDATE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/manifest.json; docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json; docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1/adaptive_shadow_queue_projection.json; docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1/adaptive_shadow_queue_receipt.json; docs/evidence/CARD-NEW-TOP10-SHADOW-RESEARCH-PLAN-PROPOSAL-V1/shadow_research_plan_proposal.json`
- source_range_or_section: `Each JSON artifact L1`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `These artifacts are PROVEN_PRESENT reusable intermediates for readiness discussion, but not proof of C0 capacity or B0 matrix size.`
- open_question: `B0 must still provide representative CandidateDecision / TrialSpec sample identities.`
- owner: `Committed evidence artifacts`

### Claim C0-P1-CAP-009

- claim_id: `C0-P1-CAP-009`
- claim: `Isolated shadow plan replay artifacts are present, but result status is NO-GO_EVIDENCE_UNAVAILABLE; therefore they are NOT_PROVEN_FOR_CAPACITY even though a local capacity subfield and protected-surface verification artifact exist.`
- classification: `IMMUTABLE_INPUT_CANDIDATE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/result.json; docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/post_execution_verification.json`
- source_range_or_section: `Each JSON artifact L1`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `BC-CP1 should not treat this artifact set as benchmark readiness PASS.`
- open_question: `Future benchmark sample must be selected from B0 and admitted separately.`
- owner: `Committed evidence artifacts`

### Claim C0-P1-CAP-010

- claim_id: `C0-P1-CAP-010`
- claim: `In the isolated Phase 1 worktree, canonical live queue, research spine corpus, and research ledger paths were absent during read-only filesystem inspection, so current production-like immutable inputs were unavailable to this worker.`
- classification: `LOCAL_INPUT_AVAILABILITY`
- source_repo: `Local filesystem inspection`
- source_sha_or_version: `observed_at=2026-09-01T03:30:48Z on NEW-TOP10 base 35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `artifacts/autonomous_research/next_action_queue.json; artifacts/autonomous_research/research_spine; data/research/research_ledger.duckdb`
- source_range_or_section: `read-only existence check returned ABSENT for all three paths`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Phase 1 cannot nominate current live corpus/ledger/queue as fixed benchmark inputs without importing or creating artifacts, which was outside scope.`
- open_question: `B0 or a later admitted benchmark card must provide immutable input identities.`
- owner: `C0 Phase 1 worker`

### Claim C0-P1-CAP-011

- claim_id: `C0-P1-CAP-011`
- claim: `Validation/verifier commands listed in this file are bounded verification candidates only; they are not a capacity benchmark plan because they do not define B0 sample identity, temporary output boundary, measurement fields, or protected-surface before/after parity requirements by themselves.`
- classification: `BENCHMARK_BOUNDARY`
- source_repo: `NEW-TOP10; GitHub Issue`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070; #14 updated_at=2026-09-01T02:26:05Z`
- source_path_or_official_url: `scripts/verify_autonomous_research.py; scripts/verify_backtest_strategy_matrix.py; scripts/verify_research_spine_batch.py; scripts/verify_daily_research_quota.py; scripts/verify_adaptive_shadow_queue.py; https://github.com/bluemaple18-home/NEW-TOP10/issues/14`
- source_range_or_section: `scripts/verify_autonomous_research.py L198-L330; scripts/verify_adaptive_shadow_queue.py L36-L188; Issue #14 Benchmark readiness / Non-goals`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `MEDIUM_HIGH`
- conflict_with: `Previous candidate wording could be read as treating verifier list as a benchmark plan`
- implication: `BC-CP1 should require separate benchmark admission and B0 sample facts before any capacity number is accepted.`
- open_question: `Exact benchmark command set remains future work.`
- owner: `C0 Phase 1 worker`
