# 09 — A1 Admission and A2 Prerequisites

日期：2026-08-30
Execution base：`origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88`
裁決範圍：A1 admission recommendation；A2 prerequisites only
當前治理狀態：`A1–A6 BLOCKED / NOT STARTED`

## Integrator recommendation

```text
CONDITIONAL_GO_FOR_SEPARATE_A1_ADMISSION_DECISION
A1_RECOMMENDED_SCOPE = NARROW_DOMAIN_SCHEMA_AND_VALIDATOR_TIGHTENING
A2 = PREREQUISITES_ONLY / BLOCKED_BEHIND_ACCEPTED_AND_IMPLEMENTED_A1
```

本 recommendation 不自行 unpause、派工或開始 A1。Mainline/Owner 仍須以另行 card 明確接受 A1 scope、mutation boundary、tests、rollback/removal owner，才構成 admission。

## A1 admission findings

### A0-INT-ADM-001

| field | value |
|---|---|
| claim_id | `A0-INT-ADM-001` |
| subject | A1 architecture prerequisite |
| claim | Owner 已接受 `DATASET_BUNDLE_V1`、legacy `FEATURES_ARTIFACT_V1`、requested/executed resolution delta、transformation identity default與fundamentals prerequisite，故 A0 的 material identity-grain blocker 已解除。 |
| authority | Owner-accepted dataset identity-grain decision |
| scope | A1 admission recommendation input；不是 implementation |
| as_of | 2026-08-30 |
| evidence_ref | decision §§1、4、5、12 |
| evidence_hash | `44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `NOT_A_GAP` |
| owner | Owner / Mainline |
| next_action | 可進入另行 A1 admission decision；不可把本 finding 當作 A1 已啟動。 |

### A0-INT-ADM-002

| field | value |
|---|---|
| claim_id | `A0-INT-ADM-002` |
| subject | A1 measured implementation slice |
| claim | 現有 runtime只證明單檔 dataset hash；bundle manifest schema/canonicalizer/validator、per-consumer component matrix、fundamentals snapshot identity、requested/executed bundle binding與legacy bridge尚未實作。 |
| authority | Owner decision；Lane B dataset mapping |
| scope | Proposed A1 minimum sufficient slice |
| as_of | 2026-08-30 |
| evidence_ref | decision §§4、8、10、11；04 `CLAIM-DATASET-006`～`014` |
| evidence_hash | `decision=44b3f5cd173c36d98144c385ac2e399284145bfc`; `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b` |
| status | `MEASURED_GAP` |
| owner | Proposed A1 card owner |
| next_action | A1 card限於既有 TrialSpec/receipt/CAS seams 的 schema/catalog/validator tightening與受影響 tests；禁止 provider/scheduler/production/learning mutation。 |

### A0-INT-ADM-003

| field | value |
|---|---|
| claim_id | `A0-INT-ADM-003` |
| subject | reuse before new subsystem |
| claim | NEW-TOP10 已有 canonical JSON、TrialSpec/Intent/Attempt/Receipt、immutable JSON corpus、CAS、legacy migration與rebuildable DuckDB；A1 不需要第二套 lifecycle、Dataset Registry、ledger、DB或prior-art backend。 |
| authority | Lane A authority/boundary；Lane C reuse matrix；Owner decision |
| scope | A1 product-fit boundary |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-007`；03 `A0-BND-001`、`004`～`007`；06 Decision Matrix / `C-NEW-001`～`002`；decision §§3、6 |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `03=02db82892a91e6f3f95528717434104b6f365f63`; `06=f49c5279cf55010eba996579628dddb6050d64ca`; `decision=44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `NOT_A_GAP` |
| owner | Proposed A1 card owner / reviewer |
| next_action | A1 明列 `WRAP/ADAPT`、`why_not_less`、`why_not_more`、`do_not_absorb`；任何 new authority/registry 提案直接退件。 |

### A0-INT-ADM-004

| field | value |
|---|---|
| claim_id | `A0-INT-ADM-004` |
| subject | unresolved A1 technical details |
| claim | mandatory component/cardinality matrix、typed resolution reason codes、signals/events/universe entrypoint conditions與exact migration coverage仍有 UNKNOWN，但可由 A1 fail-closed contracts或後續 A3 quarantine 處理，不需要在 A0猜測。 |
| authority | Owner-accepted decision technical follow-up |
| scope | A1/A3 dependency split |
| as_of | 2026-08-30 |
| evidence_ref | decision §11 `U-DATASET-001`、`004`、`007`、`008` |
| evidence_hash | `44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `UNKNOWN` |
| owner | Proposed A1 card owner；future A3 owner for legacy coverage |
| next_action | A1未定義部分 fail closed；legacy coverage留在blocked A3，不得擴張 A1 去掃或改寫 corpus。 |

### A0-INT-ADM-005

| field | value |
|---|---|
| claim_id | `A0-INT-ADM-005` |
| subject | A1 admission disposition |
| claim | 沒有 governing-authority、identity-grain或terminal-boundary hard stop阻止提出一張 narrow A1 card；但 A1目前仍 blocked，因尚無另行 Owner/Mainline admission與mutation授權。 |
| authority | A0 integrated findings；current A0 governance boundary |
| scope | Mainline admission recommendation |
| as_of | 2026-08-30 |
| evidence_ref | 07 `A0-INT-HAZ-001`～`008`；08 hard-stop assessment；decision §8 |
| evidence_hash | `07=cce5061af67f502f88217c625a0e863a32d57c8e`; `08=f7371837a8d9d7626670f872749d8907e9f058b0`; `decision=44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `MEASURED_GAP` |
| owner | Owner / Mainline |
| next_action | 裁決為 `CONDITIONAL_GO_FOR_SEPARATE_A1_ADMISSION_DECISION`；取得明確 acceptance 前維持 A1 blocked/not started。 |

## Mandatory scope for any admitted A1 card

以下每一項都是 `A0-INT-ADM-002` 的 bounded next action，不是本輪 implementation：

1. additive `DATASET_BUNDLE_V1` manifest/schema/canonicalizer/validator；
2. `dataset_bundle_id` content address與deterministic round-trip tests；
3. legacy `dataset_hash` typed為 `FEATURES_ARTIFACT_V1`，禁止 semantic rewrite；
4. per-consumer component/cardinality/resolution matrix，unresolved fail closed；
5. transformation identity=`contract version + exact Git blob set`；
6. fundamentals snapshot identity/coverage，否則相關 consumer not executable；
7. requested/executed bundle IDs與explicit resolution delta；
8. immutable corpus rebuild、mismatch、fallback、path-independence與legacy quarantine tests；
9. removal/rollback owner與不刪 immutable historical evidence的契約。

## A2 prerequisites only

### A0-INT-A2-001

| field | value |
|---|---|
| claim_id | `A0-INT-A2-001` |
| subject | A2 dependency gate |
| claim | A2不能由A0直接 admission；它必須等待 A1另行 accepted、實作並驗證 bundle schema/identity後，才可評估 execution binding。 |
| authority | Owner-accepted decision；A0 governance boundary |
| scope | A2 prerequisite inventory only |
| as_of | 2026-08-30 |
| evidence_ref | decision §§8、9、12 |
| evidence_hash | `44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `MEASURED_GAP` |
| owner | Future A2 admission owner（未准入） |
| next_action | 維持 A2 blocked；不得派工或設計 runtime mutation。 |

### A0-INT-A2-002

| field | value |
|---|---|
| claim_id | `A0-INT-A2-002` |
| subject | requested/executed binding prerequisites |
| claim | A2需要 ExecutionIntent immutable bind requested bundle、受控 resolution point bind executed bundle、terminal receipt驗證兩側 manifests/IDs/delta/evidence refs，且 mismatch 必須 typed/fail closed。 |
| authority | Owner-accepted dataset identity-grain decision |
| scope | A2 prerequisites only |
| as_of | 2026-08-30 |
| evidence_ref | decision §§4.4、9、10 |
| evidence_hash | `44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `MEASURED_GAP` |
| owner | Future A2 card owner（未准入） |
| next_action | A1通過前只保留清單；禁止在A0/A1順帶實作A2 execution adapter。 |

### A0-INT-A2-003

| field | value |
|---|---|
| claim_id | `A0-INT-A2-003` |
| subject | terminal and rebuild prerequisites |
| claim | 現有terminal state/fail-closed boundary可重用；A2新增的dataset binding必須能由immutable corpus重建，且legacy-only attempt不能被誤判為exact bundle evidence。 |
| authority | Lane A terminal boundary；Owner decision |
| scope | A2 acceptance prerequisites only |
| as_of | 2026-08-30 |
| evidence_ref | 03 `A0-BND-002`～`007`；decision §9 |
| evidence_hash | `03=02db82892a91e6f3f95528717434104b6f365f63`; `decision=44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `NOT_A_GAP` |
| owner | Future A2 card owner（未准入） |
| next_action | 若A2未來 admission，延伸既有 receipt validator/CAS/projection seam；禁止第二套 lifecycle或ledger。 |

## Final frontier statement

- A0 evidence bundle：可交 Mainline architecture acceptance review。
- A1：`CONDITIONAL_GO` recommendation only；仍 `BLOCKED / NOT STARTED`，等待另行明示 admission。
- A2：prerequisites only；仍 `BLOCKED / NOT STARTED`，且等待 accepted + implemented A1。
- A3–A6：`BLOCKED / NOT STARTED`。
