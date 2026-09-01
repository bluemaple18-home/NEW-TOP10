# C0 Phase 1 — Execution Authority and Runner Seam

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-1`
- NEW-TOP10 source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- AI Core source SHA: `21801303adff285268f7646df94dc53da31a835f`
- Observed at: `2026-09-01T03:30:48Z`
- Boundary: read-only inventory and seam discovery only. This file does not admit Phase 2, C1, cutover, capacity finalization, bridge removal, canary, dual-write, claim/lease/retry design, or runtime mutation.

## Direct answer

The current runner cannot directly accept a canonical `TrialSpec` as its execution input. The existing path can create immutable trial specs, intents, attempts, and terminal receipts around a run, but the execution runner is still driven by topic/scenario/profile CLI inputs and runner defaults. The minimal exact gap is a direct TrialSpec consumption seam: load and validate immutable TrialSpec identity, bind dataset/ranking authority, translate only the existing executable fields into the current replay call, and preserve requested-vs-executed receipt comparison without changing backtest math.

## Runner seam inventory

| Surface | Current behavior | C0 Phase 1 conclusion |
|---|---|---|
| Contract validator | `validate_trial_spec` requires schema `research-trial-spec.v1`, `trial_spec_id`, canonical parameter set, research/dataset/ranking/execution authority fields, and content-hash identity. | Canonical TrialSpec identity exists as a contract. |
| Matrix runner input | `run_backtest_strategy_matrix.py` parses scenario/profile CLI knobs and research receipt IDs, not a TrialSpec path or TrialSpec ID as the execution source. | Direct TrialSpec runner input is absent. |
| Scenario expansion | The matrix runner expands validation profile combinations and maps scenario fields through `replay_args`. | Existing execution seam still interprets profile/scenario inputs before replay. |
| Attempt start | `begin_topic_attempt` derives TrialSpecs from `ResearchTopic` and selected scenarios, then writes intent and attempt start. | TrialSpecs are produced by the current adapter before execution, not consumed by the runner as the execution request. |
| Attempt finish | `finish_topic_attempt` reads produced artifacts, reconstructs executed facts, compares requested vs executed, and writes terminal receipt. | Terminal receipt boundary exists and should be reused by any future direct TrialSpec seam. |
| Immutable writer | `receipt_store.py` validates payloads, checks identity/path matching, writes immutable JSON via atomic temp/link/fsync, and rejects non-identical collisions. | Identity persistence boundary exists, but it is a store boundary rather than direct runner input. |
| Ledger projection | `observation_ingest.py` rebuilds a DuckDB ledger from immutable corpus entities and validates receipt/intent/attempt/TrialSpec membership during ingestion. | Observation/ledger state is rebuildable projection after terminal receipt, not execution authority. |

## Minimum exact gap for direct canonical TrialSpec execution

Phase 1 does not implement this gap. The smallest future implementation slice would be:

1. Add a direct input seam for immutable TrialSpec identity, either as a TrialSpec corpus path or `trial_spec_id` resolved from the existing immutable corpus.
2. Validate the TrialSpec with the existing contract validator before execution.
3. Bind dataset bundle and ranking-source authority from the accepted execution spec; do not infer these from topic, queue order, candidate directory, profile name, or runner defaults.
4. Map only already-supported executable parameter fields (`horizon`, `stop_loss_pct`, `take_profit_pct`, `max_group_exposure`) into the existing replay args.
5. Preserve coverage-only / contract-dependent fields as non-executable unless a separate admitted card changes that contract.
6. Reuse the existing intent/attempt/terminal receipt machinery so requested-vs-executed differences remain explicit.
7. Keep the current backtest math untouched.

## Claim ledger

### Claim C0-P1-EXE-001

- claim_id: `C0-P1-EXE-001`
- claim: `Issue #14 admits Phase 1 as read-only inventory and seam discovery, with Phase 2, cutover, and production side effects explicitly not admitted.`
- classification: `CONTRACT`
- source_repo: `GitHub Issue`
- source_sha_or_version: `#14 updated_at=2026-09-01T02:26:05Z`
- source_path_or_official_url: `https://github.com/bluemaple18-home/NEW-TOP10/issues/14`
- source_range_or_section: `Status / Scope / Non-goals / Stop rules`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `This file may inventory the seam but may not implement queue, runner, capacity, canary, rollback, or bridge removal changes.`
- open_question: `None for Phase 1 authority; Phase 2 admission remains external to this worker.`
- owner: `Issue #14 / Mainline`

### Claim C0-P1-EXE-002

- claim_id: `C0-P1-EXE-002`
- claim: `Canonical backlog defines Card C as research execution control: queue reference, claim/lease, idempotency/retry, and direct TrialSpec runner, while preserving that C has no candidate priority or ranking authority.`
- classification: `CONTRACT`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `docs/RESEARCH_SPINE_BACKLOG.md`
- source_range_or_section: `L147-L179`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Runner and queue inventory must distinguish execution control from B-lane search/ranking authority.`
- open_question: `Exact Card C implementation remains inadmissible until the required checkpoints complete.`
- owner: `Canonical backlog`

### Claim C0-P1-EXE-003

- claim_id: `C0-P1-EXE-003`
- claim: `The repository already has a canonical TrialSpec contract with content-hash identity, canonical parameter validation, dataset authority, ranking-source authority, execution profile, and safety fields.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/contracts.py`
- source_range_or_section: `L281-L321`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `A direct runner seam should reuse this contract instead of introducing a second TrialSpec authority.`
- open_question: `Future work must decide the accepted input carrier: corpus path, TrialSpec ID resolver, or admitted thin adapter.`
- owner: `Research spine contract`

### Claim C0-P1-EXE-004

- claim_id: `C0-P1-EXE-004`
- claim: `The matrix runner command-line surface accepts scenario/profile knobs and research receipt identifiers, but no direct TrialSpec path or TrialSpec ID input that drives execution.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_backtest_strategy_matrix.py`
- source_range_or_section: `L64-L104`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Runner direct TrialSpec acceptance is currently absent.`
- open_question: `Whether the future seam should be owned by the matrix runner itself or a thin pre-run adapter is not admitted in Phase 1.`
- owner: `Runner surface`

### Claim C0-P1-EXE-005

- claim_id: `C0-P1-EXE-005`
- claim: `The matrix runner expands validation-profile scenarios and translates each scenario through `replay_args` before calling the existing portfolio replay.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_backtest_strategy_matrix.py`
- source_range_or_section: `L107-L130, L580-L623`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `The current executable seam is scenario expansion, not immutable TrialSpec consumption.`
- open_question: `Future direct TrialSpec execution must define how to bypass profile expansion without altering replay math.`
- owner: `Runner surface`

### Claim C0-P1-EXE-006

- claim_id: `C0-P1-EXE-006`
- claim: `Attempt start creates TrialSpecs from topic/scenario context, writes immutable TrialSpecs, creates research intent and attempt IDs, and records the started attempt.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/run_receipts.py`
- source_range_or_section: `L278-L424`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `The current adapter is upstream of execution; it is not evidence that the runner can directly accept an externally admitted canonical TrialSpec.`
- open_question: `Future work must decide whether this adapter is retained temporarily or narrowed after direct TrialSpec input exists.`
- owner: `Receipt boundary`

### Claim C0-P1-EXE-007

- claim_id: `C0-P1-EXE-007`
- claim: `Terminal receipt validation requires terminal status, requested identity fields, executed units, identity match status, and explicit requested-vs-executed difference disclosure.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/contracts.py`
- source_range_or_section: `L638-L934`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `The terminal boundary is establishable for Phase 1 and should be the receipt boundary reused by future execution-control work.`
- open_question: `No runtime mutation was performed, so this is source evidence rather than a fresh run receipt.`
- owner: `Research spine contract`

### Claim C0-P1-EXE-008

- claim_id: `C0-P1-EXE-008`
- claim: `AI Core baseline keeps current frontier authority at none / waiting for owner-product evidence and treats model-routing evidence as characterization, not implementation authority.`
- classification: `AUTHORITY_CHECK`
- source_repo: `ai-core`
- source_sha_or_version: `21801303adff285268f7646df94dc53da31a835f`
- source_path_or_official_url: `docs/ai-core-backlog.md`
- source_range_or_section: `L25-L29, L144-L151`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `No AI Core authority contradiction was found that would stop this Phase 1 evidence-only inventory.`
- open_question: `Future model routing or authority changes remain outside this worker.`
- owner: `AI Core backlog`

### Claim C0-P1-EXE-009

- claim_id: `C0-P1-EXE-009`
- claim: `The immutable JSON store validates payloads, verifies optional identity-field to filename matching, writes canonical JSON with temp-file/link/fsync semantics, returns identical existing writes as idempotent, and rejects non-identical collisions.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/receipt_store.py`
- source_range_or_section: `L16-L18, L34-L82, L84-L90, L93-L153`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Canonical identity persistence exists for TrialSpec/intent/attempt/receipt entities, but this store does not itself provide direct runner input, queue claim, lease, or retry authority.`
- open_question: `Future direct TrialSpec seam must decide how runner input resolves immutable corpus identity without adding a second store authority.`
- owner: `Research spine immutable corpus store`

### Claim C0-P1-EXE-010

- claim_id: `C0-P1-EXE-010`
- claim: `Observation ingestion treats the DuckDB ledger as rebuildable projection from immutable corpus inputs, validates receipt path identity and run receipt schema, verifies intent/attempt/requested/executed TrialSpec membership, verifies CAS artifacts, records observations/provenance, and records conflicts or rejections.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/observation_ingest.py`
- source_range_or_section: `L1-L43, L397-L419, L1060-L1234, L1276-L1395`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Terminal receipt and downstream observation projection boundaries are establishable from source, while ledger projection remains downstream evidence and not execution admission authority.`
- open_question: `Phase 1 did not rebuild or mutate the ledger, so this remains source-backed boundary evidence.`
- owner: `Research ledger ingestion`
