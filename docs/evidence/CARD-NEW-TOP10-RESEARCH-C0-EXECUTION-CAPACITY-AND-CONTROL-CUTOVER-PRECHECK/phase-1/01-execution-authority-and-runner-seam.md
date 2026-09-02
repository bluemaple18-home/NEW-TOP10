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

## Phase 1 authority transition map

`UNKNOWN` below means the inspected source did not establish that field without runtime mutation or external side effect. The map follows the BC-CP1 requested transition order; where current implementation order differs, the difference is called out explicitly.

| Transition | Source path / entrypoint | Input identity grain | Output identity grain | Authority class | Side effects | Current reader/writer | Failure behavior | Duplicate behavior | Replacement target | Removal condition/test |
|---|---|---|---|---|---|---|---|---|---|---|
| Request/proposal → selection | `scripts/build_research_decision_brief.py`; `app/research/shadow_plan_proposal.py`; `scripts/run_pm_research_harness_loop.py`; `scripts/run_autonomous_research.py` | source artifact path, proposal/projection IDs, PM card ID, topic/candidate identifiers | PM decision item, research card, `ResearchTopic.topic_id`, selected topic list | B/proposal or manager selection; not C priority authority | Brief/card/state files may be written by their runners; Phase 1 did not invoke them | Decision brief and PM harness are readers/writers; autonomous manager is topic selector | Boundary errors or failed subprocess in PM harness; invalid/missing source documents fail proposal | Proposal dedupe by `proposal_id`; manager avoids queued/history/registry duplicates | Canonical admitted CandidateDecision / TrialSpec request | Must wait for B0 candidate decision matrix and Card C admission; no removal test for this Phase 1 |
| Selection → TrialSpec resolution | `scripts/run_autonomous_research.py`; `app/research/run_receipts.py` | `ResearchTopic`, validation profile/scenario fields, dataset/ranking manifests | `trial_spec_id`, `requested_trial_spec_ids`, `intent_id`, `run_id`, `attempt_event_id` | Adapter-generated TrialSpec authority around current runner | Immutable TrialSpec/intent/attempt writes if executed | `begin_topic_attempt` writes immutable specs/intents/attempts | Contract validation or identity mismatch raises before/at write | Immutable store returns identical existing writes or rejects collisions | Direct TrialSpec input seam | Remove/narrow adapter only after runner accepts canonical TrialSpec directly |
| TrialSpec resolution → queue/admission | `scripts/run_autonomous_research.py` manager queue; `app/research/adaptive_shadow_queue.py` shadow projection | current queue uses `topic_id` and manager status; shadow queue uses semantic action IDs | `next_action_queue.json` actions, shadow queue projection rows | Manager queue/projection; not canonical TrialSpec admission | Manager writes queue; shadow projection writes only shadow outputs and checks canonical parity | Autonomous manager writer/reader; adaptive shadow queue projection/verifier | Invalid queue rows are skipped; projection fails closed on boundary/admission/parity errors | Manager queue bounded to actionable topics; shadow queue dedupes semantic actions | Queue references canonical TrialSpec identity only | Requires separate admitted queue-reference contract and removal of topic-only interpretation |
| Queue/admission → claim/lease/reservation | `scripts/run_fog_research_worker.sh`; `scripts/run_pm_research_harness_loop.sh`; `app/research/batch_owner.py` | process lock path, queue-owner lock, batch intent reference; no per-TrialSpec item identity | worker lock, queue-owner lock, batch intent authority result | Operational mutual exclusion / batch envelope; per-item claim authority missing | Lock files and status/retry files may be written by workers; Phase 1 did not invoke them | Fog worker and PM harness lock owners; batch owner verifier | stale pid cleanup, skip on active owner/PM harness, batch authority errors | No durable item duplicate claim found; batch argv hash catches envelope mismatch | Durable claim/lease/reservation per canonical TrialSpec or queue item | Not admitted in Phase 1; no removal test found for process locks |
| Claim/lease/reservation → runner | `scripts/run_daily_research_quota.sh`; `scripts/run_autonomous_research.py`; `app/research/batch_owner.py`; `scripts/run_backtest_strategy_matrix.py` | batch id, batch intent ref, normalized runner argv, selected topic/scenario/profile args | runner output artifact paths, matrix payload, run metadata | Batch envelope and allowlisted runner; not direct TrialSpec execution | Running would write outputs/ledger/projection; Phase 1 did not run | Daily quota shell invokes autonomous runner; autonomous runner invokes allowlisted scripts | nonzero runner exit leads verification/ingest handling and nonzero final exit | batch owner hashes argv and validates batch id/repo/stage/path; direct item duplicate behavior UNKNOWN | Runner consumes canonical TrialSpec identity | Requires direct TrialSpec seam and benchmark admission |
| Runner → attempt | `app/research/run_receipts.py`; `scripts/run_autonomous_research.py` | selected topic/scenarios and generated TrialSpecs | started attempt event with `run_id`, `intent_id`, `attempt_event_id` | Attempt lifecycle authority | Immutable attempt-start write | Attempt writer in `begin_topic_attempt`; runner main carries context | start validation or write collision fails loudly | immutable identity/path collision protection via store | Attempt starts from accepted TrialSpec execution intent | Keep lifecycle, change upstream input grain after direct seam |
| Attempt → terminal receipt | `app/research/run_receipts.py`; `app/research/contracts.py`; `app/research/receipt_store.py` | attempt context plus produced artifacts/matrix execution authority | immutable `receipt_id`, terminal status, executed units, requested/executed differences | Terminal receipt authority | Immutable receipt/CAS writes | `finish_topic_attempt` and receipt store writer | exceptions/KeyboardInterrupt/non-success produce terminal failure receipt paths when reachable; schema validation errors fail | identical immutable writes OK; non-identical collision rejected | Reuse for direct TrialSpec execution | No removal target; this is canonical boundary |
| Terminal receipt → retry/reconciliation | `app/research/run_receipts.py`; `scripts/run_autonomous_research.py`; `scripts/run_fog_research_worker.sh` | started attempts older than reconciliation threshold; topic manager status; failure fingerprint | orphan reconciliation event, updated manager status/queue, retry state/circuit state | Recovery/retry policy, not canonical claim retry | Reconciliation/manager/retry files may be written by runners; Phase 1 did not invoke them | receipt reconciliation writer; manager/fog retry writers | orphan attempts become UNKNOWN facts; retry circuit opens after max failures; manager controls cooldown/max runs | manager uses registry/history/queue duplicate suppression; claim-level duplicate retry UNKNOWN | Canonical claim retry tied to durable lease/attempt status | Requires separate admitted claim/retry design |
| Retry/reconciliation → legacy publication | `scripts/run_daily_research_quota.sh`; `app/research/history_compatibility_projection.py`; `scripts/run_weekend_representative_replay.py`; `app/research/a6_closure.py` | ledger/native receipts or representative replay rows | derived `run_history.jsonl`, projection manifest, legacy appender rows | Compatibility bridge / legacy writer, not new-run truth | Derived legacy history writes if invoked; Phase 1 did not invoke | daily quota projection writer; legacy replay appender source-declared | projection/verification failures stop daily quota chain; appender duplicate guard skips existing keys | projection replace/manifest; appender duplicate key guard | ledger-backed consumers and removal of legacy-history authority | A6 removal condition/test per bridge; removal itself not admitted |

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

### Claim C0-P1-EXE-011

- claim_id: `C0-P1-EXE-011`
- claim: `The Phase 1 transition map can establish source-backed boundaries for proposal/selection, adapter-generated TrialSpec resolution, topic queue projection, process-level locks, batch-envelope runner invocation, attempt start, terminal receipt, retry/reconciliation, and legacy publication; it cannot establish canonical TrialSpec queue admission or durable per-item claim/lease from the inspected sources.`
- classification: `WORKFLOW_INVENTORY`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/build_research_decision_brief.py; app/research/shadow_plan_proposal.py; scripts/run_pm_research_harness_loop.py; scripts/run_autonomous_research.py; app/research/run_receipts.py; app/research/receipt_store.py; app/research/batch_owner.py; scripts/run_fog_research_worker.sh; scripts/run_daily_research_quota.sh; app/research/history_compatibility_projection.py; scripts/run_weekend_representative_replay.py; app/research/a6_closure.py`
- source_range_or_section: `scripts/build_research_decision_brief.py L40-L67, L249-L285; app/research/shadow_plan_proposal.py L57-L76, L223-L336, L339-L380; scripts/run_pm_research_harness_loop.py L190-L208, L261-L267, L548-L595; scripts/run_autonomous_research.py L2228-L2238, L2305-L2378, L3022-L3238, L3990-L4215; app/research/run_receipts.py L60-L104, L278-L424, L520-L953; app/research/receipt_store.py L34-L82, L84-L90, L93-L153; app/research/batch_owner.py L22-L34, L66-L87, L143-L164, L167-L239, L385-L456; scripts/run_fog_research_worker.sh L22-L40, L48-L102, L141-L164, L189-L249, L251-L293; scripts/run_daily_research_quota.sh L73-L103, L137-L180, L183-L249; app/research/history_compatibility_projection.py L1-L23, L60-L141, L160-L191; scripts/run_weekend_representative_replay.py L114-L148, L151-L164; app/research/a6_closure.py L46-L60, L98-L244`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `MEDIUM_HIGH`
- conflict_with: `Card A desired end state requires direct TrialSpec runner and queue references to spec identity only`
- implication: `BC-CP1 should treat current C authority as partially bounded by source contracts but incomplete for canonical execution-control cutover.`
- open_question: `Runtime/live failure behavior and duplicate behavior remain unverified where source does not define them or Phase 1 forbids invocation.`
- owner: `C0 Phase 1 worker`
