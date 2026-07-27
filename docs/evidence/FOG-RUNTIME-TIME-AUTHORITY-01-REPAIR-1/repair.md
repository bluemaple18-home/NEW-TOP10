---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1
evidence_kind: architecture_repair
reviewed_candidate_sha: 26d8471d15572f216095122f2462df79bc96edc1
review_evidence_sha: 3102e1385760227e53ef0d2eb37b918e17418d90
status: READY_FOR_TARGETED_REVIEW
---

# FOG-RUNTIME-TIME-AUTHORITY-01 Repair-1 evidence

## Fixed boundary

```text
starting_head: 5ffc0a33874fe742ba7ffa2170ad6236612817e4
starting_head_parent: 3102e1385760227e53ef0d2eb37b918e17418d90
reviewed_candidate: 26d8471d15572f216095122f2462df79bc96edc1
review_evidence: 3102e1385760227e53ef0d2eb37b918e17418d90
worktree: isolated / detached
unrelated_dirty_paths: []
runtime_or_production_mutation: NONE
merge_push_deploy: NOT_RUN
implementation_authorization: DENIED
```

Phase 0 RED先保存於
`docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/phase0-red.md`，之後才修改
architecture。

## Finding before → after

| Finding | Before | After |
|---|---|---|
| `FRTA-P1-01` | `daily source_date == market_run_date`，合法休市日被拒 | 明分 `market_run_date`、`artifact_run_date`、`daily_source_date`、`source_trade_date`；固定休市日 ACCEPT、wrong／future source與 artifact drift fail-closed matrix |
| `FRTA-P1-02` | successor base、rejected-code boundary與前鏈 safety allowlist不完整 | 固定 Review GO後 accepted architecture commit為唯一 base；`acd835df…` 只作 non-ancestor evidence；新增 keep／reimplement／reject matrix、clean-room policy、I1–I5 modules/tests與四個 regression IDs |
| `FRTA-P1-03` | receipt v3只有 minimum fields，沒有 exact manifest／fixture／mapping | 新增唯一 JSON Schema 2020-12 closed authority、complete fixture、types／required／nullability、v2 mapping及 deterministic reject規則 |

## Successor regression mapping

```text
FRTA-REG-RRV-P1-01-PROCESSED-ID
  scripts/verify_processed_id_authority.py
  scripts/verify_fog_closed_regime_recovery.py
  tests/test_fog_closed_regime_runtime.py

FRTA-REG-RRV-P1-03-SOURCE-BASELINE
  scripts/fog_authority_contracts.py
  scripts/verify_fog_closed_regime_recovery.py
  tests/test_fog_closed_regime_runtime.py

FRTA-REG-RECEIPT-V3-EXACT
  scripts/verify_closed_regime_runtime.py
  scripts/verify_daily_research_quota.py
  tests/test_fog_closed_regime_runtime.py
  tests/test_daily_research_quota_verifier.py

FRTA-REG-TIME-DATE-LINEAGE
  scripts/fog_runtime_time_authority.py
  producer/verifier adapters
  tests/test_fog_runtime_time_authority.py
  tests/test_fog_runtime_time_wiring.sh
```

上述都是 successor Implementation卡的 red→green contract，不代表本 Repair執行或
通過 runtime tests。

## Receipt v3 manifest與hostile mutations

- Root及所有 nested object：closed，`additionalProperties=false`。
- 所有 object keys：required；required list無重複且皆存在於 properties。
- 唯一 nullable field：`topic_run_lineage[].decision`。
- Canonical fixture：schema `examples[0]`，完整包含 queue／runner／contract／
  exact-regime／transition／topic lineage／production impact。
- Fixture topic lineage canonical JSON SHA-256：
  `849f37e96efa858ab3032126daf7ed6a7d76048729055063b6c448b9e167c385`。

| Mutation | Expected |
|---|---|
| top-level unknown field | `RECEIPT_SCHEMA_REJECT` |
| missing `queue_owner` | `RECEIPT_SCHEMA_REJECT` |
| numeric `runner_identity` | `RECEIPT_SCHEMA_REJECT` |
| null `production_impact` | `RECEIPT_SCHEMA_REJECT` |
| nested unknown time field | `RECEIPT_SCHEMA_REJECT` |
| wrong canonical `daily_source_date` | `DAILY_SOURCE_DATE_MISMATCH` |
| future `daily_source_date` | `FUTURE_DAILY_SOURCE_DATE` |
| drifted `artifact_run_date` | `ARTIFACT_IDENTITY_DRIFT` |

`x-v2-to-v3-mapping` 明列可比較、必須重算／重查 authority及無法補造而 fail
closed三類。缺 run-context instant、source lineage、contract、artifact或 hash
不得升級，只能 archive v2。

## Mechanical verification

Exact changed-file allowlist：

```text
docs/architecture/fog_runtime_receipt_v3.schema.json
docs/architecture/fog_runtime_time_authority_v1.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/phase0-red.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/repair.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/verify_contract.py
docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_REPAIR-1_contract_closure.md
```

可重現指令：

```bash
python3 -m json.tool \
  docs/architecture/fog_runtime_receipt_v3.schema.json >/dev/null
.venv/bin/python \
  docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/verify_contract.py
rg -n \
  'market_run_date|artifact_run_date|daily_source_date|source_trade_date' \
  docs/architecture/fog_runtime_time_authority_v1.md
rg -n \
  'additionalProperties|required|queue_owner|runner_identity|state_transition|production_impact' \
  docs/architecture/fog_runtime_receipt_v3.schema.json
git diff --check
```

目前 contract verifier結果：

```text
schema_object_contract=true
canonical_fixture=true
unknown_top_level_rejected=true
missing_queue_owner_rejected=true
runner_identity_type_rejected=true
null_production_impact_rejected=true
unknown_nested_time_rejected=true
v2_mapping_present=true
```

## Targeted re-review boundary

本 evidence只交回原 Reviewer targeted re-review `FRTA-P1-01/02/03`與上述直接
regressions。狀態是 `READY_FOR_TARGETED_REVIEW`，不是自行 GO，也不授權
Implementation、runtime、live acceptance、merge、push或 deploy。
