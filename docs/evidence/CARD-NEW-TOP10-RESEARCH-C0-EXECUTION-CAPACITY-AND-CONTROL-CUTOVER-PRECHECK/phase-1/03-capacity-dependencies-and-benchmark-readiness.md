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

## Benchmark readiness inventory

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
