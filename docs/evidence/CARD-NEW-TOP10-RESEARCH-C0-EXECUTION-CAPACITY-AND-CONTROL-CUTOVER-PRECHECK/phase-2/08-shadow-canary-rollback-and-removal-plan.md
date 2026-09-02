# C0 Phase 2 — Shadow Canary, Rollback, and Removal Plan

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-2`
- Candidate parent: `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`
- Canonical source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- Observed at: `2026-09-01T05:47:34Z`
- Boundary: plan/receipt only。未執行 canary、未啟 scheduler、未切換 reader/writer、未移除 bridge。

## Direct answer

C1 前只能接受 shadow canary plan，不可接受 production canary。可重用 native-evidence activation 的 protected-surface、capacity budget、cleanup、stop-loss 與 parity 模式；但 C1 admission 前仍缺 direct TrialSpec seam、item claim/lease/retry、representative capacity、E4 cadence、A6 consumer parity、rollback drill。

## Shadow canary plan

| Gate | Required proof before C1 canary | Current status |
|---|---|---|
| Input authority | admitted CandidateDecision → Canonical TrialSpec identity; no topic-only fallback | BLOCKED |
| Execution isolation | output root separated from production, queue, scheduler, model, ranking, publish | DESIGN ONLY |
| Capacity | representative E3 sample with wall time, candidate/sec, CPU, peak RSS, I/O, bytes/files, cleanup | UNMEASURED |
| Claim/lease | durable per-item claim with retry/orphan states and terminal receipt binding | MISSING |
| Protected parity | before/after hashes for queue, scheduler, production, corpus, ledger, bridge surfaces | PATTERN EXISTS, NOT RUN |
| Dual-write/cutover | shadow projection parity before any write switch; no execution dual-write by default | NOT PROVEN |
| Rollback | fail-closed disable switch, no deletion of canonical receipts, legacy projection retained | DESIGN ONLY |
| Removal | bridge-specific consumer parity and tests after shadow pass | NOT READY |

## Rollback design

Rollback should mean disabling the new C execution-control seam and returning to current source-declared legacy/projection behavior without deleting immutable receipts. It must not erase canonical corpus facts, mutate model/ranking/publish artifacts, or mark unknown orphan facts as success. Any stuck claim must become terminal evidence or explicit orphan receipt before requeue.

## Removal plan

1. Keep all A6 bridges until ledger/native consumer parity is proven per bridge.
2. For `CARD_C_CONTROL_CUTOVER` bridges, first shadow-read both old and new consumers and compare semantic outputs.
3. Disable legacy writer only after new runs first persist intent/attempt/receipt and compatibility output is derived from ledger.
4. Remove bridge source only after removal test changes from "surface exists" to "consumer no longer requires legacy input" and passes.
5. Preserve historical/recovery tools unless a separate archival-retirement card admits deletion.

## Claim ledger

### Claim C0P2-SCR-001

```yaml
claim_id: C0P2-SCR-001
claim: Native evidence activation policy already encodes capacity budget, protected queue/scheduler/production surfaces, storage write paths, and safety flags forbidding production promotion, queue selection change, and scheduler change.
classification: REUSABLE_POLICY_PATTERN
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/native_evidence_activation_policy_v1.json
source_range_or_section: lines 1-79
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: creating an unbounded production canary plan.
implication: Future shadow canary should reuse this protected-surface/capacity shape, not bypass it.
open_question: C1-specific surfaces and thresholds remain to be admitted.
owner: C1 shadow canary owner
```

### Claim C0P2-SCR-002

```yaml
claim_id: C0P2-SCR-002
claim: Existing native evidence canary evidence reports manual-only development-only execution, scheduler disabled, no production promotion, isolated root, capacity budgets, cleanup pass, stop-loss pass, and production/queue hashes unchanged.
classification: COMMITTED_CANARY_PATTERN_EVIDENCE
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-V1/capacity_and_real_canary.json
source_range_or_section: lines 1-103
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: using historical native canary as current C1 canary pass.
implication: This is a pattern and historical evidence only; C1 still needs its own shadow canary.
open_question: no C1 claim/lease/direct TrialSpec canary has been run.
owner: Native evidence owner / future C1 owner
```

### Claim C0P2-SCR-003

```yaml
claim_id: C0P2-SCR-003
claim: Adaptive shadow queue policy is explicitly shadow-only and forbids canonical queue writes, manager selection changes, scheduler changes, production changes, synthetic fallback, legacy fallback, and sealed/unknown fallback.
classification: SHADOW_BOUNDARY_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/research_shadow_queue_policy_v1.json
source_range_or_section: lines 1-47
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: treating shadow queue output as canonical queue admission.
implication: C1 cutover must introduce separate admitted authority before changing queue selection.
open_question: future canonical queue-reference contract not admitted.
owner: Shadow queue policy owner / future C1 owner
```

### Claim C0P2-SCR-004

```yaml
claim_id: C0P2-SCR-004
claim: C1 remains blocked because direct TrialSpec runner seam, claim/lease/retry, representative E3 capacity, E4 cadence, A6 consumer parity, and rollback drill are missing.
classification: BLOCKER_SYNTHESIS
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba; d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-1/01-execution-authority-and-runner-seam.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md
source_range_or_section: C0 phase-1 lines 12-38,40-54; B0 phase-1 lines 17-35,153-170
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: admitting production canary or bridge removal from source-only evidence.
implication: Shadow plan may proceed only as future admitted work; no C1 admission now.
open_question: independent reviewer/Integrator decision remains required.
owner: Mainline Integrator / future C1 owner
```
