# A0 Dataset Identity / Grain Architecture Decision

日期：2026-08-30
狀態：`PROPOSED_FOR_OWNER_ACCEPTANCE / DOCS_ONLY / NOT_IMPLEMENTED`
Execution base：NEW-TOP10 `4c6d41a44314beb3592ccdf7a9b43d8fe614ad88`
Lane B evidence：`a6ca93cbc1bbe8bf7203721db51b028730c31aa8`
Lane C evidence：`f760e45a210c27970f275e2d28b42266df38bd80`

## 1. Decision boundary

本文件只提出 Owner 可接受或退回的 architecture decision。它沒有修改 code、config、schema、runtime、DB、data、scheduler 或 production，也沒有解除 A0 的 `IDENTITY_GRAIN_AMBIGUITY_TRIGGERED` stop、admit A1，或開始 A1–A6。

提案的最小充分範圍是：定義一個可由 immutable manifest 重算的 dataset bundle identity、釐清 requested / executed binding，並固定既有 `dataset_hash` 的 legacy 意義。它不建立 Dataset Registry、authority DB、新 runtime authority、通用 lifecycle/FSM，亦不導入 OMI runtime。

## 2. Problem and pinned evidence

### 2.1 Problem

目前 `dataset_authority.dataset_hash` 與 strategy-matrix `dataset_hash` 的實際 grain，是單一 `features.parquet` 檔案 bytes 的 SHA-256；但 training 與 ranking 的 consumer-visible M4 frame 可能同時受 `features.parquet`、`events.parquet`、fundamentals cache、`config/signals.yaml`、transformation code，以及 ranking 的 universe fallback 影響。現有單檔 hash 無法唯一證明實際被 consumer 讀取的完整輸入 closure。

因此，同名 `dataset_hash` 同時被理解成「單一 artifact identity」與「有效 dataset identity」。若不先裁決，A1 會把既有值重新解釋、由 path 猜測 sibling inputs，或以執行後 filesystem scan 補洞；這三種做法都會破壞 immutable evidence 與 deterministic rebuild。

### 2.2 Evidence table

| Evidence | Pinned finding | Status |
|---|---|---|
| `a6ca93c:.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/04-dataset-and-features-lineage-map.md` | `dataset_hash` 是單一 `features.parquet` artifact hash；M4 consumer-visible frame 有額外 inputs 與 transformation identity；`CLAIM-DATASET-014` 判定 grain conflict。 | `CONFIRMED / CONFLICT` |
| 同上 `CLAIM-DATASET-007`、`008` | training 可落入 test features fallback；ranking 在 universe 缺失/空值時可使用全部 feature stocks。 | `CONFIRMED` |
| 同上 `CLAIM-DATASET-009`～`011` | requested 與 executed receipt 已有 hash/manifest seam，但 validator 只接受一個 dataset file。 | `CONFIRMED` |
| `a6ca93c:.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/05-market-evidence-and-provider-semantics-map.md` | live raw provider attempt、fallback/session 與 raw payload hash 尚未形成 durable receipt；OMI 只適合 ADAPT field vocabulary。 | `UNKNOWN / measured gap` |
| `f760e45:.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/06-ai-core-and-prior-art-matrix.md` | 現有 TrialSpec/Intent/Receipt、immutable corpus、CAS 與 rebuildable DuckDB seams 應優先 WRAP/ADAPT；拒絕第二套 authority、registry、backend 或 runtime。 | `CONFIRMED` |
| `4c6d41a:docs/RESEARCH_SPINE_BACKLOG.md` | A0 只能評估 A1 admission；DuckDB 必須可由 immutable evidence 重建，不能成為 canonical truth。 | `CONFIRMED` |
| `4c6d41a:docs/operations/CURRENT_OPERATIONAL_FRONTIER.md` | Research lane 不得做 runtime/config/schema/data/scheduler/production mutation。 | `CONFIRMED` |

現行 `research-canonical-json.v1` 與 `sha256:` helper 是可重用 seam；本提案沿用其 canonical JSON scalar/object semantics，但尚未修改或宣稱 runtime 已支援 bundle manifest。

### 2.3 Structured evidence claims

| field | `ADR-DATASET-001` |
|---|---|
| `claim_id` | `ADR-DATASET-001` |
| `subject` | legacy `dataset_hash` grain |
| `claim` | 現有 requested/executed dataset hash 的可證明 grain 是單一 `features.parquet` artifact bytes hash，不是完整 M4 consumer-visible dataset。 |
| `authority` | NEW-TOP10 pinned code mapping evidence |
| `scope` | A0 docs-only architecture input |
| `as_of` | 2026-08-30 |
| `evidence_ref` | `a6ca93c:.../04-dataset-and-features-lineage-map.md`, `CLAIM-DATASET-009`～`011` |
| `evidence_hash` | `git_blob_sha1:7c60fc73ec1e8608d28461e47d5fe7b38033346b` |
| `status` | `CONFIRMED` |
| `owner` | Owner / Mainline Integrator |
| `next_action` | 接受或退回 `FEATURES_ARTIFACT_V1` legacy 定位；不得 shadow reinterpretation。 |

| field | `ADR-DATASET-002` |
|---|---|
| `claim_id` | `ADR-DATASET-002` |
| `subject` | canonical dataset identity grain |
| `claim` | 單檔 hash 無法 deterministic bind M4 額外 inputs、transform 與 fallback semantics，形成 A1 前的 identity-grain blocker。 |
| `authority` | NEW-TOP10 pinned code mapping evidence |
| `scope` | A0 architecture stop |
| `as_of` | 2026-08-30 |
| `evidence_ref` | `a6ca93c:.../04-dataset-and-features-lineage-map.md`, `CLAIM-DATASET-006`～`008`、`014` |
| `evidence_hash` | `git_blob_sha1:7c60fc73ec1e8608d28461e47d5fe7b38033346b` |
| `status` | `CONFLICT` |
| `owner` | Owner / Mainline Integrator |
| `next_action` | 裁決本文件提出的 closure grain；接受前維持 A0 stop 與 A1 blocked。 |

| field | `ADR-DATASET-003` |
|---|---|
| `claim_id` | `ADR-DATASET-003` |
| `subject` | reuse and authority boundary |
| `claim` | 現有 immutable receipt/CAS/projection seams 可 WRAP/ADAPT；不需要新 Dataset Registry、DB、runtime authority 或 OMI backend。 |
| `authority` | NEW-TOP10 + AI Core prior-art mapping evidence |
| `scope` | A0 minimum-sufficient decision boundary |
| `as_of` | 2026-08-30 |
| `evidence_ref` | `f760e45:.../06-ai-core-and-prior-art-matrix.md`; `4c6d41a:docs/RESEARCH_SPINE_BACKLOG.md` |
| `evidence_hash` | `git_blob_sha1:f49c5279cf55010eba996579628dddb6050d64ca`; `git_blob_sha1:9e84f150e37c3b717df5a85a0e5be57b38b4439b` |
| `status` | `CONFIRMED` |
| `owner` | Owner / Mainline Integrator |
| `next_action` | 若 decision 被接受，後續 card 只收斂既有 domain seams。 |

## 3. Alternatives considered

| Alternative | Decision | Why |
|---|---|---|
| 重新定義既有 `dataset_hash` 為完整 dataset | `REJECT` | 舊 receipt 的 bytes 不會因此改變；同一值產生新語意，既有 evidence 會被錯誤升級。 |
| 以 `features.parquet` path 或目錄作 identity | `REJECT` | path 可搬移、覆寫、重用，且無法證明 sibling inputs 與 transform。 |
| 執行後掃 filesystem 推定實際 dataset | `REJECT` | 無法證明 scan 時點等於 execution 時點，也不可 deterministic rebuild。 |
| 每個 component 各自帶 hash，但不建立 closure identity | `REJECT` | receipt 無法以單一 immutable reference 比較 requested / executed closure。 |
| 新增中心 Dataset Registry / DB | `REJECT` | 沒有 measured need；會建立新 authority，且與 immutable evidence → rebuildable projection invariant 衝突。 |
| 導入 OMI/OpenLineage/MLflow/DVC backend | `REJECT` | prior art 可 ADAPT vocabulary，但 backend 不得成為 NEW-TOP10 canonical truth。 |
| content-addressed `dataset_bundle_id` over canonical manifest | `PROPOSED` | 可重算、path-independent，能封閉 consumer-visible inputs 與 transformation identity，並可沿用既有 immutable receipt seams。 |

## 4. Proposed decision

### 4.1 Canonical identity and grain

canonical dataset identity 提案為：

```text
identity type: dataset_bundle_id
identity kind: DATASET_BUNDLE_V1
grain: 一份 canonical immutable manifest 所封閉、供一個明確 consumer contract
       實際建立輸入 frame 所需的全部 consumer-visible dataset inputs、
       coverage/resolution semantics 與 transformation identity
```

`dataset_bundle_id` 是 manifest identity payload 的 content address，不是 path、目錄、registry row ID、runtime ID 或事後 inventory ID。同一 bytes 位於不同 path，且 identity-bearing semantics 相同時，必須得到同一 bundle ID；任何會改變 consumer-visible rows、columns、coverage、fallback branch 或 transform 的 component/semantics 改變，都必須得到不同 ID。

bundle 是 consumer contract scoped：training、backtest、ranking 若讀取不同 inputs 或有不同 fallback semantics，不得被迫共用同一 manifest。它們可以引用相同 component content IDs，但只有 closure 相同時才共享同一 `dataset_bundle_id`。

### 4.2 Bundle component roles

| Role | Identity-bearing requirement | Explicit semantics |
|---|---|---|
| `FEATURES_ARTIFACT` | 所有 bundle 必填；以檔案 bytes SHA-256 與 format/schema contract 定位。 | 不得只記 path；production/test fallback 必須形成不同 executed component identity。 |
| `EVENTS_ARTIFACT` | consumer contract 可能讀取時必須出現。 | 存在時記 content ID；允許缺失時也要以 declared `ABSENT_*` resolution state 表示，不能省略後猜測。 |
| `FUNDAMENTALS_SNAPSHOT` | consumer contract 可能 join 時必須出現。 | 必須封閉 snapshot content、as-of/coverage 與 missing semantics；尚無 immutable snapshot 時不得假裝可重建。 |
| `SIGNALS_CONFIG` | config 影響 frame/feature selection 時必須出現。 | 以 config bytes/content ID 和 contract version 定位，不以 filename 定位。 |
| `UNIVERSE_ARTIFACT` | ranking consumer 讀取 universe 時必須出現。 | 缺失/空值而採全部 feature stocks，是 identity-bearing resolution state。 |
| `TRANSFORMATION_IDENTITY` | 所有 bundle 必填，為 top-level closure member。 | 至少封閉 transformation contract version 與精確 source/content identity；不得只寫可移動 branch name。 |
| `CONSUMER_CONTRACT` | 所有 bundle 必填，為 top-level closure member。 | 說明 consumer/entrypoint 與讀取規則版本，防止不同 reader semantics 被同一 bundle 混用。 |

以下資訊不是 bundle component identity：locator/path、建立時間、run/thread/session ID、DuckDB row ID、receipt 儲存位置。它們可以作 receipt metadata 或 locator，但不得影響或替代 `dataset_bundle_id`。

raw provider payload/attempt lineage 目前是 measured gap。只要 consumer 沒有直接讀 raw payload，它屬於上游 provenance reference，不自動擴張為 bundle component；若未來 consumer contract 直接依賴 raw payload，才由後續 accepted card 把它納入 closure。Ranking source、model artifact、parameter spec 也維持既有獨立 authority，不塞入 dataset bundle。

### 4.3 Canonicalization and hash rule

提案沿用 `research-canonical-json.v1` 的 UTF-8 canonical JSON 規則，並新增 dataset manifest 的 deterministic preconditions：

1. identity payload 必含 `schema_version`、`canonicalization_version`、`identity_kind`、`consumer_contract`、`components`、`transformation_identity` 與 coverage/resolution semantics。
2. object keys 依 canonical JSON 規則排序；不允許 NaN/Infinity；數值正規化沿用既有 helper。
3. `components` 在 hash 前必須依 `(role, identity_kind, content_id, resolution_status)` 排序；不允許同一 single-cardinality role 重複。多值 role 必須有 stable member key 與明確 cardinality contract。
4. artifact `content_id` 為 `sha256:<64 lowercase hex>` 的檔案 bytes hash。nested manifest 亦以其 canonical payload content hash 引用。
5. `dataset_bundle_id`、locator/path、timestamps、receipt IDs、runtime IDs 與非 identity metadata 不得放入 identity payload。
6. 未解析 component、只知道 path、或需靠 scan 才能補齊時，不得發出 `dataset_bundle_id`；應 fail closed 為 unresolved / not executable。

計算式：

```text
dataset_bundle_id = "sha256:" + SHA256(
  canonical_json_bytes(dataset_bundle_identity_payload)
).hexdigest()
```

Manifest 本身必須 immutable 保存，且任何 verifier 只靠該 manifest 及它引用的 immutable component evidence，即可重算 bundle ID。A1 若採用此提案，必須先把上述規則固化為 schema/validator/test；本文件不是該實作。

### 4.4 Requested / executed semantics

requested 與 executed 兩側必須使用同一 identity type 與 canonicalization contract，各自引用一個完整的 `dataset_bundle_id`：

```text
requested_dataset_bundle_id
executed_dataset_bundle_id
```

- 無 substitution/fallback 時，兩值必須相等。
- 若已授權的 fallback 或 runtime resolution 改變 component/coverage/transform，executed 值必須改為 resolved closure 的另一個 bundle ID；receipt 必須顯式記錄 before/after IDs、變更的 component roles、reason code、resolution authority 與 evidence refs。
- 若 requested manifest 未能在 execution 前解析成完整 content identity，不得執行後再掃 filesystem 補成 executed identity；必須 fail closed 或先產生受控、可稽核的 resolution evidence。
- `requested == executed` 只能由兩份可重算 manifest 的 ID 比較證明，不能由 path 相同、檔名相同或 status 文案推定。
- TrialSpec、ExecutionIntent 與 terminal receipt 的 binding 細節屬 A1/A2 後續 scope；A0 只固定這個 invariant。

### 4.5 Decision invariants

1. `dataset_bundle_id` 唯一命名 consumer-visible input closure，不命名 runtime execution 或 registry row。
2. path 只能是 locator，永遠不是 identity evidence。
3. identity-bearing absence、fallback 與 coverage 不得以缺欄表示。
4. executed closure 在 execution boundary 被顯式綁定，不由事後 filesystem 狀態推定。
5. 既有 `dataset_hash` 不重新解釋，不自動等同 `dataset_bundle_id`。
6. immutable manifest/artifacts 是 evidence；DuckDB 或其他 index 只能是可刪除重建的 projection。
7. 沒有 complete evidence 的歷史資料保持 legacy/unknown，不猜測升級。

## 5. Legacy `dataset_hash` migration and quarantine

既有欄位固定定位如下：

```text
field: dataset_hash
legacy_identity_kind: FEATURES_ARTIFACT_V1
grain: exactly one features.parquet artifact bytes hash
semantic upgrade: forbidden
```

Compatibility/migration 規則：

1. legacy reader 仍可依原語意讀取 `dataset_hash`；新 reader 必須把它標成 `FEATURES_ARTIFACT_V1`，不得稱為完整 dataset bundle。
2. 不得從 legacy path、同目錄 siblings、目前 filesystem 或 hash 名稱反推出 bundle components。
3. 只有 contemporaneous immutable evidence 已完整封閉全部 components/transform/coverage 時，後續 A3 才可用顯式 migration manifest 記錄 `legacy dataset_hash -> dataset_bundle_id`、evidence refs、confidence=`EXACT` 與 migration version；該 mapping 不能改寫原 receipt。
4. 證據不足的 legacy records 保持 `LEGACY_DIAGNOSTIC_ONLY` 或等價 quarantine status，不得 admission 為 matched learning/adaptive evidence。
5. 新 execution 不得只寫 legacy `dataset_hash`；這是後續 implementation gate，不是本文件已生效的 runtime 行為。

Compatibility bridge owner 提案為 A1/A3 implementer；removal owner 為 A6。Removal condition 是所有 active writers/readers 已以 bundle ID 通過 round-trip、requested/executed mismatch、legacy quarantine 與 corpus rebuild tests，且新 execution 不再依賴 legacy-only field。Removal 不得刪除歷史 immutable evidence。

## 6. Why this is minimum sufficient

`why_not_less`：只改欄位名稱、保留單檔 hash 或把多個 path 裝進 manifest，都不能關閉 M4 consumer-visible closure 與 requested/executed fallback 的 measured gap。

`why_not_more`：A0 不需要 registry、database、provider resolver、通用 lifecycle、raw payload retention system 或新 runtime。現有 TrialSpec/receipt/immutable corpus/CAS/projection seams 足以承接後續最小 schema tightening。

`do_not_absorb`：不吸收 OMI runtime/SQLite/Alembic/provider adapters/control plane/UI；不把 OpenLineage、MLflow、DVC、Optuna、RDF 或 event store 升為 authority；不把 DuckDB、path、runtime ID 或 filesystem scan 升為 truth。

## 7. Compatibility, removal, and rollback

- Compatibility：保留 legacy field 原語意；新 schema 若經 Owner 與後續 card 接受，只能以明確 typed bridge 並存，不能 shadow reinterpretation。
- Removal：bridge 的 target removal stage 是 A6；在 acceptance tests 與 immutable historical retention 未滿足前不得移除 legacy reader。
- Docs-only rollback：Owner 若不接受本提案，revert 本文件即可；`4c6d41a`、`a6ca93c`、`f760e45` 的既有 code/evidence 不變，A0 stop 保持。
- Future implementation rollback prerequisite：任何 A1/A2 實作必須可停止新 bundle emission/reading並回到 legacy behavior，同時保留已寫入的 immutable proposal evidence；真正 rollback plan 由該 implementation card 驗收，本文件不授權執行。

## 8. A1 admission gate

A1 目前仍是 `BLOCKED`。只有以下全部成立，主線才可另行裁決是否 admission：

1. Owner 明確接受、修訂或退回本 decision；不能以本檔存在視為 acceptance。
2. identity grain、legacy `FEATURES_ARTIFACT_V1` 定位、requested/executed invariant 與禁止 path/scan identity 無未決 material ambiguity。
3. A1 卡明確限制為既有 domain seams 的 schema/catalog/validator tightening，並寫出 owner、removal、rollback 與 affected tests。
4. mandatory component matrix、transformation identity granularity、fundamentals snapshot semantics 等 UNKNOWN 有明確裁決或 fail-closed handling。
5. 不需要 runtime/config/schema/data/production mutation 才能完成 admission review；若需要，必須另取授權。

本文件不判定 `A1_ADMITTED`，也不解除 A0 stop。

## 9. A2 prerequisites only

若且唯若 A1 之後被接受並實作，A2 才能評估下列 prerequisites；此處不設計或實作 A2：

- ExecutionIntent 能 immutable 綁定 requested bundle manifest/ID。
- execution boundary 能在執行前或受控 resolution point 綁定 executed bundle manifest/ID。
- terminal receipt 能 fail closed 驗證兩側 manifest、ID、resolution delta 與 evidence refs。
- identity mismatch 有 typed reason/status，不靠 status prose、path equality 或事後 scan。
- receipt corpus 可在刪除 DuckDB 後重建 requested/executed dataset binding。
- legacy-only attempt 無法被誤分類為 exact bundle evidence。

這些只是 prerequisite inventory；A2 仍由 backlog dependency 與另行 admission 控制。

## 10. Given / When / Then acceptance contract

1. **Given** 相同 component bytes、consumer contract、coverage/resolution semantics 與 transformation identity 位於不同 paths，**When** verifier canonicalizes manifests，**Then** 兩者得到相同 `dataset_bundle_id`。
2. **Given** 任一 identity-bearing component、coverage/fallback state 或 transform identity 改變，**When** 重算 manifest，**Then** `dataset_bundle_id` 必須改變。
3. **Given** components 輸入順序不同但集合與 stable member keys 相同，**When** 依規則排序後 hash，**Then** bundle ID 相同；duplicate/ambiguous role 必須被拒絕。
4. **Given** execution 無 fallback/substitution，**When** terminal receipt 驗證 binding，**Then** requested 與 executed bundle IDs 相等。
5. **Given** execution 使用已授權 fallback，**When** terminal receipt 驗證 binding，**Then** executed ID 反映新 closure，且 receipt 顯式列出 before/after、changed roles、reason與 authority；不得只寫 path。
6. **Given** 只有 path 或未解析 component，**When** 嘗試發出 bundle ID，**Then** validator fail closed，不掃 filesystem 補值。
7. **Given** legacy `dataset_hash`，**When** 新 reader ingest，**Then** 它只被分類為 `FEATURES_ARTIFACT_V1`；沒有完整 contemporaneous evidence 時保持 quarantine。
8. **Given** DuckDB/index 被刪除，**When** 從 immutable manifests/receipts/migration evidence rebuild，**Then** bundle identity 與 requested/executed bindings 可重現。
9. **Given** Owner 尚未接受本文件，**When** 評估 A1 frontier，**Then** A1 仍為 blocked，A2 只保留 prerequisites。

## 11. UNKNOWN and technical follow-up

| ID | Status | Subject | Required next action / owner decision |
|---|---|---|---|
| `U-DATASET-001` | `UNKNOWN` | 各 consumer 的 mandatory/optional component matrix 尚未以 executable contract 固化。 | Owner 接受 grain 後，由 A1 卡逐 entrypoint 定義；未定義者 fail closed。 |
| `U-DATASET-002` | `UNKNOWN` | transformation identity 要採 contract version + exact source blob set、tree hash或其他粒度。 | Owner 選擇最小可重現且不因無關 code 過度 invalidation 的粒度。 |
| `U-DATASET-003` | `UNKNOWN` | fundamentals cache 尚無完整 immutable snapshot identity/coverage contract。 | A1 決定先建立 snapshot identity或將相關 consumer 明確標為 not executable。 |
| `U-DATASET-004` | `UNKNOWN` | `signals.yaml`、events 與 universe 在每個 entrypoint 的實際讀取條件需逐一驗證。 | A1 前以 pinned code/tests 建 component matrix，不以推測補齊。 |
| `U-DATASET-005` | `UNKNOWN` | raw provider attempt/session/payload receipt 與 bundle 的 provenance linkage 尚未存在。 | Owner 決定是否列為 A1 admission prerequisite或明確 defer；不可順手建立 provider runtime。 |
| `U-DATASET-006` | `UNPINNED_RUNTIME_ARTIFACT` | 目前 materialized parquet bytes、row/date coverage 與 producer run 未在 A0 讀取。 | 如確有必要，另行授權 runtime artifact inspection；不得由 committed code 推定。 |
| `U-DATASET-007` | `UNKNOWN` | 可被 EXACT migration 的 legacy corpus 覆蓋率尚未盤點。 | A3 才能做 immutable evidence inventory；不足者 quarantine，不猜測。 |
| `U-DATASET-008` | `UNKNOWN` | typed resolution reason codes 與 receipt field names 尚未定案。 | A1/A2 卡在不改本 decision invariants 下定義並測試。 |

## 12. Remaining Owner decisions

Owner 尚須明確裁決：

1. 是否接受 `DATASET_BUNDLE_V1` 的 consumer-visible closure grain 與 content-addressed `dataset_bundle_id`。
2. 是否接受 legacy `dataset_hash == FEATURES_ARTIFACT_V1` 且永不重新解釋。
3. 是否接受 requested/executed 各自引用 bundle ID、無 fallback 時相等、有 fallback 時以顯式 resolution delta 綁定。
4. transformation identity 的最小粒度與各 consumer mandatory component matrix。
5. fundamentals/raw-provider lineage 是 A1 admission prerequisite、fail-closed item，或明確 defer 到哪一張後續卡。

在上述 decisions 被接受並由主線留下 acceptance evidence 前，本提案狀態維持 `PROPOSED_FOR_OWNER_ACCEPTANCE / DOCS_ONLY / NOT_IMPLEMENTED`。
