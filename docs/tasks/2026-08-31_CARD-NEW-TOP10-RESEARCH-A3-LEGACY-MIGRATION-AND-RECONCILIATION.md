---
id: CARD-NEW-TOP10-RESEARCH-A3-LEGACY-MIGRATION-AND-RECONCILIATION
status: local_candidate_review_pending
type: implementation
issue: 5
depends_on: [3, 4]
---

# CARD-NEW-TOP10-RESEARCH-A3-LEGACY-MIGRATION-AND-RECONCILIATION

日期：2026-08-31

## 1. Root question

能否在不猜測 lineage、不改寫 A1/A2 immutable truth、也不建立 ongoing backfill 或第二套 authority 的前提下，把既有 legacy research artifacts 與 `run_history.json/jsonl` 一次性轉成 immutable migration manifest，讓每個來源 artifact 與 row 都有可驗證 disposition，並能解釋 old/new run、observation 與 artifact count 的差額？

## 2. Owner admission 與 scope lock

- Owner 已明示 admission A3；本卡可進 planning 與其後的 bounded implementation，但不包含 push、merge 或關閉 Issue #5。
- 依賴 #3 A1 與 #4 A2 已完成 canonical mainline acceptance。
- Issue #5 為本卡 executable scope：legacy inventory、deterministic mapping、inferred mapping 的 explicit confidence/reason、one-to-many／unresolved `combo_id`、old/new count reconciliation、migration quality report，以及 ambiguous lineage／sealed metadata 的 fail-closed eligibility。
- `app/research/legacy_migration.py`、`app/research/contracts.py`、`app/research/observation_ingest.py`、`app/research/history_compatibility_projection.py` 與 `tests/test_research_legacy_migration.py` 是既有 seam；只能最小延伸，不重建 subsystem。
- A4–A6 維持 `BLOCKED / NOT_STARTED`。A3 acceptance 不自動 admission A4–A6。
- 不碰 `.work/current`，不修改 scheduler、provider、features、ranking、publish、production、runtime authority 或 backtest math。

## 3. Known facts 與 measured gap

### 3.1 已存在、可直接沿用

1. `discover_legacy_sources()` 已可發現 `run_history.jsonl`、`run_history.json` 與 strategy matrix artifacts。
2. `build_migration()` 已把 source bytes、record mapping 與 manifest 寫入 content-addressed corpus，並以 canonical content 產生 identity。
3. `validate_migration_manifest_v2()` 與 `validate_migrated_record()` 已提供 exact-field validation、count reconciliation、canonical path/hash 與 identity 檢查。
4. `ingest_corpus()` 已驗證 manifest/mapping hash、拒絕 identity collision，並將 DuckDB 保持為可重建 projection。
5. 既有 tests 已覆蓋 idempotency、tamper rejection、semantic duplicate/conflict、incremental manifest attribution，以及 legacy evidence 不得升格為 adaptive eligibility。
6. A1 canonical parameter/trial/bundle identity 與 A2 intent/attempt/receipt 是新 evidence authority；legacy input 永遠不能反向覆蓋它們。

### 3.2 已量測缺口

1. Issue #5 要求五種 migration disposition：`MIGRATED_EXACT`、`MIGRATED_INFERRED`、`LEGACY_INCOMPLETE`、`LEGACY_UNRESOLVED`、`EXCLUDED_NON_RESEARCH`；現有 migrated record 沒有獨立 disposition 欄位。
2. 現有 `record_kind` 表達 payload 形狀，`preliminary_classification` 表達下游 eligibility；兩者都不是 migration disposition，不能拿來假裝五種 disposition 已完成。
3. 非 mapping row 目前只進入 aggregate `excluded` count，沒有逐 row locator、reason、evidence 與 disposition，無法證明「每個 legacy row」皆有處置。
4. inferred mapping 尚無 pinned inference policy、confidence、reason 與 evidence refs；`combo_id` 缺少一對多與 unresolved 的明確 mapping envelope。
5. manifest 只有 `seen = mapped + excluded` 與 eligibility classification counts；沒有 disposition counts、mapping-output cardinality、old/new run/observation/artifact reconciliation 或 typed gap report。
6. compatibility projection 可讀 legacy rows，但不得被用作 migration truth 或用最新列選擇邏輯倒推原始 lineage。

## 4. Minimum sufficient decision

### why_not_less

只替既有 `record_kind` 或 `preliminary_classification` 換名稱，仍無法同時回答「這列怎麼遷移」與「可否進入哪種研究用途」；只補 aggregate counts 也無法定位被排除、推斷或 unresolved 的個別 row。因此最小充分變更必須新增獨立 disposition envelope、逐 row evidence，以及 deterministic reconciliation。

### why_not_more

現有 CAS、manifest、validator、ingest 與 projection seam 已足以承載一次性 migration。A3 不需要新 DB、ledger、registry、FSM、runtime、scheduler、daily backfill、DVC/MLflow/OpenLineage service 或 W3C PROV/RDF subsystem。

### do_not_absorb

- 不吸收 optimizer、priority、queue、ranking、publish、production promotion 或模型訓練能力。
- 不建立第二套 canonical identity、eligibility authority、artifact registry、event store 或 lifecycle。
- 不把 legacy `combo_id`、path、mtime、row order、latest-wins projection 或相似參數當作 canonical lineage。
- 不追求 100% mapping coverage；缺證據即保留 incomplete/unresolved。
- 不建立 ongoing daily migration/backfill path。

## 5. Assumptions

- **AS-A3-001**：來源 bytes hash 與 row locator 足以穩定識別被檢視的 legacy evidence，但不單獨證明 canonical lineage。 `traces_to: FR-A3-001, FR-A3-004`
- **AS-A3-002**：A1 parameter/trial identity 與 A2 receipts 是唯一可接受的新 lineage anchor；若不存在，不得由 legacy 欄位猜出。 `traces_to: FR-A3-003, SC-A3-002`
- **AS-A3-003**：同一 legacy row 可對應零、一或多個 candidate `combo_id`；多個 candidate 不等於多個已證明 canonical mappings。 `traces_to: FR-A3-006`
- **AS-A3-004**：DuckDB 與 history compatibility output 都是 projection；刪除後應可只靠 immutable corpus、manifest 與 versioned policy 重建。 `traces_to: FR-A3-010`

## 6. Contract decisions

### 6.1 三個互不替代的軸

| 軸 | 回答問題 | 例子 | 禁止混用 |
|---|---|---|---|
| `record_kind` | 原始 payload 是什麼形狀／粒度？ | `PARAMETER_RESULT`、`TOPIC_SUMMARY`、`UNSUPPORTED_COORDINATE`、`UNRESOLVED_RECORD` | 不代表 migration 成敗或 eligibility |
| `migration_disposition` | 這個 artifact／row 如何被 A3 處置？ | 五種 Issue #5 disposition | 不代表可進 adaptive／sealed learning |
| `preliminary_classification` | 這份 migrated evidence 可進哪種下游用途？ | `LEGACY_DIAGNOSTIC_ONLY`、`SEALED_VALIDATION_ONLY`、`TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE`、`UNSUPPORTED_NOT_AN_OBSERVATION`、`INVALID_LINEAGE` | 不得回推 exact/inferred mapping |

若 `EXCLUDED_NON_RESEARCH` 不產生研究 observation，仍須產生 immutable disposition record；eligibility 軸使用明確的 non-observation／not-applicable 值，不得靠缺欄位表示。最終 controlled vocabulary 必須由 validator 固定，且不得讓 excluded/unresolved evidence 成為 positive 或 negative observation。

### 6.2 五種 migration disposition

| Disposition | 必要條件 | 禁止宣稱 |
|---|---|---|
| `MIGRATED_EXACT` | source artifact、row locator、所有 required identity/value 與 canonical target 均有直接可驗證 evidence；mapping 無推斷步驟 | 不能只因欄位看起來相同或 hash 可重算就宣稱 lineage exact |
| `MIGRATED_INFERRED` | 依 versioned deterministic policy 得到一或多個 candidate mapping，且保存 confidence、reason 與 evidence refs | 不能升格為 exact；不能單憑 inferred mapping取得 adaptive eligibility |
| `LEGACY_INCOMPLETE` | 可確認為 research evidence，但缺少完成 canonical mapping 所需欄位／artifact／terminal facts | 不能補零、套 default 或由鄰近 row 猜值 |
| `LEGACY_UNRESOLVED` | 有衝突、歧義、多 candidate 無法裁決，或 evidence 無法建立 deterministic mapping | 不能用 latest-wins、row order、path 或 arbitrary winner 解決 |
| `EXCLUDED_NON_RESEARCH` | explicit evidence 證明該 artifact／row 不屬於 research observation corpus | 不能把 parse error、缺欄位或 ambiguous lineage 偷渡成 non-research |

### 6.3 每個 disposition record 的最小 evidence envelope

每個 discovered artifact 與 row 都必須有 immutable record，至少包含：

- `source_artifact_id`、`source_type`、`record_locator`；artifact-level inventory record 使用明確 artifact locator。
- `record_kind` 與 `migration_disposition`。
- `disposition_policy_version`、`inference_policy_version`（不適用時為 controlled `NOT_APPLICABLE`）。
- `confidence`：controlled vocabulary；`MIGRATED_EXACT` 必須為 `EXACT`，inferred 必須是非 `EXACT`，incomplete/unresolved/excluded 不得偽裝推斷信心。
- 非空 `reason_codes` 與 immutable `evidence_refs`；refs 至少能定位 source CAS 與 row locator，若引用 A1/A2 identity 亦須是 immutable ref。
- `combo_mapping`：mapping status、零或多個 candidate `combo_id`、每個 candidate 的 evidence/reason；不得用空字串表達 unknown。
- canonical content identity；同 identity 不同 payload 必須 collision fail loudly。

### 6.4 `combo_id` cardinality 與 unresolved

- exact/inferred mapping 都須明列 cardinality：`ZERO`、`ONE`、`ONE_TO_MANY`；candidate list canonical-sort、去重並納入 identity。
- `ONE_TO_MANY` 必須保留每個 edge 的 evidence，不得只保留一個 aggregate reason。
- 多 candidate 且無 governing evidence 可裁決時，row disposition 必須為 `LEGACY_UNRESOLVED`；不能任選 winner。
- legacy `combo_id` 只能是 source evidence。只有通過 A1 canonical identity validator 的 target 才能成為 canonical mapping target。

### 6.5 Reconciliation contract

每個 source 與整體 quality report 都須可重算下列關係：

```text
source_artifacts_seen = sum(source_artifact_disposition_counts)
rows_seen = MIGRATED_EXACT + MIGRATED_INFERRED + LEGACY_INCOMPLETE
          + LEGACY_UNRESOLVED + EXCLUDED_NON_RESEARCH
mapping_edges_emitted = sum(each row's canonical candidate edges)
new_migrated_records + excluded_disposition_records = rows_seen
```

另須分別報告 legacy run rows、legacy observation-like rows、source artifacts、new migrated records、mapping edges 與 projected observations；任何差額都以 typed gap（例如 excluded、incomplete、unresolved、deduplicated、one-to-many expansion、not-observation）解釋。`old_count != new_count` 本身不是錯誤；無法由 disposition records 重算的差額才 fail closed。不得為達成相等而複製、刪除或強配 row。

### 6.6 Immutability、idempotency 與 collision

- 相同 source bytes、locator、versioned policies 與 mapping evidence 必須產生相同 record、mapping 與 manifest IDs。
- 同一 target path/identity 已存在相同 bytes 時為 idempotent success；不同 bytes 必須 loud collision，不得 overwrite。
- manifest 必須綁定 disposition counts、quality/reconciliation report hash 與所有 mapping record hashes。
- ingest 必須先完整驗 hash、schema、identity、count 與 refs，再以 transaction 更新 rebuildable projection；驗證失敗不得部分 ingest。
- semantic duplicate 可 deweight；conflict 必須 quarantine/no winner。兩者不得改寫原始 migration disposition evidence。

## 7. Functional requirements

- **FR-A3-001**：inventory 每個 discovered source artifact 與 row，保存 CAS hash、source type、locator 與 parser evidence。 `traces_to: Issue#5, SC-A3-001`
- **FR-A3-002**：為每個 artifact／row產生且只產生一個五類 migration disposition。 `traces_to: Issue#5, SC-A3-001`
- **FR-A3-003**：保持 `record_kind`、`migration_disposition`、`preliminary_classification` 三軸獨立並由 validator 拒絕非法組合。 `traces_to: SC-A3-002`
- **FR-A3-004**：每個 disposition 保存 explicit confidence、reason codes、policy versions 與 immutable evidence refs。 `traces_to: SC-A3-003`
- **FR-A3-005**：只有 direct evidence 完整時可 `MIGRATED_EXACT`；inferred/incomplete/unresolved 一律不得猜 lineage 或提升 eligibility。 `traces_to: SC-A3-002, SC-A3-003`
- **FR-A3-006**：支援 `combo_id` zero/one/one-to-many candidate edges並保存 unresolved，不任選 winner。 `traces_to: SC-A3-004`
- **FR-A3-007**：source 與 corpus reconciliation 可重算 artifacts、rows、dispositions、mapping edges、new records與observations差額。 `traces_to: SC-A3-005`
- **FR-A3-008**：migration quality report 報告 coverage 與 typed gaps，不以 100% match 為成功條件。 `traces_to: SC-A3-005`
- **FR-A3-009**：manifest/mapping/quality evidence immutable、idempotent、content-addressed、collision-safe。 `traces_to: SC-A3-006`
- **FR-A3-010**：DuckDB 與 history compatibility output 可刪除重建，且不得成為 migration authority。 `traces_to: SC-A3-007`
- **FR-A3-011**：A1/A2 evidence 不可被 legacy input覆寫；invalid/tampered/ambiguous evidence fail closed且不部分 ingest。 `traces_to: SC-A3-002, SC-A3-006`

## 8. Success criteria

- **SC-A3-001**：mixed source fixture 的 artifact 與每列都有唯一 disposition record，disposition counts總和等於 discovery counts。 `traces_to: FR-A3-001, FR-A3-002`
- **SC-A3-002**：缺 lineage、sealed metadata 或 canonical target evidence 的 rows 不能變成 exact 或 eligible observations。 `traces_to: FR-A3-003, FR-A3-005, FR-A3-011`
- **SC-A3-003**：inferred fixture 固定產生相同 confidence/reason/evidence refs；缺任一欄位 validator fail。 `traces_to: FR-A3-004, FR-A3-005`
- **SC-A3-004**：one-to-many fixture 保存全部 canonical-sorted edges；ambiguous fixture 保持 unresolved 且沒有 winner。 `traces_to: FR-A3-006`
- **SC-A3-005**：old/new counts 與每個 typed gap 可由 immutable disposition records 完整重算。 `traces_to: FR-A3-007, FR-A3-008`
- **SC-A3-006**：重跑得到相同 IDs/bytes；tamper、identity collision、count/ref mismatch 都在 ingest 前 fail loudly。 `traces_to: FR-A3-009, FR-A3-011`
- **SC-A3-007**：刪除 DuckDB 後只用 immutable corpus/manifest/policies重建，snapshot與 migration attribution一致。 `traces_to: FR-A3-010`
- **SC-A3-008**：受影響 tests、trace preflight、完整 Research Spine regression與 `git diff --check` 通過；獨立 Review 無未解 P0/P1。

## 9. Vertical slices

### Slice A3.1 — Characterization 與 RED contract tests

- 先鎖定五類 disposition、三軸獨立、逐 row excluded evidence、confidence/reason/ref 與 count equations。
- RED：現有 aggregate-only excluded、缺 disposition、非法軸組合應失敗。
- checkpoint：只允許 contract/test fixtures；若必須改 source discovery semantics，先停下重審 scope。
- `traces_to: FR-A3-001..FR-A3-005, SC-A3-001..SC-A3-003`

### Slice A3.2 — Minimal builder mapping

- 在既有 builder seam 產生 disposition envelope；exact/inferred/incomplete/unresolved/excluded 均有 deterministic record。
- RED：同資料改 path 不改 semantic mapping；同 locator/policy 的不同 payload collision；缺 evidence 不得 exact。
- GREEN：最小 builder/validator變更使 contract tests 通過，不改 eligibility owner。
- checkpoint：五類可由 fixture逐一證明，無 heuristic guessing。
- `traces_to: FR-A3-002..FR-A3-006, SC-A3-001..SC-A3-004`

### Slice A3.3 — Cardinality 與 reconciliation quality report

- 增加 zero/one/one-to-many edge、typed gaps、artifact/row/run/observation counts與 immutable quality report。
- RED：duplicate candidate、unexplained delta、arbitrary winner、count不守恆皆失敗。
- GREEN：所有 counts可由 disposition records重算，差額被 typed gap完整解釋。
- checkpoint：`old != new` 被接受，但 unexplained delta 必須是零。
- `traces_to: FR-A3-006..FR-A3-009, SC-A3-004..SC-A3-006`

### Slice A3.4 — Ingest/rebuild/compatibility boundary

- 讓既有 ingest 驗證新 manifest/mapping/report；DuckDB只保存 projection與完整 attribution。
- history compatibility projection只讀已驗證 evidence，不倒推 migration lineage，不新增 ongoing backfill。
- RED：tamper、manifest/record/report hash mismatch、partial ingest、legacy overwrite A1/A2 都失敗。
- GREEN：重複 ingest與 clean rebuild snapshot一致，legacy history output仍為 projection。
- checkpoint：若需新 DB/ledger/authority、scheduler 或 runtime mutation，立即停止。
- `traces_to: FR-A3-009..FR-A3-011, SC-A3-006..SC-A3-007`

### Slice A3.5 — Acceptance bundle

- 執行完整 verification、產生固定 SHA candidate、獨立 review；只修 reproducible P0/P1。
- checkpoint：A3 `GO / no P0/P1` 只代表 candidate可送 mainline acceptance，不 admission A4–A6。
- `traces_to: SC-A3-008`

## 10. Likely affected files

- `app/research/contracts.py`
- `app/research/legacy_migration.py`
- `app/research/observation_ingest.py`
- `app/research/history_compatibility_projection.py`（只有 compatibility boundary 測試證明必要時）
- `tests/test_research_legacy_migration.py`
- 直接受影響的 migration/ingest/compatibility tests
- 本 task card 與必要的 backlog/frontier status

任何超出此清單的 implementation file 必須先說明 measured need；scheduler/provider/features/ranking/publish/production/backtest math 與 `.work/current` 禁止。

## 11. Blockers 與 stop conditions

遇到下列任一情況立即停止並回報 exact evidence，不建立 workaround：

1. Issue #5 與 A1/A2 canonical identity、artifact、eligibility 或 terminal boundary 產生 governing conflict。
2. 無法以 source bytes + locator + immutable refs 區分 exact、inferred、incomplete、unresolved 或 excluded。
3. exact mapping 需要 path/mtime/latest row/row proximity/default values 或其他 lineage guessing。
4. reconciliation 只能靠刪除、複製或強配 records 才能達成 count equality。
5. acceptance 要求 ongoing backfill、scheduler/provider/runtime/production mutation、backtest math變更，或新 authority/DB/ledger/registry/FSM。
6. compatibility projection 需要成為 canonical writer，或 legacy data將覆寫 A1/A2 immutable evidence。
7. 出現 reproducible P0/P1、identity collision、partial ingest、unexplained count delta或non-deterministic rebuild。
8. main advanced並造成 material conflict，或 Issue #5 remote scope改變。

## 12. Verification contract

每個 implementation slice 先跑 directly affected RED/GREEN tests；acceptance 至少執行：

```bash
.venv/bin/python -m pytest \
  tests/test_research_legacy_migration.py \
  tests/test_research_spine_contracts.py \
  tests/test_research_ledger.py \
  tests/test_research_receipt_store.py \
  tests/test_research_dataset_bundle.py \
  tests/test_autonomous_research_receipts.py \
  tests/test_research_spine_daily_cutover.py \
  tests/test_research_batch_owner.py \
  tests/test_research_eligibility_failure.py \
  tests/test_isolated_external_review_backfill.py \
  tests/test_isolated_daily_backfill.py \
  tests/test_shadow_replay_authority_reconciliation.py \
  tests/test_strategy_component_registry.py \
  tests/test_strategy_archetype_evidence_map.py -q

# Repo 目前沒有 task-card trace preflight；先做 bounded trace presence check。
# 若 implementation 前 repo 新增正式 preflight，改以正式 script 為準。
rg -n "FR-A3-|SC-A3-|AS-A3-|traces_to" \
  docs/tasks/2026-08-31_CARD-NEW-TOP10-RESEARCH-A3-LEGACY-MIGRATION-AND-RECONCILIATION.md

git diff --check
```

另外必須保存：固定 candidate SHA、remote SHA equality、exact changed files、test count、trace result、diff check、independent reviewer disposition與 remaining P0/P1。不得用狀態文案取代 command evidence。

## 13. Rollback

- implementation 前保留 A2 accepted baseline；A3 只新增 versioned migration evidence，不改寫既有 source artifacts或A1/A2 corpus。
- 回退方式是停止使用/移除 A3 新 parser-policy version與其 derived manifest/mapping/report，再由既有 immutable evidence clean rebuild；不得刪除或重寫歷史 source CAS。
- DuckDB、quality projection與compatibility output可刪除重建，不是 rollback authority。
- removal test：移除 A3 projection後，A1/A2 tests與既有 Research Spine ingest仍通過，且 legacy source bytes/hash不變。

## 14. Current status

`A3 = LOCAL_CANDIDATE / REPAIR_COMPLETE / REVIEW_PENDING`。

本卡已完成 Slice A3.1–A3.4 的 bounded implementation 與 fixed-SHA `aea377eab761e46ddc7f8afe9b3ec0f30ddd114b` Review repair。下一步只能建立新 fixed-SHA candidate 並做獨立 re-review；不得跳到 A4–A6、push、merge或 Issue closeout。

## 15. Implementation 與 Review repair receipt

- Initial implementation RED：`tests/test_research_legacy_migration.py -q` 為 `11 passed / 5 failed`，固定逐 row disposition、mapping evidence、ambiguous no-winner、axis validator 與 quality report 缺口。
- Initial fixed candidate：`aea377eab761e46ddc7f8afe9b3ec0f30ddd114b`；獨立 Review disposition=`NO-GO`，四項 remaining P1 為 legacy self-authorized exact、ingest dangling target/ref、legacy sealed eligibility 越權，以及 malformed/scalar/empty 被誤列 non-research exclusion。
- Repair hostile RED：`17 passed / 4 failed`，分別重現上述四項 P1。
- Repair boundary：exact/inferred/excluded 必須引用與 source artifact、locator、legacy combo 及 canonical A1 trial target 綁定的 immutable mapping authority；ingest 在 migration transaction write 前驗 authority、trial target與 governing A2 receipt 的 schema/path/identity/ref；sealed eligibility 只由 canonical target加 governing receipt stage/bundle evidence決定；malformed/scalar/empty research input保留 incomplete/unresolved，不能自動 excluded。
- Repair GREEN：focused migration tests=`23 passed`；card full regression family=`172 passed`；trace presence 與 `git diff --check` pass。
- Current disposition：`LOCAL_CANDIDATE / REVIEW_PENDING`。尚未產生 repair fixed SHA，尚未 re-review；不得宣稱 `GO`、accepted 或 admission A4–A6。

## 16. Review repair generation 2 receipt

- Repair generation 1 fixed candidate：`67ca4f407892807cfcdd99a43909dde88841c858`；獨立 fixed-SHA re-review 尚有兩項 P1：`RUN_HISTORY_JSON` 的 non-list collection 沒有逐 locator disposition，以及 EXACT multi-candidate no-winner record 在 ingest 被錯誤拒絕。
- Generation 2 hostile RED：focused migration tests=`23 passed / 4 failed`；三個 `history/runs/rows` non-list fixtures 與一個 EXACT ambiguous build→ingest fixture 均可重現。
- Generation 2 GREEN：non-list collection 以 collection JSON pointer 產生 `LEGACY_INCOMPLETE` parser evidence，artifact/row/quality counts守恆且不列 `EXCLUDED_NON_RESEARCH`；EXACT multi-candidate 缺 `ALL_TARGETS_PROVEN` 時保持 `LEGACY_UNRESOLVED / AMBIGUOUS_NO_WINNER`，ingest仍完整驗 authority/source/targets/refs且不選 winner。
- Verification：focused migration tests=`27 passed`；card full regression family=`176 passed`；trace presence 與 `git diff --check` pass。
- Current disposition：`LOCAL_CANDIDATE / REPAIR_GENERATION_2_COMPLETE / REVIEW_PENDING`。尚未產生 generation 2 fixed SHA 或 re-review；不得宣稱 `GO`、accepted 或 admission A4–A6。
