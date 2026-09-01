# C0 Phase 2 — A6 Bridge to Cutover Map

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-2`
- Candidate parent: `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`
- Canonical source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- A6 evidence source: `docs/evidence/CARD-NEW-TOP10-RESEARCH-A6-DEPRECATION-REBUILD-AND-BRIDGE-REMOVAL-GATES`
- Observed at: `2026-09-01T05:47:34Z`
- Boundary: bridge mapping only。未移除 bridge、未切換 consumer、未啟動 dual-write 或 canary。

## Direct answer

A6 已有可機器檢查的 bridge inventory 與 removal tests；C0 Phase 2 可把它轉成 cutover map，但不能把 source-declared active bridge 視為 live invocation proof，也不能以 removal-test presence 視為 removal readiness。C1 前的核心 gate 是：每個 `CARD_C_CONTROL_CUTOVER` bridge 都要證明 ledger/native consumer parity、legacy read/write stop condition、rollback path、與 no truth-authority inversion。

## Bridge cutover map

| Bridge group | A6 status | Target stage | C0 cutover gate |
|---|---|---|---|
| `history_compatibility_projection` | `ACTIVE_BRIDGE` | `CARD_C_CONTROL_CUTOVER` | Ledger-backed consumers must match legacy projection; projection remains derived until all consumers stop using legacy JSONL as input. |
| `fog_map_run_history_reader` | `ACTIVE_BRIDGE` | `CARD_C_CONTROL_CUTOVER` | Fog Map must read first-party ledger/projection API with same status semantics; verifier must pass without run_history input. |
| `campaign_progress_run_history_reader` | `ACTIVE_BRIDGE` | `CARD_C_CONTROL_CUTOVER` | Progress projection parity and missing-history fail-closed behavior required. |
| `weekend_training_run_history_reader` | `ACTIVE_BRIDGE` | `CARD_C_CONTROL_CUTOVER` | Weekend lifecycle summary must consume ledger-backed compatibility output or be explicitly out of C1 scope. |
| `legacy_run_history_appenders` | `ACTIVE_LEGACY_WRITER` | `CARD_C_CONTROL_CUTOVER` | New runs must persist intent/attempt/receipt first; legacy appenders must be disabled or converted to derived projection after parity. |
| Historical migration bridges | `PRESERVE_FOR_HISTORICAL_REPLAY` | `POST_A6_ARCHIVE_RETIREMENT` | Preserve until historical migration corpus no longer needs legacy intake. Not a C1 blocker unless used for new-run truth. |
| Recovery/backfill bridges | `QUARANTINED_FROM_NORMAL_RUNS` / `ACTIVE_SUPPORT_BRIDGE` | `POST_A6_RECOVERY_TOOLING` | Keep quarantined; removal only after recovery tooling is retired or documented as archival. |
| Liquidity/combo readers/writers | `ACTIVE_BRIDGE` / `ACTIVE_LEGACY_WRITER` | `POST_A6_LEGACY_REPLAY_RETIREMENT` | Not first C1 cutover unless live consumer evidence shows they block new-run truth; must not be silently broken. |

## Live activity status

- Source-declared active: proven by A6 inventory.
- Live invocation: not proven for all bridges under this Phase 2 evidence-only scope.
- Safe removal: not proven; each bridge still requires bridge-specific consumer parity and rollback evidence.

## Claim ledger

### Claim C0P2-A6-001

```yaml
claim_id: C0P2-A6-001
claim: A6 bridge inventory defines 13 rows with required owner, direction, authority, read/write mode, removal condition, removal test, target stage, and status, and validator rejects truth-authority inversion.
classification: OBSERVED_A6_INVENTORY_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/a6_closure.py
source_range_or_section: lines 30-60,98-287
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: treating legacy run history as new-run truth authority.
implication: C0 may use A6 inventory as cutover map input, but not as permission to remove bridges.
open_question: bridge-by-bridge live invocation frequency and consumer parity remain unmeasured.
owner: A6 closure owner / future C1 cutover owner
```

### Claim C0P2-A6-002

```yaml
claim_id: C0P2-A6-002
claim: Bridge-specific removal tests currently assert source surface presence/marker mapping; they do not prove consumer parity or safe removal.
classification: OBSERVED_TEST_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: tests/test_research_spine_a6_bridge_removals.py
source_range_or_section: lines 1-64
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: using removal-test existence as removal readiness.
implication: C1 cutover must add runtime/parity evidence before deleting or disabling any bridge.
open_question: which bridges are actually exercised by live daily/fog/weekend flows.
owner: A6 test owner / future cutover reviewer
```

### Claim C0P2-A6-003

```yaml
claim_id: C0P2-A6-003
claim: A6 closure receipt reports row_count=13 and zero bridge inventory errors, with source_scan over app/research and scripts surfaces.
classification: COMMITTED_EVIDENCE_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-A6-DEPRECATION-REBUILD-AND-BRIDGE-REMOVAL-GATES/closure_receipt.json
source_range_or_section: lines 14-72
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: claiming A6 inventory is incomplete at source-metadata level.
implication: The remaining C0/C1 gap is not metadata existence; it is live activity, parity, and cutover safety.
open_question: no fresh A6 closure verifier was run in this candidate due evidence-only/no-venv boundary.
owner: A6 closure evidence owner
```

### Claim C0P2-A6-004

```yaml
claim_id: C0P2-A6-004
claim: A6 source decision explicitly rejected absorbing Card B/C control cutover, production/scheduler mutation, and ranking/backtest semantics into A6.
classification: GOVERNANCE_BOUNDARY_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-A6-DEPRECATION-REBUILD-AND-BRIDGE-REMOVAL-GATES/gap_matrix.json
source_range_or_section: lines 1-16
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: reinterpreting A6 as already having performed C control cutover.
implication: C0 Phase 2 must design gates and blockers, not claim A6 already completed them.
open_question: C1 implementation scope remains future admission.
owner: Mainline / future C1 owner
```
