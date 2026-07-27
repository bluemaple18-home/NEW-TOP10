---
card_id: REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01
status: GO_FOR_IMPLEMENTATION_CARD
evidence_kind: repair_1_targeted_architecture_review
original_candidate_sha: 26d8471d15572f216095122f2462df79bc96edc1
original_review_sha: 3102e1385760227e53ef0d2eb37b918e17418d90
repair_candidate_sha: f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171
repair_candidate_parent_sha: 5ffc0a33874fe742ba7ffa2170ad6236612817e4
---

# REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01 Repair-1 targeted re-review

## Verdict

`GO_FOR_IMPLEMENTATION_CARD`

Repair-1 已關閉固定 findings `FRTA-P1-01`、`FRTA-P1-02`、
`FRTA-P1-03`，且獨立 direct-regression probe 未發現 P0/P1。此 verdict只授權
主線接受 architecture並建立 successor Implementation卡；不等於 runtime、
merge、deploy或 production acceptance。

## Fixed boundary與preflight

```text
reviewer_identity: reused / unique
reviewer_thread: 019fa448-4ffe-7473-af1a-7cc1f417bdd7
worktree: isolated / registered / detached
review_starting_head: 3102e1385760227e53ef0d2eb37b918e17418d90
repair_card_commit: 5ffc0a33874fe742ba7ffa2170ad6236612817e4
repair_candidate: f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171
repair_candidate_parent: 5ffc0a33874fe742ba7ffa2170ad6236612817e4
original_review_is_parent_ancestor: PASS
starting_worktree_clean: PASS
unrelated_dirty_paths: []
git_metadata: PASS
python: uv-created temporary .venv / CPython 3.12.12
zoneinfo: PASS
sha256: PASS
network_needed_for_review_logic: NO
live_runtime_needed: NO
production_acceptance: NOT_RUN
```

Repair parent只新增 Repair card；parent→candidate只改：

```text
docs/architecture/fog_runtime_receipt_v3.schema.json
docs/architecture/fog_runtime_time_authority_v1.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/phase0-red.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/repair.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/verify_contract.py
docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_REPAIR-1_contract_closure.md
```

未修改 runtime、tests、config、plist、model、ranking、baseline或 production
artifact。

## Fixed findings disposition

| Finding | Disposition | Independent evidence |
|---|---|---|
| `FRTA-P1-01` | `CLOSED` | civil run、artifact run、daily source與regime source四種日期分離；合法休市日與三個 hostile source/identity cases皆符合固定 outcome |
| `FRTA-P1-02` | `CLOSED` | successor base固定為主線接受後 architecture SHA；`acd835df…`維持 rejected non-ancestor；clean-room matrix、必要 modules/tests與四個 regression IDs完整 |
| `FRTA-P1-03` | `CLOSED` | 單一 closed JSON Schema列出完整 keys/types/required/nullability、canonical fixture與 v2 fail-closed mapping；全層 hostile mutations通過 |

Targeted re-review沒有新增 finding ID或一般建議。

## FRTA-P1-01：日期語意分離

Architecture 現在分開定義：

- `market_run_date`：aware UTC run context投影的 Taipei civil date；
- `artifact_run_date`：canonical artifact path/payload run identity；
- `daily_source_date`：canonical daily source lineage，可早於 run date；
- `source_trade_date`：canonical regime-history最近適用交易日。

獨立 probe固定重算：

| Case | Result |
|---|---|
| run/artifact=`2026-08-08`、daily source=`2026-08-07` | `ACCEPT` |
| canonical source=`2026-08-07`、claim=`2026-08-06` | `DAILY_SOURCE_DATE_MISMATCH` |
| daily source=`2026-08-09` | `FUTURE_DAILY_SOURCE_DATE` |
| artifact run=`2026-08-07` | `ARTIFACT_IDENTITY_DRIFT` |

Verifier contract要求直接讀 canonical artifacts重算，沒有 receipt claim補值路徑。

Disposition：`FRTA-P1-01 CLOSED`。

## FRTA-P1-02：successor lineage與clean-room rebuild

獨立 ancestry結果：

```text
git merge-base --is-ancestor acd835df… f9cfbab…
exit=1
```

Candidate 明定：

- rejected `acd835df…` 不得 merge、cherry-pick、copy patch或作 worktree base；
- 唯一合法 base是本 architecture由主線接受後的完整 SHA；
- processed-ID、source/baseline、receipt v3與time lineage均須 clean-room
  red→green；
- I1–I4納入 fixed finding要求的 authority/recovery/verifier modules及直接 tests；
- I5再次鎖定 successor base、四個 `FRTA-REG-*` IDs與 protected hashes。

Reviewer probe確認六個必要 modules/tests及四個 regression IDs均存在於 normative
architecture，且 keep/reimplement/reject matrix不採信 rejected stored PASS。

Disposition：`FRTA-P1-02 CLOSED`。

## FRTA-P1-03：receipt v3 exact-schema trust boundary

Normative authority：

`docs/architecture/fog_runtime_receipt_v3.schema.json`

Reviewer未採信 Executor verifier，另以
`repair1_targeted_probe.py`逐層解析 local refs及 fixture：

| Check | Result |
|---|---|
| instance object layers | 9 |
| closed object layers | 9/9 |
| unknown-field mutations rejected | 9/9 |
| missing-required mutations rejected | 46/46 |
| wrong-type mutations rejected | 46/46 |
| `required == properties`、無 duplicate | PASS |
| 唯一 nullable location | `$defs.topic_run.properties.decision` |
| complete fixture | PASS |
| topic lineage canonical hash | PASS |
| invalid calendar/UTC/non-Z/path traversal | 4/4 rejected |
| v2 relabel prohibited | PASS |
| missing v2 authority fails closed/archive-only | PASS |

Schema綁定 queue owner、runner identity、research contract、exact regime、
state transition、topic lineage與 production impact。Architecture另要求 verifier
strict parse timestamps、重算 date/hash/source/exact regime及使用自有 clock。

Disposition：`FRTA-P1-03 CLOSED`。

## Direct regression verification

Reviewer evidence：

- `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/repair1_targeted_probe.py`
- `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/repair1_targeted_results.json`

結果：

| Axis | Result |
|---|---|
| policy hash | `67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357`；與 fixture一致 |
| exact ages | `-5` accept、`-5.001` reject、`900` accept、`900.001` reject |
| host drift | UTC／Taipei／Los Angeles均投影 `2026-07-28` |
| DST fold | folds `[0,1]`且 UTC round-trip |
| Executor verifier control | PASS，但不作唯一 GO依據 |
| JSON syntax／probe compile | PASS |
| candidate `git diff --check` | PASS |

原 Review 的8-case time matrix與 receipt non-authority contract未被本 Repair弱化。

## Spec與Standards axes

- Spec axis：`PASS`。三個固定 P1均有 normative contract、machine-readable
  authority或 fixed regression ledger。
- Standards axis：`PASS`。candidate維持 architecture-only allowlist、closed
  schema、deterministic probes、safe-stopped migration／rollback與 production
  boundary。

## Acceptance snapshot

```text
status: GO_FOR_IMPLEMENTATION_CARD
root_question: Repair-1 是否關閉 FRTA-P1-01/02/03 且不引入直接 regression
evidence: independent targeted probe、schema hostile matrix、ancestry/allowlist/diff gates
acceptance_mapping: FRTA-P1-01 CLOSED；FRTA-P1-02 CLOSED；FRTA-P1-03 CLOSED
missing_evidence: successor implementation candidate、runtime tests、live acceptance
remaining_risk: architecture尚未實作；runtime與production維持未接受
next_step: 主線可接受 fixed architecture SHA並建立 successor Implementation卡
limits: 不授權 merge/push/deploy、LaunchAgent操作、queue/circuit變更或 production acceptance
```
