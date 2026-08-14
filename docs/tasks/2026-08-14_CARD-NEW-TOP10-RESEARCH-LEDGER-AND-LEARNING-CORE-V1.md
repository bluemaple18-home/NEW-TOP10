---
id: CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: IN_PROGRESS
type: architecture-implementation
priority: P1
owner: TOP10new research platform
role: implementation
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 跨研究 identity、不可變 receipt、資料 schema、sealed 隔離、歷史遷移與可重建 projection；規格已固定，但需高強度資料契約與回歸驗證。
date: 2026-08-14
production_change_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1/
---

# NEW-TOP10 Research Ledger & Learning Core V1

## 任務目的

建立 NEW-TOP10 長期研究系統的唯一事實骨架（canonical Research Spine）：

```text
Research Definition
        ↓
Canonical TrialSpec
        ↓
Research Intent / Attempt
        ↓
Existing Backtest Execution
        ↓
Immutable RunReceipt
        ↓
Rebuildable Research Ledger
        ├─ Observation / Eligibility projection
        ├─ Failure classification projection
        ├─ Matched Learning projection
        └─ Fog Map / PM projection input
```

本卡不是在舊系統外新增一套 Adaptive Layer。它要建立新的 canonical research spine，讓舊的混合 identity、每日 backfill 與多份 history authority 可以逐步退休。

本卡完成後，刪除 DuckDB ledger，仍必須只靠 immutable source corpus、catalog/schema definitions 與 migration manifest 完整重建所有 Card A 資料；任何新 run 從 attempt 開始到成功或失敗，都不得隔天再掃 filesystem 猜測發生過什麼。

## Root question

NEW-TOP10 能否以單一、可重建、可稽核且 sealed fail-closed 的研究事實骨架，回答「實際要求跑什麼、實際跑了什麼、產生何種 evidence、哪些 evidence 可以學、學到了什麼」？

## Scope boundary

### 本卡必做

- Canonical Research Parameter Catalog。
- 版本化 TrialSpec canonicalization 與 identity。
- Research Intent / Attempt identity。
- Immutable RunReceipt，完整記錄 requested 與 executed 差異。
- 失敗 attempt 也必須產 receipt。
- 可刪除重建的 DuckDB Research Ledger。
- 一次性 legacy migration 與 migration manifest。
- Observation eligibility、sealed isolation 與 lineage validation。
- Matched parameter learning、failure classification 與 PM-readable learning summary。
- 新研究完成路徑原生寫 receipt，不依賴隔日 filesystem backfill。
- 舊 history authority 的 deprecation 契約與 consumer migration map。

### 本卡禁止

- Adaptive priority 或 shadow queue。
- 改 manager queue 選題順序。
- 讓 daily quota 消費 adaptive decision。
- TrialSpec 驅動的精確 runner integration（屬後續 Runner Integration 卡）；本卡只記錄現有 runner 的 requested/executed 事實。
- Optuna。
- Dynamic refinement。
- Dashboard／Fog Map UI 重做。
- LightGBM retrain、model write、ranking change、promotion 或 production config mutation。
- 新 scheduler、launchd 或背景服務。

## Canonical identity model

### `topic_id`

研究假設或研究家族 identity。不得用它代表精確可執行參數。

### `coverage_coordinate_id`

Fog Map / inventory 的 coverage 座標。可以是合法但不可執行、unsupported 或 rule-pruned；不等於 negative observation。

### `trial_spec_id`

可執行研究定義的內容位址 identity：

```text
trial_spec_id = hash(canonicalization_version + normalized TrialSpec content)
```

必須同時保存：

- `canonicalization_version`
- `trial_spec_schema_version`
- normalized content
- content hash algorithm

Normalization 規則變更必須升版；不得讓相同語意靜默換 hash，也不得讓不同語意共用舊 hash。

### `intent_id`

一次要求執行 TrialSpec 的 immutable request identity。即使 trial 相同，不同 request／selection reason 仍有不同 intent。

### `run_id`

一次 execution attempt identity。retry 必須建立新 run，並連回相同或後繼 intent；不得覆寫前一個失敗 attempt。

### `observation_id`

一次 completed execution 對一個可識別結果單元的 identity。它不是 raw row number，也不是 `combo_id` 的別名。

### `artifact_id`

Source artifact 的內容雜湊 identity。

### `lineage_id`

由 dataset、ranking source、regime、research stage、episode partitions、sealed policy 與相關 authority hashes 組成的版本化 lineage identity。

### Legacy `combo_id`

只保留在 migration mapping 與 compatibility projection，不再成為新 Research Spine 的 canonical primary key。

## Canonical Research Parameter Catalog

單一 catalog 必須描述：

- dimension id 與資料型別。
- allowed values 與 ordered numeric adjacency。
- `null` / `none` / disabled 的 categorical baseline 語意。
- coverage participation。
- executable support。
- research stage restrictions。
- regime restrictions。
- runner field mapping。
- default value 與 default 是否只是 coverage default。
- dynamic value policy（V1 固定禁止 execution）。
- catalog schema/version/hash。

Fog Map grid、formal executable parameter universe、validation profiles 與 matched learning adjacency 必須在Card A內改由同一catalog projection產生。Catalog是唯一authoring authority；舊map/formal/runner definitions只能成為generated compatibility projections或reader adapters。Authority cutover完成前不得宣告Card A完成，避免catalog變成第四份永久定義。

若歷史 artifact 沒有正式證明 `regime_gate`、`risk_guard` 或 `entry_filter`，observation 必須保存 `UNKNOWN`，不得用 Fog Map default coordinate 補造成 execution evidence。

## TrialSpec contract

至少包含：

- schema 與 canonicalization version。
- topic / topic family identity。
- parameters 與 parameter catalog version。
- research stage。
- regime scope。
- dataset authority / expected lineage。
- ranking source authority。
- execution profile。
- production safety contract。
- requested source / selection reason（Card A 可為 existing manager）。

TrialSpec 是 requested definition，不等於 execution fact。

## Immutable RunReceipt contract

### Receipt lifecycle

Runner 啟動前必須先以 atomic exclusive-create 寫入 immutable Intent 與 AttemptStarted event；不得等執行完成才第一次留下事實。正常可控制的 terminal path 必須產 terminal receipt：

- `SUCCEEDED`
- `FAILED`
- `REJECTED_BEFORE_EXECUTION`
- `CANCELLED`

不得只為成功 run 產 receipt。SIGKILL、host crash或斷電無法保證terminal writer執行；reconciliation只能把已有AttemptStarted且無terminal receipt者標為 `ORPHANED_ATTEMPT`，不得猜測executed parameters、lineage或結果。後續retry建立新`run_id`，不得補寫或覆寫舊attempt。

Intent、AttemptStarted與terminal receipt均使用write-temp + fsync + atomic rename或等價durable protocol；identity path採exclusive-create，既存內容不同時必須報collision，不得覆寫。

### Requested vs executed

Receipt 至少保存：

- `requested_trial_spec_id`
- `requested_parameters`
- `requested_research_stage`
- `requested_regime_scope`
- `requested_dataset_authority`
- `executed_parameters`
- `executed_research_stage`
- `executed_regime_scope`
- `executed_dataset_hash`
- `executed_ranking_source_hash`
- `resolution_events[]`
- `identity_match_status`

任何 runner resolution、fallback、profile adjustment、parameter expansion 或 dataset substitution 都必須留下結構化差異。Card A 不一定阻止既有 matrix expansion，但 receipt 必須忠實記載 requested 與 executed units，不能只保存意圖。

### Lineage 與 sealed policy

Receipt 必須保存足以重建：

- research stage。
- regime identity。
- dataset hash。
- ranking source hash。
- development / validation / embargo / sealed episode IDs 與 authority hashes。
- sealed usage status。
- candidate / baseline relationship。
- source artifact hashes。

Sealed status 使用三態：

- `PROVEN_NON_SEALED`
- `SEALED`
- `UNKNOWN`

只有 `PROVEN_NON_SEALED` 才可能成為 adaptive-eligible observation。缺欄、衝突或無法重建 authority 一律 fail closed。

### Safety

每張 receipt 必須明示：

- `does_not_train_model = true`
- `does_not_change_production_ranking = true`
- `production_promotion_allowed = false`

## Source authority order

來源只用於建立可追溯evidence chain，不得以precedence掩蓋衝突。任何sealed status、research stage、dataset、regime或episode authority衝突，一律 `INVALID_LINEAGE` 並fail closed。Requested authority與executed fact分欄保存，不做precedence merge。

在沒有衝突時，來源可信度順序為：

1. Immutable run / development / statistical-family authority contract。
2. Strategy Matrix contract 與執行 inputs。
3. Autonomous research run outcome / command receipt。
4. Explicit migration manifest mapping。
5. Legacy backfill row。

檔名、目錄名稱與時間戳只能協助 discovery，不得證明 research stage、regime 或 sealed status。

## Research Ledger

### Storage role

使用單一 DuckDB 作 query/index/cache：

`data/research/research_ledger.duckdb`

DuckDB 不是 evidence authority，必須可安全刪除後重建。Canonical inputs 只有：

- immutable RunReceipt corpus。
- versioned catalog/schema definitions。
- immutable content-addressed source corpus（CAS）。
- immutable migration manifest。

Manifest只記hash與可變原路徑不足以重建。Legacy migration必須把canonical migrated record或原始source bytes寫入immutable CAS，manifest以content hash引用；原路徑只作provenance。

### 最低 tables / projections

- `trial_specs`
- `research_intents`
- `run_receipts`
- `run_artifacts`
- `observations`
- `observation_provenance`
- `observation_eligibility`
- `migration_sources`
- `projection_runs`

具體正規化可在 implementation slice 中定案，但禁止把 JSON blob 當唯一可查欄位。

### Idempotency

同一 receipt identity、artifact content hash 與 observation identity 重複 ingest 不得新增 rows。內容相同但來源路徑不同只可增加 provenance mapping，不可增加 evidence weight。

Semantic observation identity至少由以下內容版本化產生：

- executed `trial_spec_id` / normalized executed parameters。
- executed `lineage_id`。
- result unit / independent episode cluster identity。
- metric/result policy version。
- attempt inclusion policy。

相同semantic identity但metrics或lineage facts衝突時標記collision並停止該observation進入eligibility；不得last-write-wins。

### Incremental ingestion

新 receipts 以 immutable receipt identity / manifest cursor 增量 ingest。正常 daily path 不掃全 repo，也不以 filesystem mtime 作唯一 cursor。

### Rebuild invariant

刪除 DuckDB 後，rebuild 必須得到相同的：

- key sets。
- row counts。
- content hashes。
- eligibility counts。
- projection policy/version provenance。

## Legacy migration

### Migration inputs

- Existing Strategy Matrix artifacts。
- Autonomous run outputs。
- `run_history.json`。
- `run_history.jsonl`。
- Existing regime/development authority artifacts。

### Migration rules

- 每個 source artifact 必須 content-addressed。
- Source bytes或canonical migrated record必須進immutable CAS；只保留原路徑不合格。
- migration manifest 保存 source hash、parser version、classification result 與 exclusion reason。
- 無完整參數的 topic-level record：`TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE`。
- 無可信 lineage：`LEGACY_DIAGNOSTIC_ONLY` 或 `INVALID_LINEAGE`。
- sealed evidence：`SEALED_VALIDATION_ONLY`。
- unsupported、rule-pruned、missing data：`UNSUPPORTED_NOT_AN_OBSERVATION`。
- Migration 不得把缺少的 V2 dimensions 補成 default execution evidence。
- Legacy rows 可用於診斷與 reconciliation，但不得因資料量大而降低 eligibility gate。

Migration 完成後，舊 history 宣告 `LEGACY_READ_ONLY`。Compatibility reader 可以暫存，但必須有移除條件，不得成為新研究的正常寫入路徑。

## Observation eligibility

允許狀態：

- `ADAPTIVE_ELIGIBLE`
- `LEGACY_DIAGNOSTIC_ONLY`
- `SEALED_VALIDATION_ONLY`
- `TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE`
- `UNSUPPORTED_NOT_AN_OBSERVATION`
- `INVALID_LINEAGE`

`ADAPTIVE_ELIGIBLE` 必須同時證明：

- complete parameter identity。
- dataset lineage。
- research stage。
- regime identity。
- artifact source hash。
- terminal execution result。
- `sealed_usage_status = PROVEN_NON_SEALED`。
- requested/executed identity 可解釋。

Eligibility policy 必須保存：

- `eligibility_policy_version`
- classifier code/version hash 或等價版本。
- input receipt / observation IDs。
- generated timestamp。
- structured reason codes。

## Matched learning contract

### Comparison unit

V1 使用 matched contrast，不使用跨 topic／regime／dataset 的簡單 group average。

Matching key 至少包含：

- canonical topic family。
- regime identity。
- dataset hash。
- ranking source hash。
- research stage。
- lineage family / independent episode cluster。
- 其他所有 executable parameters。

只允許目標 parameter 不同。

### Evidence unit

Confidence 不得按 raw row 數膨脹。每個 finding 必須同時回報：

- raw observation count。
- deduplicated observation count。
- distinct lineage count。
- independent matched contrast count。

同一 artifact 的 archive、copy、backfill 或 repeated projection 不得增加 evidence weight。

### Numeric / categorical

- `null`、`none`、disabled 是 categorical baseline，不參與 numeric slope或 adjacency。
- Numeric adjacency 來自 versioned Parameter Catalog。
- `max_drawdown` 越接近 0 越好。

### Output classifications

- `HIGHER_LOOKS_BETTER`
- `LOWER_LOOKS_BETTER`
- `INTERIOR_PEAK`
- `FLAT`
- `NON_MONOTONIC`
- `UNSTABLE`
- `INSUFFICIENT_EVIDENCE`
- `GLOBAL_NOT_ESTIMABLE`
- `RISK_RETURN_TRADEOFF`
- `CONDITIONAL_EFFECT`
- `ROBUST_BASIN`
- `SHARP_PEAK`
- `OVERFIT_RISK`
- `LOW_SENSITIVITY`

### Confidence

正式名稱使用 `evidence_confidence`，避免與統計信賴區間混淆。至少考慮：

- independent matched contrast count。
- distinct lineage count。
- effect size。
- direction consistency。
- variance。
- regime consistency。
- statistical evidence quality。

單一 dataset 或單一 lineage 即使 rows 很多，也不得判 HIGH。

### Robust / failure rules

- Robust basin 必須是 Parameter Catalog 中連續相鄰值，且 matched metrics 接近、return 正向、drawdown 合格。
- Sharp peak 必須有中心點與左右 matched neighbors。
- `EXCESS_DRAWDOWN` 沿用 versioned research contract threshold。
- `NO_IMPROVEMENT` 必須相對 matched baseline。
- `DATA_INSUFFICIENT` 是 evidence 狀態，不算策略 failure。
- Dead region 只能由 `ADAPTIVE_ELIGIBLE` matched evidence 建立；unsupported、legacy、sealed與missing data禁止使用。
- Global finding 只有跨 regime 一致且 evidence gate 通過才可產生；否則為 `GLOBAL_NOT_ESTIMABLE`。

## Projection provenance

所有可重算 projection 必須保存：

- schema version。
- input corpus / receipt set hash。
- Parameter Catalog version/hash。
- eligibility policy version。
- failure classifier version。
- learning policy version。
- canonicalization version。
- generated timestamp。

同一批 receipts 因 policy 升版得到不同結論時，兩個 projection 必須可同時解釋，不得覆寫成無版本的 latest-only truth。

## Required artifacts

```text
artifacts/autonomous_research/
├── receipts/
│   └── <run_id>.json
├── migration/
│   └── research_ledger_migration_manifest_v1.json
├── search_knowledge_YYYY-MM-DD.json
├── search_knowledge_latest.json
└── adaptive_learning_summary_YYYY-MM-DD.md
```

每次projection寫入不可變路徑，至少包含`projection_run_id`或`input_corpus_hash + policy versions hash`。同日多次執行不得覆寫。`latest`只能是immutable projection的指標／副本，不得是唯一保存版本。

## Required CLI

```bash
uv run python -m app.research.observation_ingest --date YYYY-MM-DD
uv run python -m app.research.parameter_learning --date YYYY-MM-DD
uv run python scripts/verify_adaptive_learning.py --date YYYY-MM-DD
```

另需提供 deterministic rebuild verification，可由 verifier 子命令或獨立 script 實作：

```bash
uv run python scripts/verify_adaptive_learning.py --date YYYY-MM-DD --rebuild-ledger
```

## Repo-level impact map

### 現行資料流

```text
config/regime_research_contract.json ──┐
app/research/map_contract.py ──────────┼─→ parameter / coverage identities
scripts/run_autonomous_research.py ────┼─→ topic selection + matrix commands
scripts/run_backtest_strategy_matrix.py┼─→ candidate/baseline matrix artifacts
                                      ├─→ autonomous run artifact
                                      ├─→ run_history.json (bounded manager history)
scripts/backfill_research_map_run_history.py
                                      └─→ run_history.jsonl (mixed evidence)
                                               ↓
                         Fog Map / inventory / progress / weekend replay consumers
```

### Target Card A 資料流

```text
Research Parameter Catalog + schema definitions
                ↓
versioned TrialSpec / Intent
                ↓
existing autonomous + strategy matrix execution
                ↓
terminal immutable RunReceipt (success and failure)
                ↓
DuckDB Research Ledger ← one-time legacy migration manifest
                ↓
eligibility / failure / matched-learning projections
                ↓
search knowledge + PM summary
```

### Source ownership / likely impact

| Concern | Current owner / consumer | Card A target | Mutation timing |
|---|---|---|---|
| Base/V2 coverage dimensions | `app/research/map_contract.py` | Parameter Catalog projection | Contract slice first；consumer cutover later |
| Formal executable parameters / sealed split | `config/regime_research_contract.json`、`scripts/run_autonomous_research.py` | Catalog + lineage authority | Preserve semantics；do not weaken gates |
| Matrix metrics and episode evidence | `scripts/run_backtest_strategy_matrix.py` | Receipt observation source | Add native receipt inputs/outputs only after schema gate |
| Autonomous attempt lifecycle | `scripts/run_autonomous_research.py` | Intent/run/receipt producer | Add terminal receipt path；do not change selection |
| Manager history | `artifacts/autonomous_research/run_history.json` consumers | Operational compatibility projection | Deprecate as evidence authority |
| Mixed research history | `run_history.jsonl` producers/consumers | One-time migration input / compatibility projection | Stop new canonical writes after cutover |
| Legacy backfill | `scripts/backfill_research_map_run_history.py` + daily shell | Migration-only command | Remove from normal daily path only after native receipt parity |
| Daily owner | `scripts/run_daily_research_quota.sh` | Same scheduler | No adaptive queue；only replace backfill with verified receipt ingestion after checkpoint |
| Fog Map | `app/research/fog_map_domain.py`、builder/verifiers | Future ledger projection consumer | Card A preserves output contract；UI unchanged |
| Weekend inventory | `scripts/weekend_training_common.py`、inventory/frontier scripts | Future ledger/catalog consumer | Card A records migration seam；no priority change |
| Verifiers | daily、matrix、map/backfill verifiers | Receipt/ledger/rebuild gates | Extend before authority cutover |

### Known direct consumers of legacy history

至少包含：

- Research Fog Map builder/verifier。
- Weekend inventory、representative replay與training common。
- Research campaign progress。
- Liquidity replay batch/stage2與其 verifiers。
- PM research harness / handoff / status reporting。
- 5913 effectiveness review。

Implementation 不得用一次全域替換改完。每個 consumer 必須先分類為：

- operational history consumer。
- coverage projection consumer。
- evidence/learning consumer。
- verification/audit consumer。

只有 evidence/learning consumer 在 Card A 必須切到 ledger；其他 consumer可保留 compatibility projection，但不得再宣稱 legacy history 是 canonical evidence。

## Architecture friction to remove

1. `combo_id` 同時承擔 coverage、execution與observation identity。
2. Parameter grid 分散在 Fog Map、formal contract與runner profiles。
3. `run_history.json` 與 `.jsonl` 粒度、retention與authority不同，卻同名為 history。
4. 正常 daily flow依賴事後 backfill推測 research evidence。
5. Fog Map、weekend queue與autonomous manager各自維護局部狀態。
6. Legacy artifact copies可能重複增加表面 evidence rows。

Card A 的修正原則是建立單一 spine與可重建 projections，不再新增永久雙軌。

## Requirements traceability

### 使用者故事 <!-- US-001 -->

身為 NEW-TOP10 的長期維運者，我要讓所有研究定義、執行事實、lineage、eligibility 與 learning 都能由單一可重建骨架解釋，以免系統持續累積重複 identity、事後猜測與無法稽核的研究結論。

### Functional requirements

- **FR-001**：Canonical identities分離且可追溯，legacy `combo_id`不再是新主鍵。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：TrialSpec canonicalization版本化。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：每個 attempt，不論成功或失敗，都產 immutable terminal receipt。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：Receipt保存 requested與executed及所有resolution差異。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：Sealed status三態且 fail closed。 <!-- FR-005 traces_to: US-001 -->
- **FR-006**：建立單一 versioned Parameter Catalog，禁止新增分散 authority。 <!-- FR-006 traces_to: US-001 -->
- **FR-007**：DuckDB ledger可由canonical corpus完整重建。 <!-- FR-007 traces_to: US-001 -->
- **FR-008**：Ingestion idempotent且正常路徑incremental。 <!-- FR-008 traces_to: US-001 -->
- **FR-009**：Legacy sources透過immutable manifest一次性遷移與分類。 <!-- FR-009 traces_to: US-001 -->
- **FR-010**：Eligibility狀態與policy provenance可稽核。 <!-- FR-010 traces_to: US-001 -->
- **FR-011**：只以matched、independent evidence做parameter learning。 <!-- FR-011 traces_to: US-001 -->
- **FR-012**：所有projection保存policy/version provenance。 <!-- FR-012 traces_to: US-001 -->
- **FR-013**：舊history authority有明確deprecation與removal condition。 <!-- FR-013 traces_to: US-001 -->
- **FR-014**：不改production ranking/model/promotion，不消費sealed evidence調參。 <!-- FR-014 traces_to: US-001 -->

### Success criteria

- **SC-001**：刪除DuckDB後重建，key sets、counts與projection hashes一致。 <!-- SC-001 traces_to: FR-007, FR-008, FR-012 -->
- **SC-002**：新run從attempt開始到terminal status不依賴隔日filesystem scan。 <!-- SC-002 traces_to: FR-003, FR-013 -->
- **SC-003**：Receipt能精確重建requested/executed差異。 <!-- SC-003 traces_to: FR-004 -->
- **SC-004**：sealed或unknown lineage無法進入adaptive-eligible learning。 <!-- SC-004 traces_to: FR-005, FR-010 -->
- **SC-005**：重 ingest不增加observation或evidence weight。 <!-- SC-005 traces_to: FR-008 -->
- **SC-006**：方向、flat、peak、basin與interaction只由matched evidence建立。 <!-- SC-006 traces_to: FR-011 -->
- **SC-007**：每項learning可回答使用哪個corpus、catalog與policy version。 <!-- SC-007 traces_to: FR-002, FR-006, FR-012 -->
- **SC-008**：舊history只作legacy/compatibility，不再是新研究canonical evidence。 <!-- SC-008 traces_to: FR-009, FR-013 -->
- **SC-009**：production ranking、model、signals與promotion均無變更。 <!-- SC-009 traces_to: FR-014 -->

### Acceptance scenarios

1. **Given** 一個legacy `combo_id`可映射到coverage、trial與observation，When執行migration，Then三種canonical identity各自產生且保留mapping。 <!-- AS-US001-01 traces_to: FR-001 -->
2. **Given** 相同TrialSpec content與固定canonicalization version，When重複normalize，Then產生相同hash；版本改變時可辨識原因。 <!-- AS-US001-02 traces_to: FR-002 -->
3. **Given** attempt成功、失敗、pre-execution reject或cancel，When進入terminal state，Then均有immutable receipt。 <!-- AS-US001-03 traces_to: FR-003 -->
4. **Given** runner調整profile或展開matrix，When寫receipt，Then requested與executed及resolution events完整可查。 <!-- AS-US001-04 traces_to: FR-004 -->
5. **Given** sealed或無法證明非sealed的lineage，When執行eligibility，Then分別為sealed-only或invalid且不能學習。 <!-- AS-US001-05 traces_to: FR-005 -->
6. **Given** Parameter Catalog，When產生coverage/executable/adjacency projection，Then不需新增另一份parameter authority。 <!-- AS-US001-06 traces_to: FR-006 -->
7. **Given** immutable corpus與空DuckDB，When執行rebuild，Thenledger與projection結果可重現。 <!-- AS-US001-07 traces_to: FR-007 -->
8. **Given** 相同receipt、copy與第二次ingest，When執行incremental ingestion，Then不增加observation或evidence weight。 <!-- AS-US001-08 traces_to: FR-008 -->
9. **Given** legacy artifacts/history，When執行一次性migration，Then每筆source有manifest、parser version與分類理由。 <!-- AS-US001-09 traces_to: FR-009 -->
10. **Given** 任一observation，When產生eligibility，Thenpolicy version、input IDs與reason codes可稽核。 <!-- AS-US001-10 traces_to: FR-010 -->
11. **Given** 不同topic/regime/dataset或多個parameters同時改變，When執行learning，Then不得形成matched direction evidence。 <!-- AS-US001-11 traces_to: FR-011 -->
12. **Given** 相同receipt corpus與不同policy version，When重算projection，Then兩版結果均保留完整provenance。 <!-- AS-US001-12 traces_to: FR-012 -->
13. **Given** native receipt parity通過，When切換正常daily path，Thenlegacy history只保留compatibility/migration用途並有removal contract。 <!-- AS-US001-13 traces_to: FR-013 -->
14. **Given** Card A全部CLI與tests執行，When比較production guards與檔案hash，Thenranking/model/signals/promotion無變更。 <!-- AS-US001-14 traces_to: FR-014 -->

## Implementation slices

### `RSL-SLICE-001`｜Contract fixtures and trace preflight

- `status`: COMPLETED（2026-08-14；schema gate GO）
- `traces_to`: `FR-001`, `FR-002`, `FR-003`, `FR-004`, `FR-006`, `FR-012`
- `blocked_by`: none
- `frontier`: yes
- 交付：TrialSpec、Intent、RunReceipt、Parameter Catalog、migration manifest與projection provenance的versioned JSON examples/schema；建立trace validator。
- 驗證：schema fixtures覆蓋success、failure、unknown lineage、requested/executed mismatch；trace preflight無dangling IDs。
- 可能檔案：`app/research/contracts.py`、`config/research_parameter_catalog.json`、`tests/test_research_spine_contracts.py`。
- Gate：`schema_gate`。

### `RSL-SLICE-002`｜Canonical identity and catalog authority cutover

- `status`: COMPLETED（2026-08-14；recompute gate GO）
- `traces_to`: `FR-001`, `FR-002`, `FR-006`
- `blocked_by`: `RSL-SLICE-001`
- 交付：deterministic normalization/hash；從catalog產base/executable/coverage/validation-profile projections；舊definitions改為generated compatibility surface，不再author values。
- 驗證：canonicalization version測試、property fixtures、現行81×112 coverage語意與formal executable parameter semantics無意外漂移。
- 可能檔案：`app/research/identity.py`、`app/research/parameter_catalog.py`、`app/research/map_contract.py`、targeted tests。
- Gate：`recompute_gate`。

### `RSL-SLICE-003`｜Immutable terminal receipt producer

- `status`: COMPLETED（2026-08-14；schema/cmd gate GO；adversarial re-review GO）
- `traces_to`: `FR-003`, `FR-004`, `FR-005`, `FR-014`, `SC-002`, `SC-003`
- `blocked_by`: `RSL-SLICE-001`, `RSL-SLICE-002`
- 交付：既有autonomous/matrix execution在attempt開始時建立intent/run identity，所有terminal path原生寫receipt；requested/executed resolution完整。
- 驗證：成功、runner failure、pre-execution rejection與matrix expansion fixtures都有receipt；既有選題順序不變。
- 可能檔案：`scripts/run_autonomous_research.py`、`scripts/run_backtest_strategy_matrix.py`、receipt writer與targeted tests。
- Gate：`cmd_gate` + `schema_gate`。

### Checkpoint 1｜Native source authority

- `status`: GO（2026-08-14；176 passed + 8 subtests；`git diff --check`通過）

必須確認：

- 新receipt corpus已能獨立描述attempt全生命週期。
- requested/executed差異無法被靜默吞掉。
- sealed/unknown fail closed。
- 尚未修改queue、scheduler owner或production。

Checkpoint 1 未通過，不得開始ledger migration。

### `RSL-SLICE-004`｜Rebuildable DuckDB ledger and incremental ingest

- `status`: COMPLETED（2026-08-14；recompute gate GO；adversarial re-review GO）
- `traces_to`: `FR-007`, `FR-008`, `FR-012`, `SC-001`, `SC-005`
- `blocked_by`: `RSL-SLICE-003`
- 交付：receipt-first ingest、normalized tables、content-addressed provenance、incremental cursor與rebuild command。
- 驗證：fresh DB、second ingest、copied artifact與deleted/rebuilt DB產生相同key sets/counts/hashes。
- 可能檔案：`app/research/observation_ingest.py`、ledger schema/migrations、`tests/test_research_ledger.py`。
- Gate：`recompute_gate`。

### `RSL-SLICE-005`｜One-time legacy migration and reconciliation

- `status`: COMPLETED（2026-08-14；recompute gate GO；adversarial re-review GO）
- `traces_to`: `FR-009`, `FR-010`, `FR-013`, `SC-008`
- `blocked_by`: `RSL-SLICE-004`
- 交付：legacy discovery、content hashing、migration manifest、classification funnel與current repo reconciliation。
- 驗證：source rows→artifact rows→unique migrated observations→eligibility states漏斗可重跑；topic-level、unsupported、sealed/unknown不得升格。
- 可能檔案：migration module/script、legacy backfill compatibility code、targeted tests。
- Gate：`recompute_gate`。

### `RSL-SLICE-006`｜Native daily receipt ingestion cutover

- `status`: COMPLETED（2026-08-14；cmd/recompute gate GO；adversarial re-review GO）
- `traces_to`: `FR-003`, `FR-013`, `SC-002`, `SC-008`
- `blocked_by`: `RSL-SLICE-004`, `RSL-SLICE-005`
- 交付：daily正常路徑在run後驗證/ingest原生receipt；事後legacy backfill退出正常path或明確只作legacy migration mode。
- 驗證：synthetic daily run不呼叫filesystem backfill也能產完整receipt與ledger rows；既有scheduler仍唯一且選題不變。
- 可能檔案：`scripts/run_daily_research_quota.sh`、daily verifier、backfill script mode guards、tests。
- Gate：`cmd_gate`。

### Checkpoint 2｜Authority cutover

- `status`: ENGINEERING_GO / LIVE_ACTIVATION_NO_GO（2026-08-14；native batch parity與Fog compatibility projection通過；真實207,871 records rebuild約15秒。主機free 19 GiB低於容量安全線，未部署或重載排程）

必須確認：

- DuckDB可刪除重建。
- 新run不再需要隔日backfill。
- Legacy history consumers已分類。
- Compatibility projection存在明確owner/removal condition。
- Fog Map與weekend outputs尚未被破壞。

Checkpoint 2 未通過，不得建立learning projection。

### `RSL-SLICE-007`｜Eligibility and failure projections

- `status`: COMPLETED（2026-08-14；schema/recompute gate GO；adversarial re-review GO）
- `traces_to`: `FR-005`, `FR-010`, `FR-012`, `SC-004`, `SC-007`
- `blocked_by`: `RSL-SLICE-006`
- 交付：versioned eligibility與failure classifier，所有排除帶structured reason與impact counts。
- 驗證：eligible、legacy、sealed、topic-level、unsupported、invalid-lineage fixtures；sealed/unknown不能被任何learning query讀取。
- 可能檔案：`app/research/eligibility.py`、`app/research/failure_classification.py`、tests。
- Gate：`schema_gate` + `recompute_gate`。

### `RSL-SLICE-008`｜Matched parameter learning

- `status`: COMPLETED（2026-08-14；recompute gate GO；adversarial re-review GO）
- `traces_to`: `FR-011`, `FR-012`, `SC-006`, `SC-007`
- `blocked_by`: `RSL-SLICE-007`
- 交付：matched contrasts、independent evidence counting、direction/flat/peak/basin/interaction/regime-aware findings。
- 驗證：higher/lower、none categorical、drawdown direction、risk-return tradeoff、flat、interior/sharp peak、adjacent robust basin、conditional effect、regime separation與single-lineage不可HIGH。
- 可能檔案：`app/research/parameter_learning.py`、config thresholds、targeted tests。
- Gate：`recompute_gate`。

### `RSL-SLICE-009`｜Knowledge artifacts, PM summary and final verifier

- `status`: COMPLETED（2026-08-14；acceptance gate GO；adversarial re-review GO）
- `traces_to`: 所有 `FR-*` 與 `SC-*`
- `blocked_by`: `RSL-SLICE-008`
- 交付：versioned search knowledge、PM summary、Q1–Q13、rebuild verifier、before/after authority document。
- 驗證：required CLIs、targeted tests、full pytest、`git diff --check`、changed-file audit、production file hash guard。
- 可能檔案：`scripts/verify_adaptive_learning.py`、artifact renderers、`docs/evidence/...`。
- Gate：`recompute_gate` + acceptance gate。

## Current frontier

`RSL-SLICE-001`～`RSL-SLICE-009` 工程驗收完成。Card B未授權；live activation需先通過storage capacity gate。

## Required tests

至少覆蓋：

- Canonicalization版本與stable identity。
- Eligible observation accepted。
- Legacy observation diagnostic-only。
- Sealed與unknown evidence rejected。
- Topic-level row rejected for parameter learning。
- Unsupported/rule-pruned不是failure或dead region。
- Idempotent與incremental ingestion。
- DuckDB delete-and-rebuild parity。
- Every terminal attempt has receipt。
- Requested/executed差異完整且可驗。
- Matched pair higher/lower direction。
- `none` baseline categorical。
- Drawdown direction correct。
- Risk-return tradeoff。
- Interior peak、flat、sharp peak、adjacent robust basin。
- Interaction conditional effect。
- Regime separation與global-not-estimable。
- Projection policy/version provenance。
- No production write。

## Full validation

每個slice先跑targeted tests。Checkpoint與完工至少執行：

```bash
uv run pytest -q <research-spine-targeted-tests>
uv run python -m app.research.observation_ingest --date <test-date>
uv run python -m app.research.parameter_learning --date <test-date>
uv run python scripts/verify_adaptive_learning.py --date <test-date>
uv run python scripts/verify_adaptive_learning.py --date <test-date> --rebuild-ledger
uv run pytest -q
git diff --check
```

Full pytest failure必須分為 `PRE_EXISTING` 與 `INTRODUCED_BY_THIS_CARD`，並以相同base/input重現。

## PM completion questions

完工必須以實際repo evidence回答：

1. Source history records有多少？
2. Matrix artifacts與raw scenario rows有多少？
3. Unique ingested observations有多少？
4. `ADAPTIVE_ELIGIBLE`有多少？
5. `LEGACY_DIAGNOSTIC_ONLY`有多少？
6. `SEALED_VALIDATION_ONLY`有多少？
7. Unique independent evidence units與matched contrasts有多少？
8. 哪些參數已有方向性，哪些可能太高／太低？
9. 哪些參數不能判或為low sensitivity？
10. 哪些存在interior peak、robust basin或sharp peak？
11. Evidence是否主要集中於RISK_OFF？
12. 哪些結論禁止泛化到其他regime？
13. 刪除DuckDB後是否完整重建且projection hashes一致？
14. 新run是否不再需要filesystem backfill推測lineage？
15. 本卡是否有production ranking/model/promotion變更？答案必須為 `NO`。

## Compatibility bridge removal contract

任何temporary dual-read、legacy adapter或compatibility projection必須在實作時登記：

- owner。
- consumers。
- reason。
- removal condition。
- removal test。
- latest removal card（最遲Runner Integration V1完成）。

沒有removal contract的bridge不得合併。

## Rollback

- Immutable receipts與migration manifest只能新增，不覆寫既有source artifacts。
- DuckDB可刪除重建，不是rollback authority。
- Authority cutover前保留舊consumer compatibility；cutover失敗回到舊read path，但不得把新receipt刪除或改寫。
- 本卡不變更production，因此rollback不涉及model/ranking復原。

## Definition of Done

只有以下全部成立才可完成：

- Canonical identity與canonicalization version已落地。
- Parameter Catalog成為新Research Spine唯一新增parameter authority。
- 所有新attempt成功或失敗均有immutable terminal receipt。
- Requested與executed差異完整可查。
- Sealed/unknown lineage fail closed。
- DuckDB可刪除並deterministically rebuild。
- Legacy migration有immutable manifest與完整分類漏斗。
- 新run不依賴隔日filesystem backfill。
- Eligibility、failure與learning projection均有policy/version provenance。
- Matched learning不受copies/backfill/repeated projection灌水。
- PM summary能回答實際observation landscape。
- Queue、scheduler selection、Fog Map UI、Optuna、refinement與production均未擴入本卡。
