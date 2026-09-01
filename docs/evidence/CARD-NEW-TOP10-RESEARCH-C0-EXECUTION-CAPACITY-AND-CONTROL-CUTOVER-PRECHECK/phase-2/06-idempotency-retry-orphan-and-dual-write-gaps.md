# C0 Phase 2 — Idempotency, Retry, Orphan, and Dual-Write Gaps

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-2`
- Candidate parent: `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`
- Canonical source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0 fixed SHA: `d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`
- Observed at: `2026-09-01T05:47:34Z`
- Boundary: source evidence only；未設計或實作 claim/lease/retry runtime，未 dual-write，未修改 queue 或 runner。

## Direct answer

現有系統有三個可重用的邊界：immutable store 的 idempotent write、terminal receipt 的 requested/executed disclosure、orphan reconciliation 的 unknown-facts contract。缺口是 C-layer execution control：沒有 per-TrialSpec/per-queue-item durable claim、lease expiry、claim retry、orphan adoption/requeue policy，也沒有被證明必要且安全的 dual-write cutover path。

## Gap map

| Control concern | Current fact | Gap for C1 |
|---|---|---|
| Idempotency | `write_immutable_json` 對相同 bytes 回 `EXISTS_IDENTICAL`，不同 collision 直接拒絕。 | 這是 storage idempotency，不是 queue item claim idempotency。 |
| Duplicate execution | Run receipt validator 要求 `requested_trial_spec_id` 與 `execution_unit_id` 唯一。 | 沒有「同一 TrialSpec 已 claim / in progress / terminal」的 durable admission table。 |
| Claim/lease | Fog worker與 queue owner lock 是 process/owner level。 | 缺 per-item lease identity、期限、renewal、steal/adopt gate。 |
| Retry | Fog worker有 batch retry circuit；autonomous manager有 topic rerun/cooldown。 | 缺 canonical claim retry count、retry reason、poison item / dead-letter policy。 |
| Orphan | Orphan reconciliation 明確把 executed facts、lineage、dataset bundle、result 標成 unknowable。 | 缺 orphan-to-claim transition：何時 requeue、adopt、mark terminal、或人工處理。 |
| Dual-write | A6 compatibility projection可由 ledger/native receipts產生 legacy run_history；shadow/proposal policies禁止 canonical queue writes。 | C1 不應直接新增 execution dual-write；若 future cutover 需要雙路輸出，必須先證明 consumer parity 與 fail-closed rollback。 |

## Required C1 control shape

1. Durable claim identity must be keyed by canonical TrialSpec or admitted queue-item identity, not topic title, profile name, runner argv, or process PID.
2. Claim lifecycle must include `AVAILABLE`, `CLAIMED`, `RUNNING`, `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_FINAL`, `ORPHANED`, `CANCELLED`, with monotonic attempt IDs.
3. Retry must bind retry count, retryable reason, backoff, poison/dead-letter state, and terminal receipt evidence.
4. Orphan reconciliation must never infer unknown execution facts; it may only requeue/adopt after explicit evidence and protected-surface parity.
5. Any dual-write period must be treated as temporary shadow/projection, not new truth authority.

## Claim ledger

### Claim C0P2-CTL-001

```yaml
claim_id: C0P2-CTL-001
claim: The immutable JSON store has content/idempotency protection for identical writes and rejects non-identical collisions, but it does not provide queue item claims or leases.
classification: OBSERVED_CODE_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/receipt_store.py
source_range_or_section: lines 16-18,34-90,93-153
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: treating immutable file idempotency as execution-control idempotency.
implication: C1 can reuse this store for facts, but needs a separate admitted claim/lease contract.
open_question: exact claim persistence carrier is not admitted.
owner: Research Spine store owner / future C1 owner
```

### Claim C0P2-CTL-002

```yaml
claim_id: C0P2-CTL-002
claim: Run receipt validation requires unique requested TrialSpec mapping, executed unit uniqueness, exact requested/executed difference disclosure, and non-success failure reason, which is sufficient receipt boundary but not claim scheduling authority.
classification: OBSERVED_CONTRACT_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/contracts.py
source_range_or_section: lines 735-935
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: bypassing terminal receipt when adding direct TrialSpec execution.
implication: C1 should keep terminal receipts as canonical execution evidence.
open_question: which pre-execution claim states produce which terminal receipt when no runner starts.
owner: Research Spine contract owner
```

### Claim C0P2-CTL-003

```yaml
claim_id: C0P2-CTL-003
claim: Orphan reconciliation is first-class and must keep executed parameters, lineage, dataset bundle, and result as UNKNOWN; therefore orphan recovery cannot invent executed facts.
classification: OBSERVED_CONTRACT_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/contracts.py
source_range_or_section: lines 385-409
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: auto-reconstructing execution facts after a missing terminal receipt.
implication: Future retry/orphan design must prefer explicit re-run or manual terminal handling over inferred success.
open_question: orphan retention, adoption, and requeue policy remain undefined.
owner: Future C1 claim/retry owner
```

### Claim C0P2-CTL-004

```yaml
claim_id: C0P2-CTL-004
claim: Current fog worker retry is batch/process oriented, with lock files, max retries, backoff, and circuit-open state; it is not canonical per-TrialSpec retry authority.
classification: OBSERVED_RUNTIME_SOURCE_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: scripts/run_fog_research_worker.sh
source_range_or_section: lines 22-40,48-102,139-180,189-293,356-380
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: claiming the existing worker provides durable item-level lease/retry.
implication: C1 needs item-level retry/lease semantics before admission.
open_question: whether fog worker remains outer supervisor after C1 or is narrowed.
owner: Fog worker owner / future C1 owner
```

### Claim C0P2-CTL-005

```yaml
claim_id: C0P2-CTL-005
claim: Dual-write necessity is not proven for C0 Phase 2; existing A6 path already treats legacy run history as derived compatibility projection, while shadow/proposal policies explicitly forbid canonical queue writes and production changes.
classification: DUAL_WRITE_NOT_PROVEN_GAP
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/a6_closure.py; config/research_shadow_queue_policy_v1.json; config/native_evidence_activation_policy_v1.json
source_range_or_section: a6_closure.py lines 98-244; research_shadow_queue_policy_v1.json lines 37-46; native_evidence_activation_policy_v1.json lines 72-78
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: adding dual-write as a default C1 mechanism without consumer parity evidence.
implication: Future cutover should prefer shadow projection and protected-surface parity; dual-write requires a separate explicit gate.
open_question: which live consumers still require legacy run_history during transition.
owner: Integrator / future C1 cutover owner
```
