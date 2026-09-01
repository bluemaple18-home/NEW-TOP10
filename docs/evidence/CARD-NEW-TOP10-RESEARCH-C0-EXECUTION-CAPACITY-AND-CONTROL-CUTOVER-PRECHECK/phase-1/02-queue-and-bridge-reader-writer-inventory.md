# C0 Phase 1 — Queue and Bridge Reader/Writer Inventory

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-1`
- NEW-TOP10 source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- AI Core source SHA: `21801303adff285268f7646df94dc53da31a835f`
- Observed at: `2026-09-01T03:30:48Z`
- Boundary: source inventory only. This file does not define a queue contract, claim/lease/retry design, writer cutover, bridge removal, or production readiness.

## Queue / reader / writer responsibility map

| Responsibility | Current owner or surface | Phase 1 finding |
|---|---|---|
| Candidate/topic generation | `run_autonomous_research.py` builds topics from ledger signals, external review, ranking dirs, candidate dirs, and topic bank. | This is B/search-adjacent interpretation and must not become C priority authority. |
| Queue projection | `next_action_queue.json` is maintained by the autonomous research manager and consumed queue-first by selection. | Queue is topic-oriented, not canonical TrialSpec-reference-only execution admission. |
| Fallback selection | If queue rows are invalid or not enough, active topic-bank fallback may still select work. | Queue is not the sole execution admission boundary. |
| Batch owner | `batch_owner.py` binds scheduler owner, runner argv hash, paths, catalog/policy hashes, and write set into immutable batch intent. | Batch intent constrains a run envelope, but it is not per-TrialSpec claim/lease. |
| Controlled-grid drain host runner | `run_controlled_grid_drain_host_runner.py` is linkage-only and records `NO_PRODUCTION_CHANGE`, with gates/status outputs and notes excluding replay, training, ranking writes, or promotion. | Operational boundary exists for linkage repair, not execution capacity benchmark authority. |
| Process mutual exclusion | Fog worker and PM harness use lock files and queue-owner locks. | Locks prevent concurrent process/owner interference; they are not durable per-item leases. |
| Retry | Manager rerun policy and fog-worker retry circuit exist. | Retry exists as topic/batch operational policy, not canonical per-TrialSpec claim retry. |
| Terminal receipt | `run_receipts.py` starts attempts and finishes receipts. | Receipt boundary exists and is first-party immutable evidence. |
| Legacy history projection | A6 compatibility projection writes derived legacy `run_history.jsonl`; other A6 surfaces read/write or validate legacy history. | Bridges remain compatibility/recovery surfaces, not canonical truth authority. |

## Queue / claim / retry answer

- Queue: present as a topic-oriented manager queue plus projections; not yet a canonical TrialSpec-ID-only queue.
- Claim/lease: absent at canonical TrialSpec or queue-item granularity. Existing locks are process and queue-owner locks, not durable item claims.
- Retry: present as controlled topic rerun policy and fog-worker batch retry circuit; not yet an admitted canonical claim retry policy.

## Path-level `next_action_queue.json` inventory

This table is bounded to non-test runtime/tooling hits from fixed-base `git grep -l next_action_queue.json -- '*.py' '*.sh'`, plus canonical queue aliases, PM-approved queue, and related weekend frontier queue surfaces. `Current reader/writer` names source-level behavior only; no runtime invocation was performed. Test-only hits under `tests/` are excluded from runtime/tooling reader-writer inventory because they are fixtures/assertions rather than deployed readers or writers; they remain verification coverage, not queue authority.

| Path or queue surface | Source path / entrypoint | Classification | Input identity grain | Output identity grain | Authority class | Side effects | Current reader/writer | Failure behavior | Duplicate behavior | Replacement target | Removal condition/test |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `artifacts/autonomous_research/next_action_queue.json` | `scripts/run_autonomous_research.py` | `authority/current-manager-writer-and-reader` | `topic_id`, manager status, next action, candidate dir | queue actions list, top 25 actionable topics | manager queue, not TrialSpec admission | writes queue with registry/history/summary/runner registry when manager update enabled | writer: `update_manager`; reader: `load_next_action_queue`, selection | invalid/missing rows skipped; no queue yields fallback | queued/history/registry duplicates suppressed by topic ID paths | TrialSpec identity queue reference | admitted Card C queue-reference contract; no current removal test |
| `artifacts/autonomous_research/next_action_queue.json` in synthetic temp root | `scripts/verify_autonomous_research.py` | `verifier/tooling` | synthetic topic IDs, temp registry rows, temp queue actions, cooldown timestamps | boolean verification checks and `autonomous-research-verification.v1` artifact | verifier only, not runtime queue authority | writes synthetic temp queue/registry and verification artifact if invoked; Phase 1 did not invoke it | verifier writer/reader in temp root | returns FAILED/nonzero if checks fail; synthetic note says no real backtest | checks queue order, cooldown blocking, exhausted/rejected blocking, legacy flags, and missing-queue no-fallback behavior; no production duplicate claim | regression guard for current manager queue semantics | excluded from runtime authority; no removal target unless queue semantics are replaced and verifier updated |
| `artifacts/autonomous_research/next_action_queue.json` in batch intent manager paths | `app/research/batch_owner.py` | `authority/envelope-verifier` | manager root path and runner argv hash | batch intent path record / authority PASS | run-envelope authority | writes/verifies batch intent, not queue content | verifier of expected manager path | authority errors on path/argv/stage/repo mismatch | argv hash/content hash mismatch rejected | retain envelope, align queue path to TrialSpec queue later | UNKNOWN |
| `artifacts/autonomous_research/next_action_queue.json` | `scripts/run_pm_research_harness_loop.py` | `authority/harness-writer` | queue depth, topic registry, topic bank, PM decision state | top-up queue actions and harness status | PM harness low-water queue top-up, not canonical admission | writes approved work queue, research cards, canonical next-action queue top-up, harness state | reader/writer | subprocess failure raises; loop disables on empty/no approval thresholds | consumed approval keys and added topic IDs suppress duplicates | TrialSpec identity queue reference or PM-approved CandidateDecision handoff | UNKNOWN |
| `artifacts/autonomous_research/next_action_queue.json` | `scripts/build_research_fog_map.py` | `consumer/bridge` | queue JSON actions | fog map payload source path and status fields | projection consumer | writes fog-map artifact when invoked | reader | missing path yields empty read and source path `None` | UNKNOWN | ledger/native observation backed fog map | A6 fog-map bridge removal condition/test |
| `artifacts/autonomous_research/next_action_queue.json` | `scripts/build_research_decision_brief.py` | `consumer/proposal` | queue actions | PM decision brief entries | advisory decision consumer | writes brief artifacts when invoked | reader | only recognized action/status rows become decisions | `unique_decisions` dedupes decision list | B0 CandidateDecision / canonical admission | UNKNOWN |
| `artifacts/autonomous_research/next_action_queue.json` | `scripts/build_strategy_archetype_evidence_map.py` | `consumer/projection` | queue actions by archetype | strategy archetype evidence map | advisory projection | writes evidence-map artifact when invoked | reader | UNKNOWN | classification groups queue actions | B0 decision matrix or ledger-backed projection | UNKNOWN |
| `artifacts/autonomous_research/next_action_queue.json` | `app/research/native_evidence_activation.py` | `verifier/protected-surface-inventory` | queue path role and file hash/existence | baseline lock row and readiness reason codes | pre-activation guard | read-only inventory function; scripts may write evidence elsewhere | reader/verifier | missing required lock adds readiness reason | duplicate role/path rejected in policy validation | activation policy after capacity proof | UNKNOWN |
| `artifacts/autonomous_research/next_action_queue.json` | `scripts/native_evidence_replay_bundle.py` | `verifier/reusable-intermediate` | parity path list and file/tree hashes | parity hash before/after cycles/cleanup | isolated replay evidence guard | writes docs/evidence bundle/manifest if invoked; not invoked here | reader/verifier | parity drift raises; capacity exceed raises | UNKNOWN | benchmark input candidate after B0, if admitted | UNKNOWN |
| `artifacts/autonomous_research/next_action_queue.json` | `app/research/adaptive_shadow_queue.py`; `scripts/build_adaptive_shadow_queue.py`; `scripts/verify_adaptive_shadow_queue.py` | `projection/verifier` | committed bundle/manifest/policy plus canonical queue path/hash | shadow projection, comparison, receipt | shadow-only non-writer | writes shadow outputs, not canonical queue | reader/verifier | boundary/admission/parity errors fail closed | semantic action dedupe and collision errors | Card B/B0 candidate-decision input, not C execution queue | adaptive queue is not canonical until separately admitted |
| `artifacts/autonomous_research/next_action_queue.json` | `app/research/shadow_plan_proposal.py` | `proposal/verifier` | adaptive shadow projection rows, policy/catalog hashes, protected surface parity | proposal set/proposals | proposal only | writes proposal artifact if invoked, not queue | reader/verifier | source drift/protected-surface drift fails closed | proposal ID dedupe or collision error | human/B0 reviewed candidate decisions | UNKNOWN |
| `artifacts/autonomous_research/next_action_queue.json` | `scripts/run_top10_fog_map_handoff.py` | `consumer/artifact-manifest` | path presence as research artifact | harness event artifact list | bridge/consumer | event artifact read/write if invoked | artifact collector | UNKNOWN | UNKNOWN | native receipt/ledger artifacts | UNKNOWN |
| PM approved work queue (`approved_work_queue.json`) | `scripts/run_pm_research_harness_loop.py`; `scripts/verify_pm_approved_work_queue.py` | `authority-input/verifier` | PM card ID, run dir, route `research_worker` | approved work queue and research cards | PM approval intake, not canonical C admission | writes approved queue/research cards; verifier reads only | writer/verifier | verifier fails schema/approval/production-block/card-count checks | consumed approval keys suppress reprocessing | B0 CandidateDecision intake | UNKNOWN |
| Weekend frontier queue (`artifacts/weekend_training/weekend_frontier_queue_<date>.json`) | `scripts/build_weekend_universe_inventory.py`; `scripts/build_weekend_frontier_queue.py`; `scripts/verify_weekend_frontier_queue.py`; `scripts/run_weekend_representative_replay.py`; `scripts/run_representative_replay_drain_worker.py` | `related-queue/bridge` | weekend inventory rows/date | frontier queue, verification, representative replay input | weekend linkage/replay queue, not canonical `next_action_queue` | writes weekend queue/verifier/replay artifacts if invoked | writer/verifier/reader | verifier failed count; representative runner partial/OK status | selected rows by index/batch; duplicate behavior for queue rows UNKNOWN | ledger/native replay task identity | UNKNOWN |

## A6 bridge classification

Classification key:

- `active/source-declared`: A6 inventory marks the bridge as active or active legacy writer. This is source-level evidence, not proof of live production invocation unless an entrypoint is also cited.
- `historical`: A6 inventory marks the surface as historical migration input only.
- `recovery-only`: A6 inventory quarantines the surface to backfill/recovery tooling.
- `live-activity-unverified`: Phase 1 source inspection did not establish current live invocation evidence for that bridge.

| Bridge ID | A6 status / direction | Phase 1 classification | Runtime activity note |
|---|---|---|---|
| `history_compatibility_projection` | `ACTIVE_BRIDGE`, derived compatibility projection | `active/source-declared` | Daily quota script invokes projection and verification after receipt/ledger verification. |
| `legacy_run_history_jsonl_migration` | Historical migration source | `historical` | Historical input only. |
| `legacy_run_history_json_migration` | Historical migration source | `historical` | Historical input only. |
| `research_map_run_history_backfill` | Isolated migration/recovery writer | `recovery-only` | Quarantined from normal runs by A6 inventory. |
| `research_map_backfill_verifier` | Backfill format validator | `recovery-only` | Active support for recovery tooling, not normal execution authority. |
| `fog_map_run_history_reader` | `ACTIVE_BRIDGE`, read-only | `active/source-declared` | Daily quota path refreshes research map from history after projection; exact per-reader invocation remains source-level. |
| `campaign_progress_run_history_reader` | `ACTIVE_BRIDGE`, read-only | `active/source-declared + live-activity-unverified` | Source surface exists; no allowed Phase 1 runtime invocation proof. |
| `weekend_training_run_history_reader` | `ACTIVE_BRIDGE`, read-only | `active/source-declared + live-activity-unverified` | Source surface exists; no allowed Phase 1 runtime invocation proof. |
| `liquidity_v2_run_history_reader` | `ACTIVE_BRIDGE`, read-only | `active/source-declared + live-activity-unverified` | Source surface exists; no allowed Phase 1 runtime invocation proof. |
| `legacy_run_history_appenders` | `ACTIVE_LEGACY_WRITER` | `active/source-declared + live-activity-unverified` | A6 maps this bridge to `scripts/run_weekend_representative_replay.py` `append_history`; Phase 1 did not establish live invocation evidence. |
| `liquidity_v2_batch_run_history_bridge` | `ACTIVE_LEGACY_WRITER` | `active/source-declared + live-activity-unverified` | Source surface exists; no allowed Phase 1 runtime invocation proof. |
| `research_fog_map_verifier_reader` | `ACTIVE_BRIDGE`, read-only | `active/source-declared` | Verification surface exists in A6 inventory and daily quota invokes research map verification after projection. |
| `combo_effectiveness_run_history_reader` | `ACTIVE_BRIDGE`, read-only | `active/source-declared + live-activity-unverified` | Source surface exists; no allowed Phase 1 runtime invocation proof. |

## Claim ledger

### Claim C0-P1-QBI-001

- claim_id: `C0-P1-QBI-001`
- claim: `The daily research quota entrypoint runs the autonomous research runner, verifies research spine batch output, ingests/verifies ledger output, emits runtime receipt verification, then writes and verifies history compatibility projection before refreshing the research map from history.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_daily_research_quota.sh`
- source_range_or_section: `L73-L103, L137-L180, L183-L207, L215-L249`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `The normal scripted chain has first-party receipt/ledger checks followed by A6 legacy-history projection, but this is not direct TrialSpec queue execution.`
- open_question: `No Phase 1 runtime invocation was performed, so live scheduler state remains outside scope.`
- owner: `Daily research quota entrypoint`

### Claim C0-P1-QBI-002

- claim_id: `C0-P1-QBI-002`
- claim: `Autonomous research selection is queue-first but not queue-only; invalid or insufficient queue rows can yield to active topic-bank fallback.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_autonomous_research.py`
- source_range_or_section: `L2228-L2238, L2305-L2378`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `The current queue is not a canonical execution admission boundary that references only TrialSpec identity.`
- open_question: `Future C work must decide whether active-bank fallback remains allowed after canonical queue admission is introduced.`
- owner: `Autonomous research manager`

### Claim C0-P1-QBI-003

- claim_id: `C0-P1-QBI-003`
- claim: `Fog worker locking uses worker lock and queue-owner lock files to avoid concurrent process or owner interference, including stale-lock handling.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_fog_research_worker.sh`
- source_range_or_section: `L22-L40, L48-L73, L75-L102, L127-L137`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Existing locks are operational mutual exclusion, not durable per-TrialSpec claim/lease authority.`
- open_question: `Future claim/lease design remains Phase 2-or-later and is not admitted by this file.`
- owner: `Fog research worker`

### Claim C0-P1-QBI-004

- claim_id: `C0-P1-QBI-004`
- claim: `Retry currently exists as controlled topic rerun policy in the autonomous manager and as a fog-worker retry circuit with backoff, max retry count, and circuit-open state.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_autonomous_research.py; scripts/run_fog_research_worker.sh`
- source_range_or_section: `scripts/run_autonomous_research.py L91-L118, L2272-L2302; scripts/run_fog_research_worker.sh L141-L164, L189-L249, L251-L293`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Retry responsibility exists, but not in the canonical per-claim execution-control form Card C ultimately needs.`
- open_question: `Future C work must decide retry ownership after claim/lease authority is admitted.`
- owner: `Autonomous research manager / fog worker`

### Claim C0-P1-QBI-005

- claim_id: `C0-P1-QBI-005`
- claim: `Adaptive shadow queue is explicitly a projection; it compares against the canonical manager queue and verifies that canonical queue content remains unchanged before and after projection build.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/adaptive_shadow_queue.py`
- source_range_or_section: `L1-L4, L21-L49, L541-L715`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `The shadow queue is not an admitted canonical writer or replacement queue.`
- open_question: `Whether an adaptive queue becomes canonical is outside C0 Phase 1.`
- owner: `Adaptive shadow queue projection`

### Claim C0-P1-QBI-006

- claim_id: `C0-P1-QBI-006`
- claim: `A6 bridge inventory defines 13 bridge rows with owner, direction, read/write mode, removal condition, removal test, target stage, and status; validator rejects truth-authority bridges.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/a6_closure.py`
- source_range_or_section: `L30-L60, L98-L244, L247-L287`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Bridge classification can use A6 source-declared status, but cannot promote bridges to canonical truth authority.`
- open_question: `Live activity for several bridge surfaces requires runtime/log evidence outside this Phase 1 static inventory.`
- owner: `A6 closure inventory`

### Claim C0-P1-QBI-007

- claim_id: `C0-P1-QBI-007`
- claim: `A6 bridge removal tests check that mapped source paths and markers exist and define one bridge-specific test per known bridge surface.`
- classification: `OBSERVED_TEST`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `tests/test_research_spine_a6_bridge_removals.py`
- source_range_or_section: `L1-L64`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Removal-test presence is source verification, not proof that each bridge is currently invoked.`
- open_question: `Future bridge-removal or runtime-activity proof is Phase 2/C1-adjacent and not admitted here.`
- owner: `A6 bridge removal tests`

### Claim C0-P1-QBI-008

- claim_id: `C0-P1-QBI-008`
- claim: `Compatibility history projection is a derived projection from Research Ledger/native receipt data to legacy run history format, and migration reads historical legacy history sources separately.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/history_compatibility_projection.py; app/research/legacy_migration.py`
- source_range_or_section: `app/research/history_compatibility_projection.py L1-L23, L60-L141, L160-L191; app/research/legacy_migration.py L47-L129, L131-L181`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Legacy history can be categorized as derived/historical compatibility, not current canonical execution truth.`
- open_question: `Bridge removal sequencing remains explicitly outside Phase 1.`
- owner: `A6 compatibility projection / legacy migration`

### Claim C0-P1-QBI-009

- claim_id: `C0-P1-QBI-009`
- claim: `Batch owner authority binds canonical scheduler owner and entrypoint, normalized runner argv/hash, repo head, requested/allowed research stage, manager paths, corpus/ledger/output paths, policy/catalog hashes, and safety flags into a content-addressed batch intent; verification rejects missing intent unless the write set is isolated and otherwise checks scheduler, repo, argv, stage, and path matches.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/batch_owner.py`
- source_range_or_section: `L22-L34, L66-L87, L143-L164, L167-L239, L385-L456`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Batch intent provides run-envelope authority and isolated-write-set checks, but does not create per-TrialSpec queue claim/lease/retry semantics.`
- open_question: `Future C work must decide whether batch owner remains envelope-only after canonical queue references are introduced.`
- owner: `Daily research batch owner`

### Claim C0-P1-QBI-010

- claim_id: `C0-P1-QBI-010`
- claim: `Controlled-grid drain host runner is explicitly linkage-only, declares no production change, builds/validates queue/linkage/fog-map artifacts, may perform cleanup only inside its linkage flow, and records status/summary outputs stating no replay execution, model training, production ranking write, or promotion.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_controlled_grid_drain_host_runner.py`
- source_range_or_section: `L1-L6, L19-L22, L81-L119, L122-L178, L191-L235, L238-L293`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `This host runner is an operational/linkage boundary source, not authorization to run production, replay, benchmark, or capacity commands in Phase 1.`
- open_question: `Phase 1 did not execute this runner; live operational state remains unverified.`
- owner: `Controlled-grid drain host runner`

### Claim C0-P1-QBI-011

- claim_id: `C0-P1-QBI-011`
- claim: `A6 maps legacy_run_history_appenders to scripts/run_weekend_representative_replay.py marker append_history, and the mapped function appends completed representative replay rows to legacy run history only when append mode is requested and duplicate guard permits it.`
- classification: `OBSERVED_CODE`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/a6_closure.py; scripts/run_weekend_representative_replay.py`
- source_range_or_section: `app/research/a6_closure.py L46-L60, L201-L210; scripts/run_weekend_representative_replay.py L114-L148, L151-L164`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `Prior candidate text incorrectly attributed the activity note to autonomous manager writes`
- implication: `Bridge table now classifies this as source-declared active legacy writer with live activity unverified, not as proven autonomous-manager runtime activity.`
- open_question: `Live invocation evidence for this appender remains outside Phase 1 because runtime execution was forbidden.`
- owner: `A6 closure inventory / legacy replay runner`

### Claim C0-P1-QBI-012

- claim_id: `C0-P1-QBI-012`
- claim: `Path-level inventory shows the canonical autonomous next-action queue is currently a topic-oriented manager queue read and written by run_autonomous_research.py, with batch_owner.py verifying its manager path as part of batch envelope authority and PM harness able to top it up from registry/topic-bank state; none of these sources make it a TrialSpec-ID-only admission queue.`
- classification: `QUEUE_PATH_INVENTORY`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_autonomous_research.py; app/research/batch_owner.py; scripts/run_pm_research_harness_loop.py`
- source_range_or_section: `scripts/run_autonomous_research.py L2228-L2238, L2305-L2378, L2538-L2582, L3022-L3238, L3884-L3894; app/research/batch_owner.py L167-L239, L385-L456; scripts/run_pm_research_harness_loop.py L142-L171, L190-L208, L261-L267, L548-L595, L615-L645`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `Card A desired end state requires queue references to spec identity only`
- implication: `BC-CP1 should classify current queue authority as manager/topic authority plus batch envelope verification, not canonical TrialSpec admission.`
- open_question: `Per-item claim/lease/duplicate handling for TrialSpec identity remains missing.`
- owner: `Autonomous research manager / batch owner / PM harness`

### Claim C0-P1-QBI-013

- claim_id: `C0-P1-QBI-013`
- claim: `Fog Map, decision brief, strategy archetype evidence map, and top10 fog map handoff read or list next_action_queue.json as consumer/projection/bridge inputs; they do not write canonical queue authority.`
- classification: `QUEUE_CONSUMER_INVENTORY`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/build_research_fog_map.py; scripts/build_research_decision_brief.py; scripts/build_strategy_archetype_evidence_map.py; scripts/run_top10_fog_map_handoff.py`
- source_range_or_section: `scripts/build_research_fog_map.py L141-L166; scripts/build_research_decision_brief.py L40-L67, L249-L285; scripts/build_strategy_archetype_evidence_map.py L60-L145; scripts/run_top10_fog_map_handoff.py L220-L228`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `These queue readers should be treated as consumers/projections/bridges, not queue authority owners.`
- open_question: `Runtime invocation frequency is unverified because Phase 1 did not run operational flows.`
- owner: `Fog Map / decision brief / research handoff consumers`

### Claim C0-P1-QBI-014

- claim_id: `C0-P1-QBI-014`
- claim: `Native evidence activation, native evidence replay bundle, adaptive shadow queue, adaptive queue verifier, and shadow plan proposal treat next_action_queue.json as protected surface, parity input, or shadow-only/proposal input with canonical_queue_write_allowed false; they are not canonical queue writers.`
- classification: `QUEUE_VERIFIER_PROJECTION_INVENTORY`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `app/research/native_evidence_activation.py; scripts/native_evidence_replay_bundle.py; app/research/adaptive_shadow_queue.py; scripts/build_adaptive_shadow_queue.py; scripts/verify_adaptive_shadow_queue.py; app/research/shadow_plan_proposal.py`
- source_range_or_section: `app/research/native_evidence_activation.py L24-L70, L188-L255, L511-L535; scripts/native_evidence_replay_bundle.py L34-L46, L77-L83, L333-L429; app/research/adaptive_shadow_queue.py L159-L218, L238-L274, L541-L681, L684-L715, L757-L855; scripts/build_adaptive_shadow_queue.py L14-L26, L29-L80; scripts/verify_adaptive_shadow_queue.py L16-L33, L36-L122, L125-L188; app/research/shadow_plan_proposal.py L57-L76, L140-L147, L223-L336, L339-L380`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `BC-CP1 should not treat shadow/proposal/parity surfaces as current queue authority.`
- open_question: `Whether any projection becomes a canonical queue writer is outside Phase 1 and requires separate admission.`
- owner: `Native evidence / adaptive shadow / proposal surfaces`

### Claim C0-P1-QBI-015

- claim_id: `C0-P1-QBI-015`
- claim: `Related PM-approved work queue and weekend frontier queue surfaces have their own schemas, verifiers, and replay/linkage readers; they are adjacent queues or bridges, not the canonical autonomous next_action_queue.json authority.`
- classification: `RELATED_QUEUE_INVENTORY`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/run_pm_research_harness_loop.py; scripts/verify_pm_approved_work_queue.py; scripts/build_weekend_universe_inventory.py; scripts/build_weekend_frontier_queue.py; scripts/verify_weekend_frontier_queue.py; scripts/run_weekend_representative_replay.py; scripts/run_representative_replay_drain_worker.py`
- source_range_or_section: `scripts/run_pm_research_harness_loop.py L142-L171, L615-L645; scripts/verify_pm_approved_work_queue.py L50-L91; scripts/build_weekend_universe_inventory.py L291-L312; scripts/build_weekend_frontier_queue.py L185-L194; scripts/verify_weekend_frontier_queue.py L98-L108; scripts/run_weekend_representative_replay.py L86-L87, L151-L164, L211-L213; scripts/run_representative_replay_drain_worker.py L134-L155, L324-L324`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `None observed`
- implication: `Queue inventory must keep PM intake and weekend replay queues separate from canonical C execution queue requirements.`
- open_question: `Replacement/removal tests for these adjacent queues were not established in Phase 1.`
- owner: `PM harness / weekend training queue surfaces`

### Claim C0-P1-QBI-016

- claim_id: `C0-P1-QBI-016`
- claim: `Fixed-base non-test runtime/tooling grep includes scripts/verify_autonomous_research.py; this script verifies manager update and queue selection/cooldown behavior using synthetic temp-root queue and registry fixtures, writes an autonomous-research-verification artifact, and explicitly notes that it does not run a real backtest.`
- classification: `QUEUE_VERIFIER_INVENTORY`
- source_repo: `NEW-TOP10`
- source_sha_or_version: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- source_path_or_official_url: `scripts/verify_autonomous_research.py`
- source_range_or_section: `L180-L225, L228-L339, L367-L396`
- observed_at: `2026-09-01T03:30:48Z`
- confidence: `HIGH`
- conflict_with: `Previous repair table omitted this non-test tooling hit`
- implication: `The verifier should be classified as tooling verification coverage, not runtime queue authority or a capacity benchmark plan.`
- open_question: `Phase 1 did not execute the verifier; runtime status of current queue remains unverified.`
- owner: `Autonomous research verifier`
