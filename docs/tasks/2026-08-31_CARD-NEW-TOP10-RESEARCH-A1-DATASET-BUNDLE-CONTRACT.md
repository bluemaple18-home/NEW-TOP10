# CARD-NEW-TOP10-RESEARCH-A1-DATASET-BUNDLE-CONTRACT

日期：2026-08-31
狀態：`IMPLEMENTED_LOCAL / INDEPENDENT_REVIEW_GO / NOT_PUSHED / NOT_MERGED`
GitHub authority：Issue #3 `CARD-NEW-TOP10-RESEARCH-A1-CANONICAL-IDENTITY-AND-CATALOG`
Execution base：`origin/main@e3a15485240b4916f1fbd67e27b339977f8e95c0`
工作模式：`STRICT / CORE_BOUNDED / ADDITIVE_SCHEMA_AND_VALIDATOR_ONLY`

## 1. Root question

NEW-TOP10 能否在不重新解釋 legacy `dataset_hash`、不建立第二套 authority、且不實作 A2 execution binding 的前提下，用一份可重算、path-independent、consumer-scoped 的 immutable manifest，唯一命名與驗證實際 dataset input closure？

本卡的答案必須由 executable schema、canonicalizer、validator 與 tests 證明。只有文件、欄位名稱或 filesystem path 不構成完成證據。

## 2. Authority、admission 與 evidence base

### 2.1 Authority order

1. Owner 於 2026-08-31 明示「授權啟動」，授權 A1 進入本卡所界定的最小施工與驗收。
2. `docs/tasks/2026-08-30_CARD-NEW-TOP10-A0-DATASET-IDENTITY-GRAIN-DECISION.md`：Owner-accepted identity/grain decision。
3. `.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/07-schema-and-migration-hazards.md`。
4. `.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/08-open-questions-and-measured-gaps.md`。
5. `.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/09-a1-admission-and-a2-prerequisites.md`。
6. [Issue #3](https://github.com/bluemaple18-home/NEW-TOP10/issues/3) `CARD-NEW-TOP10-RESEARCH-A1-CANONICAL-IDENTITY-AND-CATALOG`。Mainline 於 2026-08-31 唯讀觀察：`state=open`、`updated_at=2026-08-23T04:18:07Z`、`comments=0`。

Issue #3 原始 scope 是 shared canonical execution identity、Quant Research domain schema 與 Parameter Catalog，且明確不改 runner behavior。其約束包括：`combo_id` 保持 legacy；不新增 opaque `lineage_id`；Parameter Catalog 只管理 validity/executability；dynamic symbolic parameters 必須保存 definition、version、context 與 resolved value；generic gaps 應回推 AI Core。原始 deliverables 是 schema/contract implementation、migration-safe compatibility definitions 與 tests。

Mainline reconciliation 將既有 TrialSpec identity、`run_id` 與 Parameter Catalog 裁決為 `NOT_A_GAP / USE_AS_IS`。因此本卡不重建 Issue #3 的既有能力，只施工 A0 measured evidence 支持的 dataset bundle identity gap；較廣的 execution identity、dynamic symbolic parameter 或 generic AI Core work 不因本卡而 admission。若後續 authority evidence 與此 reconciliation 出現 material conflict，立即停止並交 Mainline 裁決。

### 2.2 Pinned implementation evidence

- `app/research/contracts.py` 已提供 `research-canonical-json.v1`、`content_hash()`、TrialSpec 與 receipt validators；目前 `dataset_authority.dataset_hash` 仍只驗證單一 `sha256:` 值。
- `app/research/receipt_store.py` 已提供 immutable JSON writer 與 byte-level CAS；A1 應 `WRAP/USE_AS_IS`，不得另建 registry 或 database。
- `app/research/run_receipts.py` 目前由單一 features file manifest 產生 legacy `dataset_hash`，並在 terminal receipt 比對 requested/executed single-file hash。這是 compatibility seam，不是 A1 可直接改成 A2 binding 的授權。
- `app/modeling/feature_contract.py`、`app/agent_b_modeling.py`、`app/agent_b_ranking.py` 與 `scripts/run_backtest_strategy_matrix.py` 證明 consumers 的 component closure 與 fallback branch 不相同。
- `config/research_parameter_catalog.json`、現有 `trial_spec_id`、`run_id` 與 `Parameter Catalog` 均已存在：本卡分別裁決為 `USE_AS_IS` 或 `WRAP`，禁止重建。

### 2.3 CodeGraph fallback

開卡環境沒有可呼叫的 CodeGraph executable／初始化結果。依規範改用 bounded fallback，只搜尋：`app/research/contracts.py`、`app/research/receipt_store.py`、`app/research/run_receipts.py`、直接受影響 tests，以及 A0 07–09/Owner decision 指定的 consumer evidence。查詢核心為 `dataset_hash|dataset_authority|dataset_manifest|requested_executed|features.parquet|events.parquet|fundamental|signals.yaml|universe`。不得把此 bounded scan 宣稱為全 repo runtime inventory。

## 3. Admission disposition

```text
A1 = ADMITTED_FOR_THIS_CARD_ONLY
A1_IMPLEMENTATION = NOT_YET_COMPLETE
A2–A6 = BLOCKED / NOT_STARTED
```

Owner 的「授權啟動」解除 A1 的 admission blocker，但不等於任何 implementation 已完成，也不授權 A2 runtime binding。A1 只有在本卡所有 success criteria、review 與 rollback evidence 完成後才可宣告 complete。

## 4. Product-fit and minimum-sufficient boundary

### 4.1 Why not less

只替 `dataset_hash` 改名、只 hash `features.parquet`、只保存多個 path，或執行後掃 sibling files，都無法唯一證明 consumer-visible closure，也無法 deterministic 判斷 fallback、coverage 或 transformation drift。

### 4.2 Why not more

既有 canonical JSON、TrialSpec identity、immutable corpus、CAS、Parameter Catalog 與 receipt validators 已提供足夠 seam。A1 不需要 Dataset Registry、DB、ledger、第二套 lifecycle、provider resolver、event store、OMI runtime 或 A2 execution adapter。

### 4.3 Do not absorb

- 不吸收 OMI/OpenLineage/MLflow/DVC backend 或 runtime authority。
- 不把 DuckDB、path、mtime、branch name、run/session ID 升為 dataset truth。
- 不重建 TrialSpec IDs、`run_id`、Parameter Catalog、Research Ledger 或 terminal receipt lifecycle。
- 不把 raw provider acquisition provenance、learning、ranking/publish policy、scheduler 或 production promotion 塞進 bundle identity。

## 5. Scope

### 5.1 In scope

1. additive `DATASET_BUNDLE_V1` manifest data contract、canonicalizer、validator 與 content-addressed `dataset_bundle_id`。
2. typed legacy bridge：`dataset_hash` 永遠表示 `FEATURES_ARTIFACT_V1`，不得 semantic reinterpretation。
3. 明確的 per-consumer component/cardinality/resolution matrix；未列入或無法解析的 consumer/component fail closed。
4. transformation identity 固定為 `contract_version + exact Git blob set`。
5. fundamentals snapshot identity、as-of/coverage/missing semantics；無法提供時，使用 fundamentals 的 consumer 為 `NOT_EXECUTABLE`。
6. requested/executed bundle references 與 resolution delta 的 schema/prerequisites；只驗證純資料結構，不接入 ExecutionIntent、runner 或 terminal receipt writer。
7. deterministic、path-independent、mismatch、fallback、rebuild 與 legacy quarantine tests。

### 5.2 Explicit non-goals

- 不修改 provider、data acquisition、features calculation、model/backtest/ranking runtime、scheduler、publish 或 production。
- 不讓 TrialSpec/ExecutionIntent/run receipt 寫入或消費 bundle ID；這是 blocked A2 的 execution binding。
- 不建立 Dataset Registry、DB、canonical row writer、ledger 或新 authority surface。
- 不掃描或改寫 legacy corpus，不把 legacy records 猜測升級成 exact bundle evidence；完整 migration 屬 blocked A3。
- 不修改 `.work/current`。
- 不開始 A2–A6。

## 6. Minimum data contract

### 6.1 Identity payload

儲存 envelope 必須只有 `dataset_bundle_id` 與 `identity_payload`。`identity_payload` 必須只有下列 exact fields：

| field | exact contract |
|---|---|
| `schema_version` | literal `research-dataset-bundle.v1` |
| `canonicalization_version` | literal `research-canonical-json.v1` |
| `identity_kind` | literal `DATASET_BUNDLE_V1` |
| `consumer_contract` | exact object `{consumer_id, contract_version}`；兩者均為 consumer matrix 中的 literal |
| `components` | 非空 component semantic resolution records；exact discriminated union見下文 |
| `transformation_identity` | exact object `{contract_version, git_blob_ids}`；version為非空字串，IDs為非空、唯一、已排序且符合 `git-sha1:[0-9a-f]{40}` |
| `resolution_semantics` | exact object `{fallback_policy_version, identity_bearing_absence_is_explicit}`；version為非空字串，boolean 必須為 `true` |

`dataset_bundle_id = content_hash(identity_payload)`。`dataset_bundle_id` 本身、paths、timestamps、receipt IDs 與 runtime IDs 不得進入 identity payload。

#### Exact component discriminated union

每個 consumer-visible role，不論 artifact 是否存在，都必須恰有一筆 semantic resolution record。所有 variants 都是 exact-field objects；unknown fields、跨 variant 混欄或缺欄一律 fail closed。

| discriminator | exact fields | field constraints |
|---|---|---|
| `RESOLVED` | `role`, `member_key`, `identity_kind`, `content_id`, `resolution_status`, `format_contract`, `coverage` | `content_id=sha256:` + 64 lowercase hex；`format_contract`非空；禁止 `semantic_absence_code`、`member_count` |
| `ABSENT_BY_CONTRACT` | `role`, `member_key`, `identity_kind`, `resolution_status`, `semantic_absence_code`, `coverage` | 僅 `EVENTS_ARTIFACT` 可用；`semantic_absence_code=OPTIONAL_COMPONENT_NOT_PRESENT`；必須省略 `content_id`、`format_contract`、`member_count` |
| `ABSENT_USE_ALL_FEATURE_STOCKS` | `role`, `member_key`, `identity_kind`, `resolution_status`, `semantic_absence_code`, `coverage` | 僅 `UNIVERSE_ARTIFACT` 可用；`semantic_absence_code=UNIVERSE_NOT_PRESENT_USE_ALL_FEATURE_STOCKS`；必須省略 `content_id`、`format_contract`、`member_count` |
| `EMPTY_USE_ALL_FEATURE_STOCKS` | `role`, `member_key`, `identity_kind`, `content_id`, `resolution_status`, `format_contract`, `coverage`, `member_count` | 僅 `UNIVERSE_ARTIFACT` 可用；這是 resolved empty universe artifact，不是 sentinel；`content_id`必填、`member_count=0`、禁止 `semantic_absence_code` |

`role -> identity_kind` 固定映射為：`FEATURES_ARTIFACT -> FEATURES_ARTIFACT_V1`、`EVENTS_ARTIFACT -> EVENTS_ARTIFACT_V1`、`SIGNALS_CONFIG -> SIGNALS_CONFIG_V1`、`FUNDAMENTALS_SNAPSHOT -> FUNDAMENTALS_SNAPSHOT_V1`、`UNIVERSE_ARTIFACT -> UNIVERSE_ARTIFACT_V1`。`member_key` 必須是非空 stable token；本卡所有 singleton roles 固定為 `primary`。

除 `FUNDAMENTALS_SNAPSHOT` 外，一般 artifact `coverage` 必須是以下 exact union；fundamentals component直接使用§6.4 snapshot coverage exact object：

- resolved coverage：exact fields `{schema_version, status, expected_member_count, observed_member_count, date_start, date_end}`；`schema_version=dataset-component-coverage.v1`；counts為non-negative integers且observed<=expected；`COMPLETE`要求observed=expected，`PARTIAL`要求`0 < observed < expected`，`EMPTY`要求observed=0；dates為`YYYY-MM-DD|null`，empty時兩者皆null，非empty時兩者皆非null且start<=end。
- semantic absence coverage：同一 exact fields；`schema_version=dataset-component-coverage.v1`、`status=NOT_APPLICABLE`、`expected_member_count=null`、`observed_member_count=0`、`date_start=null`、`date_end=null`。
- resolved `EMPTY_USE_ALL_FEATURE_STOCKS` coverage 必須為 `status=EMPTY`、兩個 counts 均為 `0`、兩個 dates 均為 `null`，並與 top-level `member_count=0` 一致。

### 6.2 Canonicalization invariants

1. `components` 在 hash 前依 `(role, member_key, identity_kind, content_id_or_empty_string, resolution_status, semantic_absence_code_or_empty_string)` 排序；輸入順序不得影響 ID。absence variants以空字串代替不存在的 `content_id`，並靠 `resolution_status + semantic_absence_code` 唯一區分。
2. `git_blob_ids` 依完整 typed object ID 排序且不得重複；本版格式固定為正規式 `git-sha1:[0-9a-f]{40}`。source path 可作非 identity metadata，但 branch、working-tree SHA、path或 whole-repo tree hash 不可代替 exact blob set。
3. semantic record的 `(role, member_key)` 必須唯一。single-artifact role 重複、unknown/mixed union fields、unknown role、path-only component、invalid hash、NaN/Infinity、未聲明 absence/fallback 都 fail closed。
4. identity-bearing component/coverage/resolution/transform 任一改變，bundle ID 必須改變。
5. 相同 bytes 與 semantics 位於不同 paths，bundle ID 必須相同。
6. validator 必須先驗 schema，再重算 ID；不能信任呼叫端提供的 ID。

### 6.3 Consumer component/cardinality/resolution matrix

Matrix 必須是 versioned code/config contract，不能由目錄掃描推定。A1 只需固化下列已量測 consumers；未知 consumer 一律 `UNSUPPORTED_CONSUMER / NOT_EXECUTABLE`。

| consumer ID | contract version | role | artifact cardinality | semantic-record cardinality | executable resolution |
|---|---|---|---:|---:|---|
| `M4_TRAINING_V1` | `m4-training-dataset.v1` | `FEATURES_ARTIFACT` | exactly 1 | exactly 1 | production 或 test fallback 必須各自 `RESOLVED` 且產生不同 closure；不得只記 path |
| `M4_TRAINING_V1` | `m4-training-dataset.v1` | `EVENTS_ARTIFACT` | 0..1 | exactly 1 | 有檔為 `RESOLVED`；無檔為 `ABSENT_BY_CONTRACT` |
| `M4_TRAINING_V1` | `m4-training-dataset.v1` | `SIGNALS_CONFIG` | exactly 1 | exactly 1 | `RESOLVED` content ID |
| `M4_TRAINING_V1` | `m4-training-dataset.v1` | `FUNDAMENTALS_SNAPSHOT` | exactly 1 | exactly 1 | `RESOLVED` immutable snapshot identity + exact coverage；否則 consumer `NOT_EXECUTABLE` |
| `M4_RANKING_V1` | `m4-ranking-dataset.v1` | `FEATURES_ARTIFACT` | exactly 1 | exactly 1 | `RESOLVED` |
| `M4_RANKING_V1` | `m4-ranking-dataset.v1` | `EVENTS_ARTIFACT` | 0..1 | exactly 1 | `RESOLVED` 或 `ABSENT_BY_CONTRACT` |
| `M4_RANKING_V1` | `m4-ranking-dataset.v1` | `SIGNALS_CONFIG` | exactly 1 | exactly 1 | `RESOLVED` content ID |
| `M4_RANKING_V1` | `m4-ranking-dataset.v1` | `FUNDAMENTALS_SNAPSHOT` | exactly 1 | exactly 1 | `RESOLVED` immutable snapshot identity + exact coverage；否則 consumer `NOT_EXECUTABLE` |
| `M4_RANKING_V1` | `m4-ranking-dataset.v1` | `UNIVERSE_ARTIFACT` | 0..1 | exactly 1 | non-empty為 `RESOLVED`；missing為 `ABSENT_USE_ALL_FEATURE_STOCKS`；resolved empty file為 `EMPTY_USE_ALL_FEATURE_STOCKS`；三者 identity 不同 |
| `STRATEGY_MATRIX_FEATURES_V1` | `strategy-matrix-features.v1` | `FEATURES_ARTIFACT` | exactly 1 | exactly 1 | `RESOLVED`；不得暗示它等於 M4 closure |

所有 consumer 都必須含 `TRANSFORMATION_IDENTITY` 與 `CONSUMER_CONTRACT` top-level members。若實作者由 pinned code/tests 證明某一列不反映實際 consumer read，必須先修訂本卡並 review，不能在 code 中靜默改語意。

### 6.4 Fundamentals snapshot contract

`FUNDAMENTALS_SNAPSHOT_V1` 是 exact-field object，且只能含：`snapshot_content_id`、`schema_version`、`canonicalization_version`、`identity_kind`、`as_of`、`coverage`、`missing_value_semantics`、`records_contract`、`records_content_id`。

| field | exact contract |
|---|---|
| `snapshot_content_id` | `sha256:` + 64 lowercase hex；必須等於排除自身後的 `content_hash(payload)` |
| `schema_version` | literal `research-fundamentals-snapshot.v1` |
| `canonicalization_version` | literal `research-canonical-json.v1` |
| `identity_kind` | literal `FUNDAMENTALS_SNAPSHOT_V1` |
| `as_of` | `YYYY-MM-DD` |
| `coverage` | exact fields `{universe_content_id, expected_member_count, observed_member_count, date_start, date_end, status}` |
| `missing_value_semantics` | exact fields `{policy, version}`；policy enum=`PRESERVE_NULL|EXPLICIT_EMPTY_SNAPSHOT`，version為非空字串 |
| `records_contract` | exact fields `{schema_version, normalization_version}`；兩者為非空字串 |
| `records_content_id` | `sha256:` + 64 lowercase hex，指向 immutable canonical records bytes |

coverage 規則：`universe_content_id` 為 `sha256:` + 64 lowercase hex；counts為 non-negative integers且 observed 不得大於 expected；`status=COMPLETE` 時 observed=expected；`PARTIAL` 時 `0 < observed < expected`；`EMPTY` 時 observed=0。dates為 `YYYY-MM-DD|null`，非 null 時 start<=end；`EMPTY` 必須兩者皆 null，非 empty必須兩者皆非 null。

Golden vector（以 `research-canonical-json.v1` 排除 `snapshot_content_id` 後計算）：

```json
{
  "snapshot_content_id": "sha256:82f3aedc1b54e2df0064c6accc7f767231c8c98e4c7e1000a955535741fb02b5",
  "schema_version": "research-fundamentals-snapshot.v1",
  "canonicalization_version": "research-canonical-json.v1",
  "identity_kind": "FUNDAMENTALS_SNAPSHOT_V1",
  "as_of": "2026-08-30",
  "coverage": {
    "universe_content_id": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "expected_member_count": 2,
    "observed_member_count": 2,
    "date_start": "2026-06-30",
    "date_end": "2026-08-30",
    "status": "COMPLETE"
  },
  "missing_value_semantics": {
    "policy": "PRESERVE_NULL",
    "version": "fundamentals-missing.v1"
  },
  "records_contract": {
    "schema_version": "fundamentals-records.v1",
    "normalization_version": "fundamentals-normalization.v1"
  },
  "records_content_id": "sha256:2222222222222222222222222222222222222222222222222222222222222222"
}
```

Bundle 中 `FUNDAMENTALS_SNAPSHOT` component 的 `content_id` 必須等於被引用 manifest的 `snapshot_content_id`，component `coverage` 必須與 snapshot coverage逐欄相等；不一致即 fail closed。locator/path/current cache不得進 snapshot identity，也不得代替 contemporaneous immutable snapshot。未形成此 contract 時，不得發出相關 consumer 的 executable `dataset_bundle_id`。

### 6.5 Legacy bridge and quarantine

```text
field: dataset_hash
identity_kind: FEATURES_ARTIFACT_V1
grain: exactly one features artifact bytes SHA-256
semantic reinterpretation: FORBIDDEN
```

- legacy reader 可繼續讀原欄位；新 adapter 必須顯式輸出 `identity_kind=FEATURES_ARTIFACT_V1`。
- 沒有 contemporaneous complete bundle evidence 的 legacy record 標記 `LEGACY_DIAGNOSTIC_ONLY`，不得 synthesize `dataset_bundle_id`。
- A1 不改寫舊 immutable receipt，也不由 sibling path/current filesystem 補 components。
- Exact legacy-to-bundle migration coverage 留給 blocked A3。

### 6.6 Requested/executed prerequisites only

A1 可定義並單元測試下列 exact pure schema，不得把它接到 `begin_topic_attempt()`、`finish_topic_attempt()`、ExecutionIntent 或 receipt writer：

```json
{
  "requested_dataset_bundle_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "executed_dataset_bundle_id": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "resolution_delta": {
    "reason_code": "SOURCE_FALLBACK",
    "transition_profile_version": "m4-training-source-fallback.v1",
    "changed_identity_paths": [
      "/components/FEATURES_ARTIFACT:primary/content_id"
    ],
    "changed_roles": ["FEATURES_ARTIFACT"],
    "resolution_authority": "dataset-resolution-policy.v1",
    "requested_manifest_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "executed_manifest_id": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "evidence_refs": [
      "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    ]
  }
}
```

外層只能含 `requested_dataset_bundle_id`、`executed_dataset_bundle_id` 與 optional `resolution_delta`。delta 是由 `reason_code` 區分的 exact union：所有variants只能含 `reason_code`、`changed_identity_paths`、`changed_roles`、`resolution_authority`、`requested_manifest_id`、`executed_manifest_id`、`evidence_refs`；只有 `SOURCE_FALLBACK` variant額外必須含 `transition_profile_version=m4-training-source-fallback.v1`，其他reason variants必須省略該欄。hash fields與evidence refs必須是有效hash，authority非空，`changed_identity_paths`與`evidence_refs`非空、排序且唯一；`changed_roles`排序且唯一，只在沒有component change時允許空list。

Pure validator的輸入是此 envelope 加上兩份 immutable bundle manifests；必須先各自重算ID，並要求 `requested_manifest_id == requested_dataset_bundle_id`、`executed_manifest_id == executed_dataset_bundle_id`。缺任一manifest、ID重算不符或用path取代manifest都fail closed。

`reason_code` 固定 enum 與允許 path matrix：

| reason code | allowed changed path prefixes |
|---|---|
| `SOURCE_FALLBACK` | `/components/` component path grammar |
| `SOURCE_UNAVAILABLE` | `/components/` component path grammar |
| `COVERAGE_RECONCILIATION` | coverage path grammar only |
| `TRANSFORMATION_CHANGE` | `/transformation_identity/` |
| `RESOLUTION_POLICY_CHANGE` | `/resolution_semantics/` |

reason code同時約束 before/after values，不能只靠path通過：

- `SOURCE_FALLBACK`：A1只admit versioned、consumer-scoped、atomic profile `m4-training-source-fallback.v1`，且兩側consumer必須是`M4_TRAINING_V1@m4-training-dataset.v1`。validator必須以完整requested/target closure一次驗證下列全部roles，不能逐component各自放行：
  - `FEATURES_ARTIFACT:primary` 必須為同key的 `RESOLVED -> RESOLVED`，且`content_id`必須改變；format/coverage等resolution evidence可隨source一併改變。
  - `EVENTS_ARTIFACT:primary` 可完全不變，或為`RESOLVED -> RESOLVED`、`RESOLVED -> ABSENT_BY_CONTRACT`、`ABSENT_BY_CONTRACT -> RESOLVED`；target record必須符合exact union與matrix。
  - `FUNDAMENTALS_SNAPSHOT:primary` 兩側都必須為`RESOLVED`並各自通過§6.4 snapshot ID/coverage binding；可保持不變或改為target實際snapshot，但不得為任何absence variant。
  - `SIGNALS_CONFIG:primary` 必須逐欄不變。
  - 任何其他role、`consumer_contract`、`transformation_identity`、`resolution_semantics`或top-level identity path必須不變。`changed_identity_paths`必須等於上述允許roles的完整deterministic diff；`changed_roles`由paths精確派生，可含`FEATURES_ARTIFACT`、`EVENTS_ARTIFACT`、`FUNDAMENTALS_SNAPSHOT`多個roles，但必定包含`FEATURES_ARTIFACT`。
  - 若target無可命名且可驗證的fundamentals snapshot，整個target為`NOT_EXECUTABLE`；不得用fallback reason、absence record或current cache繞過。
  - `M4_RANKING_V1`、`STRATEGY_MATRIX_FEATURES_V1`及任何其他consumer使用`SOURCE_FALLBACK`一律fail closed；未來只有另行accepted的新contract/profile version才可開放。
- `SOURCE_UNAVAILABLE`：全部changed paths只能位於同一component root，`changed_roles`恰有一個role；該 `(role, member_key)` 只能是 `RESOLVED -> ABSENT_BY_CONTRACT|ABSENT_USE_ALL_FEATURE_STOCKS`，且target absence variant必須由該consumer matrix允許；例如events可到`ABSENT_BY_CONTRACT`，ranking universe可到`ABSENT_USE_ALL_FEATURE_STOCKS`。轉成`EMPTY_USE_ALL_FEATURE_STOCKS`、absence-to-absence、absence-to-resolved、mandatory role absence或其他transition都fail closed。
- 其他reason codes仍依path matrix驗證；不得用它們包裝上述source value transitions。reason enum、path與before/after transition任一不一致即fail closed。

stable typed path grammar只允許以下 leaf paths：

- component fields：`^/components/(FEATURES_ARTIFACT|EVENTS_ARTIFACT|SIGNALS_CONFIG|FUNDAMENTALS_SNAPSHOT|UNIVERSE_ARTIFACT):primary/(identity_kind|content_id|resolution_status|format_contract|semantic_absence_code|member_count)$`。
- component coverage fields：`^/components/(FEATURES_ARTIFACT|EVENTS_ARTIFACT|SIGNALS_CONFIG|FUNDAMENTALS_SNAPSHOT|UNIVERSE_ARTIFACT):primary/coverage/(schema_version|universe_content_id|expected_member_count|observed_member_count|date_start|date_end|status)$`；role schema不允許的field仍fail closed。
- transformation fields：`^/transformation_identity/(contract_version|git_blob_ids)$`；blob set 任一member改變都輸出唯一集合path `/transformation_identity/git_blob_ids`，不使用array index。
- resolution fields：`^/resolution_semantics/(fallback_policy_version|identity_bearing_absence_is_explicit)$`。

Deterministic diff 必須比較 requested/executed canonical identity payload，排除兩側 IDs。object fields以 schema field name遞迴比較；components不得用array index，而先由唯一 `(role, member_key)` 映射為typed component root，再輸出上述leaf paths。`changed_identity_paths` 是所有leaf changes按Unicode code-point排序且去重的完整集合，不得漏報、概括或加入未改paths。

`changed_roles` 只能由 `/components/{role}:{member_key}/...` paths派生，為 role names排序且去重的集合；若 changes只在 transformation/resolution semantics，必須為空 list。requested/executed 的 `consumer_id` 必須相同；`consumer_contract.contract_version` 不同時 fail closed並要求新的 TrialSpec，不得用任一 reason code解釋。每個 reason code的全部 changed paths都必須落在上表允許prefix，超界或混合prefix一律 fail closed；`COVERAGE_RECONCILIATION`只能改 coverage subtree，`TRANSFORMATION_CHANGE`只能改 transformation identity，`RESOLUTION_POLICY_CHANGE`只能改 resolution semantics，source fallback/unavailable只能改 components。

相等 IDs 時 delta 必須 absent；不等時 delta 必填，且兩個 manifest IDs、deterministic paths與derived roles全部一致。這只是 A1 結構一致性 prerequisite，不授權任何 A2 runtime transition；真正執行前 resolution point、terminal receipt binding與writer cutover全部屬 A2。

## 7. Functional requirements

- **A1-FR-001**：系統 SHALL 驗證 `research-dataset-bundle.v1` exact-field schema、component discriminated union、role/identity-kind mapping、artifact/semantic-record cardinality、resolution、coverage與hash formats；unknown/mixed fields fail closed。
- **A1-FR-002**：系統 SHALL 以 `research-canonical-json.v1` 產生 path-independent、order-independent、content-addressed `dataset_bundle_id`。
- **A1-FR-003**：系統 SHALL 以 versioned consumer matrix fail closed；每個consumer-visible role恰有一筆semantic resolution record，unknown consumer、undefined component或unresolved mandatory role不得發出executable ID；resolved empty universe不得降級為absence sentinel。
- **A1-FR-004**：transformation identity SHALL 使用 contract version 加 exact Git blob set；不得只使用 branch/path/current HEAD/whole tree。
- **A1-FR-005**：M4 consumer SHALL 綁定 exact `FUNDAMENTALS_SNAPSHOT_V1` immutable identity/coverage；bundle content ID與coverage必須逐欄匹配snapshot，否則回傳 `NOT_EXECUTABLE`。
- **A1-FR-006**：legacy `dataset_hash` SHALL 被 typed 為 `FEATURES_ARTIFACT_V1` 且永不重新解釋；證據不足的 legacy record SHALL quarantine。
- **A1-FR-007**：系統 SHALL 提供 requested/executed bundle reference與resolution delta的pure validator/deterministic diff；reason enum、allowed path prefixes、versioned consumer-scoped atomic transition profile、changed identity paths、derived roles與consumer contract一致性均須fail closed，但 SHALL NOT 寫入或改動runtime receipt lifecycle。
- **A1-FR-008**：manifest SHALL 可由 immutable JSON/CAS seams 保存並重算；刪除任何 projection 後 identity 結果不變。
- **A1-FR-009**：既有 `trial_spec_id`、`run_id` 與 Parameter Catalog SHALL `USE_AS_IS/WRAP`；A1 不得建立替代 identity/catalog authority。
- **A1-FR-010**：所有新增契約與 failure paths SHALL 有 deterministic tests，且既有 Research Spine contract/receipt tests不得回歸。

## 8. Stable vertical slices

### A1-VS-001 — Bundle schema and deterministic identity

- `traces_to`: `A1-FR-001`, `A1-FR-002`, `A1-FR-004`
- 交付：manifest types/constants、exact-field discriminated-union validator、canonicalizer、ID recomputation、absence-aware component/blob stable sorting。
- RED：相同 closure 不同 path/order產生不同 ID，或 unknown/duplicate/unresolved/mixed-variant input被接受。
- GREEN：deterministic/path-independent tests通過，identity-bearing drift必改 ID，absence records以empty content sort key穩定排序。

### A1-VS-002 — Consumer matrix and fundamentals fail-closed gate

- `traces_to`: `A1-FR-003`, `A1-FR-005`
- 交付：versioned matrix、artifact/semantic-record cardinality validation、exact fundamentals snapshot schema/golden vector與 `NOT_EXECUTABLE` result。
- RED：unknown consumer、缺/mismatch fundamentals snapshot、absence含content ID、empty universe無content ID、未聲明universe/events fallback仍能取得executable ID。
- GREEN：每個已知consumer的positive/negative cases符合§6.3，fundamentals golden vector固定，缺證據一致fail closed。

### A1-VS-003 — Legacy typed bridge and quarantine

- `traces_to`: `A1-FR-006`, `A1-FR-009`
- 交付：pure compatibility adapter/validator；保留單檔 hash原義，不碰歷史 corpus writers。
- RED：legacy hash被當成 bundle ID、由 path推導bundle、或 legacy-only record被標為 exact。
- GREEN：legacy輸出固定 `FEATURES_ARTIFACT_V1`/`LEGACY_DIAGNOSTIC_ONLY`，且原 readers/tests維持相容。

### A1-VS-004 — A2 schema prerequisites and rebuild verification

- `traces_to`: `A1-FR-007`, `A1-FR-008`, `A1-FR-010`
- 交付：pure requested/executed deterministic diff/validator、reason/path-prefix matrix tests、immutable manifest round-trip/CAS rebuild tests；不修改runner/receipt writer。
- RED：mismatch無delta、enum/path/profile/value-transition不匹配、atomic closure diff/roles漏報、signals偷變、fundamentals absence、unsupported consumer、consumer ID/version不合法，或identity依賴projection/path仍通過。
- GREEN：exact/mismatch、M4 training atomic fallback、unavailable、coverage/transform/policy/rebuild cases通過，且runtime writer parity保持不變。

## 9. Success criteria

- **A1-SC-001**：Given identity-bearing內容相同但 paths、object insertion order與component order不同，When canonicalize，Then `dataset_bundle_id` 完全相同。 `traces_to: A1-FR-001, A1-FR-002`
- **A1-SC-002**：Given 任一 component bytes、coverage、resolution、consumer contract或Git blob改變，When重算，Then ID改變。 `traces_to: A1-FR-002, A1-FR-004`
- **A1-SC-003**：Given duplicate semantic record、unknown role/consumer、invalid hash、path-only、unresolved mandatory或mixed union fields，When validate，Then fail closed且不發 ID；optional role缺semantic record也fail closed。 `traces_to: A1-FR-001, A1-FR-003`
- **A1-SC-004**：Given fundamentals golden vector，When排除自身ID canonicalize，Then得到`sha256:82f3aedc1b54e2df0064c6accc7f767231c8c98e4c7e1000a955535741fb02b5`；Given bundle content ID/coverage與snapshot不一致，Then consumer為`NOT_EXECUTABLE`。 `traces_to: A1-FR-005`
- **A1-SC-005**：Given ranking universe non-empty resolved、missing與resolved empty三種分支，When canonicalize，Then分別使用`RESOLVED`、`ABSENT_USE_ALL_FEATURE_STOCKS`、`EMPTY_USE_ALL_FEATURE_STOCKS`並得到不同IDs；empty variant必有content ID且member_count=0，absence variant必無content ID且有固定absence code。 `traces_to: A1-FR-001, A1-FR-003`
- **A1-SC-006**：Given training production features與test fallback features，When canonicalize，Then fallback closure不同，且沒有使用 path作 identity。 `traces_to: A1-FR-002, A1-FR-003`
- **A1-SC-007**：Given legacy `dataset_hash`，When bridge，Then只得到 `FEATURES_ARTIFACT_V1`；缺 contemporaneous bundle evidence時為 `LEGACY_DIAGNOSTIC_ONLY`，不產生 bundle ID。 `traces_to: A1-FR-006`
- **A1-SC-008**：Given `M4_TRAINING_V1@m4-training-dataset.v1` 的atomic fallback使features `RESOLVED→RESOLVED`且content ID改變、events `RESOLVED→ABSENT_BY_CONTRACT`、fundamentals `RESOLVED→RESOLVED`且snapshot改變、signals不變，When以`m4-training-source-fallback.v1` validate，Then只有manifest IDs與外層IDs相等、完整sorted unique paths涵蓋三個changed roles且roles精確派生才通過；漏報任一diff/role、signals改變、fundamentals absent或unsupported consumer一律fail closed。IDs相等時禁止delta，缺manifest或enum/path/profile/value-transition不匹配也fail closed。 `traces_to: A1-FR-007`
- **A1-SC-009**：Given immutable manifest/CAS corpus與空 projection，When rebuild/recompute，Then IDs及validation disposition一致。 `traces_to: A1-FR-008`
- **A1-SC-010**：Given現有 TrialSpec/receipt/legacy tests，When跑受影響suite，Then既有 IDs、Parameter Catalog與legacy writer行為不變；A2 runtime fields未出現在 writer diff。 `traces_to: A1-FR-009, A1-FR-010`

## 10. Blocking edges and frontier

```text
A0 Owner decision + A0 Integrator acceptance
  -> A1 card admission (本卡，已由 Owner 授權啟動)
  -> A1-VS-001
  -> A1-VS-002
  -> A1-VS-003
  -> A1-VS-004
  -> independent review + Mainline acceptance
  -> A1 complete
  -> only then may A2 receive a separate admission decision
```

- `A1-VS-002` blocked by `A1-VS-001` schema/identity primitives。
- `A1-VS-003` 可在 VS-001 後平行，但不得切換 active writers。
- `A1-VS-004` blocked by VS-001/VS-002；只做 pure prerequisite contract。
- A2 blocked by accepted、implemented、verified A1；A3 blocked by A1+A2；A4–A6依 backlog繼續 blocked。
- Issue #3 不得因 card merge 自動關閉；必須等 implementation、tests、review與Mainline acceptance receipt。

## 11. RED → GREEN verification

實作者須先新增 failure tests，再以最小 code 使其通過：

1. `uv run pytest` 執行新增 dataset bundle contract tests。
2. `uv run pytest tests/test_research_spine_contracts.py tests/test_research_receipt_store.py tests/test_autonomous_research_receipts.py tests/test_research_legacy_migration.py`。
3. deterministic golden vectors：reordered inputs/path changes same ID；component/coverage/fallback/blob changes different ID；fundamentals vector固定得到`sha256:82f3aedc1b54e2df0064c6accc7f767231c8c98e4c7e1000a955535741fb02b5`。
4. negative union/matrix：unknown consumer/role、duplicate或missing semantic record、mixed variant fields、absence錯帶content ID/code、empty universe缺content ID或member_count非0、unresolved mandatory、missing/mismatch fundamentals、invalid content/blob IDs、path-only input。
5. requested/executed：exact、M4 training跨features/events/fundamentals三角色atomic fallback、source unavailable、coverage reconciliation、transformation change、resolution policy change、missing/recomputed-ID-mismatch manifest、missing delta、unsorted/duplicate/incomplete paths、wrong derived roles、consumer mismatch/version drift，以及每個enum/path-prefix/profile/value-transition不匹配的fail-closed case；至少覆蓋漏報role/diff、features轉absence、features content ID未變、signals偷變、fundamentals absent/不可命名snapshot、ranking或strategy-matrix consumer使用fallback、unavailable轉empty sentinel、unavailable target不被consumer matrix允許。
6. immutable round-trip：write/read/recompute相同；projection absent仍可驗證。
7. `git diff --check`。
8. scoped diff audit：不得含 `.work/current`、provider/scheduler/production/learning、runtime writer binding或A2–A6 implementation。

若完整既有 tests 因與本卡無關的 pre-existing failure 不能全綠，receipt 必須固定 command、failure與base SHA；不得把未跑或失敗寫成 PASS。

## 12. Rollback、removal 與 ownership

- Implementation owner：A1 implementer；只負責 additive schema/canonicalizer/validator/tests。
- Review owner：independent reviewer + Mainline。
- Rollback owner：Mainline；以 revert A1 implementation commits 停止新 bundle validation/emission seam，保留所有已產生 immutable evidence。
- Legacy bridge removal owner：A6 owner；A1 無權刪除 legacy reader/field。
- Removal gate：所有 active writers/readers完成 bundle round-trip、mismatch/fallback/quarantine/rebuild驗證，且 A2/A3 已另行 accepted；移除 bridge也不得刪歷史 evidence。
- Projection/derived index 必須可刪除重建；rollback 不依賴 destructive corpus rewrite。

## 13. Stop conditions

遇到以下任一情況立即停止，回報 exact blocker，不設計 local workaround：

1. Issue #3 或較高 authority 與 Owner-accepted dataset grain出現 material governing-authority conflict。
2. 無法以 per-consumer contract唯一決定 component grain/cardinality/resolution，且不同選擇會產生不同 identity。
3. 必須修改 ExecutionIntent、runner、terminal receipt writer/boundary才能讓 A1 tests通過。
4. 必須讀/改 runtime data、建立 DB/Registry/ledger、掃描 legacy corpus或猜測 filesystem state。
5. 必須修改 provider、features/backtest/ranking、scheduler、publish、production或learning。
6. fundamentals snapshot無法被immutable命名/覆蓋，且實作者試圖用目前 cache/path代替；正確結果是 consumer `NOT_EXECUTABLE`。
7. 既有 TrialSpec IDs、`run_id`、Parameter Catalog需要 semantic rewrite或第二套 authority。
8. 任何工作需要開始 A2–A6 或寫入 `.work/current`。

## 14. Likely files

允許的最小候選面；實作前須以 RED tests確認真正必要檔案：

- `app/research/contracts.py`：共用 hash/validation seam；若保持 bounded，可放 small bridge/constants。
- `app/research/dataset_bundle.py`（preferred additive domain module）：manifest canonicalizer、validator、consumer matrix、legacy adapter、pure requested/executed diff。
- `app/research/receipt_store.py`：只有既有 immutable JSON/CAS seam 無法以 USE_AS_IS 承接 manifest round-trip時才可做薄 wrapper；不得新增 entity registry authority。
- `tests/test_research_dataset_bundle.py`（preferred new targeted suite）。
- `tests/test_research_spine_contracts.py`、`tests/test_research_receipt_store.py`、`tests/test_autonomous_research_receipts.py`、`tests/test_research_legacy_migration.py`：只補 compatibility/non-regression assertions。

預設不應修改 `app/research/run_receipts.py`。若實作者認為必須修改，視為碰到 A2/runtime-binding boundary，依 stop condition #3 停止並交 Mainline裁決。

## 15. Final acceptance contract

A1 只有在以下全部成立時可由 Mainline 宣告完成：

1. `A1-SC-001`～`A1-SC-010` 全部具可重現 evidence。
2. 每個 vertical slice 都有 RED failure與GREEN pass receipt，並能由 `traces_to` 回到 stable FR/SC。
3. legacy `dataset_hash` 沒有 semantic rewrite；Parameter Catalog、TrialSpec IDs、`run_id` 與 runtime writers保持原 authority。
4. 沒有 Registry/DB/ledger/second lifecycle，沒有 provider/scheduler/production/learning mutation。
5. independent review沒有未解 P0/P1，Mainline接受 rollback/removal evidence。
6. A2–A6保持 `BLOCKED / NOT_STARTED`；A1 complete 只允許另行評估 A2 admission，不會自動啟動 A2。

## 16. Mainline local acceptance receipt

日期：2026-08-31

### 16.1 Pinned delivery identity

| evidence | pinned value |
|---|---|
| execution base | `e3a15485240b4916f1fbd67e27b339977f8e95c0` |
| accepted task card | `3f75b42cc339e5ebd66e6d7a435a9dfe3a98ab6d` |
| accepted implementation | `02640252bed01b7f3c5616d7c24a39423dfea31a` |
| implementation parent/card boundary | `3f75b42cc339e5ebd66e6d7a435a9dfe3a98ab6d..02640252bed01b7f3c5616d7c24a39423dfea31a` |
| GitHub Issue | Issue #3 remains `open` |
| delivery state | `LOCAL_ONLY / NOT_PUSHED / NOT_MERGED` |

Implementation changed files exactly：

- `app/research/dataset_bundle.py`
- `tests/test_research_dataset_bundle.py`

相對 execution base 的第三個檔案只有本 task card；implementation 沒有修改既有 runner、receipt writer、Parameter Catalog、provider、scheduler、production或 `.work/current`。

### 16.2 RED → GREEN evidence

首次 RED failure receipt：`EVIDENCE_UNAVAILABLE`。Implementer/Mainline 提供的可核對資料沒有保存首次 RED command output、failed test IDs或failure text，因此本 receipt 不猜測、不補寫 RED 已觀察事實。此缺口不改寫為 PASS；它保留為 delivery-process evidence limitation。

GREEN evidence：

1. Implementer command：

   ```text
   uv run pytest tests/test_research_dataset_bundle.py tests/test_research_spine_contracts.py tests/test_research_receipt_store.py tests/test_autonomous_research_receipts.py tests/test_research_legacy_migration.py
   ```

   Result：`73 passed`。

2. Mainline 在同一 worktree 獨立重跑相同五個 suites：

   ```text
   .venv/bin/python -m pytest tests/test_research_dataset_bundle.py tests/test_research_spine_contracts.py tests/test_research_receipt_store.py tests/test_autonomous_research_receipts.py tests/test_research_legacy_migration.py
   ```

   Result：`73 passed in 1.58s`。

3. `git diff --check e3a15485240b4916f1fbd67e27b339977f8e95c0..02640252bed01b7f3c5616d7c24a39423dfea31a`：`PASS`。

### 16.3 Independent review disposition

Initial fixed-SHA review target：`c95ee5c6a18e07cbfd0cd4790d0c07deef3330e5`。

| severity | finding | repair disposition |
|---|---|---|
| `P2` | `_date_or_none()` 只做 regex，錯誤接受 `2026-00-01`、`2026-02-31` 等不存在日期。 | amended implementation `02640252bed01b7f3c5616d7c24a39423dfea31a` 已修復；fixed-SHA re-review=`CLOSED`。 |
| `P3` | `publish_dataset_bundle_manifest()` 重複實作 `receipt_store` 的 immutable writer。 | amended implementation `02640252bed01b7f3c5616d7c24a39423dfea31a` 已改為重用既有 seam；fixed-SHA re-review=`CLOSED`。 |

Final fixed-SHA review target：`02640252bed01b7f3c5616d7c24a39423dfea31a`。Disposition：`GO / P0=0 / P1=0 / P2=0`；上述 P2/P3 均 `CLOSED`。

### 16.4 Forbidden-surface audit

`3f75b42..0264025` 的 file-level diff 只有新增 domain module與targeted tests。Mainline bounded audit結論：

- 沒有修改 `app/research/run_receipts.py`、ExecutionIntent、terminal receipt writer/boundary或既有 runtime binding。
- 沒有修改 `config/research_parameter_catalog.json`、既有 TrialSpec IDs、`run_id` 或 legacy immutable corpus。
- 沒有新增 Dataset Registry、DB、ledger、second lifecycle或新 canonical runtime authority。
- 沒有修改 provider、features/backtest/ranking runtime、scheduler、publish、production或learning。
- 沒有讀寫 `.work/current`，沒有啟動 A2–A6。

CodeGraph 在此 worktree 未初始化，Mainline依既有規範使用 bounded fallback，只核對 task card、兩個 implementation files、五個指定 test suites及既有 receipt/CAS seams；此 audit 不宣稱全 repo CodeGraph coverage。

### 16.5 Local acceptance disposition

```text
A1_IMPLEMENTATION = LOCALLY_ACCEPTED_FOR_DELIVERY
INDEPENDENT_REVIEW = GO
ISSUE_3 = OPEN
PUSH = NOT_AUTHORIZED / NOT_DONE
PR = NOT_CREATED
MERGE = NOT_AUTHORIZED / NOT_DONE
A2–A6 = BLOCKED / NOT_STARTED
```

Mainline 接受 `02640252bed01b7f3c5616d7c24a39423dfea31a` 作為 A1 本地 delivery candidate。此 receipt 不等於 GitHub delivery、mainline merge或 Issue #3 close；也不構成 A2 admission。後續 push／PR／merge／Issue同步須另依 Owner授權執行。
