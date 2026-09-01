# B0 Phase 1：矩陣 authority 與維度 taxonomy

## 範圍與方法

- NEW-TOP10 固定來源：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`。
- AI Core dispatch baseline：`21801303adff285268f7646df94dc53da31a835f`。
- Issue authority：#13，版本以 `updatedAt=2026-09-01T02:25:41Z` 固定。
- `observed_at`：`2026-09-01T03:06:26Z`。
- 本文件把「可乘進 executable legal count 的參數維度」、「coverage-only 座標」與
  「TrialSpec／lineage context」分開；後兩者不得暗中乘進 `720`。

## Dimension map

| 維度／軸 | Phase-1 taxonomy | sole authoring source | authoring values / rule | executable count contribution |
|---|---|---|---|---:|
| `horizon` | numeric；ordinal Cartesian；executable | Parameter Catalog | `3, 5, 10, 20` | 4 |
| `stop_loss_pct` | numeric；ordinal Cartesian；structural choice (`null`=停用事件停損)；executable | Parameter Catalog | `null, .05, .06, .08, .10, .12` | 6 |
| `take_profit_pct` | numeric；ordinal Cartesian；structural choice (`null`=停用事件停利)；executable | Parameter Catalog | `null, .10, .15, .20, .25, .30` | 6 |
| `max_group_exposure` | numeric；ordinal Cartesian；structural choice (`null`=無族群 cap、仍受 gross exposure 限制)；executable | Parameter Catalog | `null, .25, .35, .45, .55` | 5 |
| `regime_gate` | categorical；conditional；coverage-only；unsupported executable | Parameter Catalog | 7 個 coverage values；`executable_values=[]` | 0 |
| `risk_guard` | categorical；conditional；coverage-only；unsupported executable | Parameter Catalog | 4 個 coverage values；`executable_values=[]` | 0 |
| `entry_filter` | categorical；conditional；coverage-only；unsupported executable | Parameter Catalog | 4 個 coverage values；`executable_values=[]` | 0 |
| exact `regime_scope` | categorical；dynamic/context-resolved；非 Parameter Catalog 維度 | Regime Research Contract taxonomy + TrialSpec context | exact base regime + exact family-tag set；`UNKNOWN`／transition 排除正式 evidence | 不乘入 720 |
| `research_stage`、dataset、ranking source、execution profile | conditional；dynamic/context-resolved；TrialSpec／lineage context | TrialSpec contract 與各自 authority hashes | 必填 context，不是 allowed-values matrix | 不乘入 720 |
| constrained allocation dimension | unknown / not identified | 缺 committed Parameter Catalog authority | 沒有 sum/floor/ceiling 或 allocation-vector 維度 | 不得推算 |
| larger full product universe | unknown | 缺 committed canonical dimension source | `SOURCE_INVENTORY_NOT_PROVEN` | 不得推算 |

## Material claims

### B0P1-AUTH-001

```yaml
claim_id: B0P1-AUTH-001
claim: config/research_parameter_catalog.json 是七個現行 stock-research parameter 欄位的唯一 allowed-values authoring authority；regime contract、runner defaults、validation profiles 與 legacy map 只能是 catalog-derived projection 或 reader。
classification: SOLE_AUTHORITY_CONFIRMED
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/research_parameter_catalog.json; app/research/parameter_catalog.py; config/regime_research_contract.json; docs/tasks/2026-08-14_CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1.md
source_range_or_section: catalog lines 1-6,127-188; parameter_catalog.py lines 1-38,87-156,171-198; regime contract lines 65-75; Card A lines 130-148
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: GOVERNING_COMMITTED_CONTRACT_AND_IMPLEMENTATION
conflict_with: none
implication: B0 不得建立第二份 allowed-values authority，也不得以 runner CLI、Fog Map 或 legacy projection 擴張 legal matrix。
open_question: none for the seven currently declared fields
owner: Parameter Catalog owner
```

### B0P1-AUTH-002

```yaml
claim_id: B0P1-AUTH-002
claim: 唯一已證明 executable 的 Cartesian 維度是 horizon、stop_loss_pct、take_profit_pct、max_group_exposure；其 cardinalities 分別為 4、6、6、5，且後三者的 null 是明確 structural-off choice，不是缺值。
classification: EXECUTABLE_NUMERIC_ORDINAL_CARTESIAN_WITH_STRUCTURAL_NULL
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/research_parameter_catalog.json; app/research/parameter_catalog.py
source_range_or_section: catalog lines 7-74; parameter_catalog.py lines 16-21,87-110,159-168
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CANONICAL_CATALOG
conflict_with: none
implication: 只有這四個維度可進入現行 executable legal count；null 必須保留其產品語意。
open_question: 是否存在尚未提交到 catalog 的其他股票參數維度
owner: Parameter Catalog owner
```

### B0P1-AUTH-003

```yaml
claim_id: B0P1-AUTH-003
claim: regime_gate、risk_guard、entry_filter 是 catalog-declared categorical coverage coordinates，但 execution_support=CONTRACT_DEPENDENT、executable_values 為空且 TrialSpec/receipt validators 要求以 null NOT_EXECUTED sentinel 保存。
classification: CATEGORICAL_CONDITIONAL_COVERAGE_ONLY_UNSUPPORTED_EXECUTION
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/research_parameter_catalog.json; app/research/contracts.py
source_range_or_section: catalog lines 75-125; contracts.py lines 281-317,761-809
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CANONICAL_CATALOG_AND_VALIDATOR
conflict_with: none
implication: 7×4×4 coverage expansion不能被當成 executable multiplier，也不能用 default coordinate 補造已執行事實。
open_question: 哪一份未來 contract 會把其中任何維度轉為 executable，以及其限制為何
owner: Parameter Catalog owner / future contract owner
```

### B0P1-AUTH-004

```yaml
claim_id: B0P1-AUTH-004
claim: exact regime、research stage、dataset、ranking source 與 execution profile 是 TrialSpec／lineage context；它們限制或解析一次 execution，但目前不是 catalog Cartesian dimension。
classification: DYNAMIC_CONTEXT_RESOLVED_NON_MATRIX_AXIS
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/regime_research_contract.json; app/research/contracts.py; docs/tasks/2026-08-14_CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1.md
source_range_or_section: regime contract lines 15-64,136-160; contracts.py lines 281-320; Card A lines 150-165
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CANONICAL_TRIALSPEC_AND_REGIME_CONTRACT
conflict_with: none
implication: C0 必須把這些 context 視為 replay 成本／資料範圍條件，而非任意乘進矩陣大小。
open_question: 每個 exact regime 可用 episode/ranking-date coverage 與其成本分布
owner: TrialSpec / lineage authority owners
```

### B0P1-AUTH-005

```yaml
claim_id: B0P1-AUTH-005
claim: 現行 catalog 沒有允許 dynamic execution 的參數，也沒有 constrained-allocation vector；max_group_exposure 只是單一 scalar cap，不能推導出 sum-to-100、floor、ceiling 或 pairwise-weight-transfer 空間。
classification: NO_COMMITTED_DYNAMIC_OR_CONSTRAINED_ALLOCATION_DIMENSION
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/research_parameter_catalog.json; docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: catalog lines 7-125 (dynamic_execution_allowed=false for all dimensions); backlog lines 444-458
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CANONICAL_CATALOG_AND_BACKLOG_BOUNDARY
conflict_with: any Trace-derived stock allocation rule
implication: Phase 1 必須拒絕從 Trace 的 15 strategies、allocation floor 或 1,961,256 外推股票矩陣。
open_question: 是否有 owner-approved、尚未提交的股票 allocation dimension；若有，必須先成為 catalog authority
owner: Owner / Parameter Catalog owner
```

### B0P1-AUTH-006

```yaml
claim_id: B0P1-AUTH-006
claim: parameter_learning 與 adaptive_shadow_queue 只消費 catalog values、eligible observations、matched contrasts 與 policy，產生 learning/priority shadow projections；它們不是參數值域或 execution authority。
classification: DERIVED_PROJECTION_NOT_AUTHORITY
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/parameter_learning.py; app/research/adaptive_shadow_queue.py; docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: parameter_learning.py lines 31-50,300-358,482-505; adaptive_shadow_queue.py lines 238-282,285-345,426-518; backlog lines 173-183,201-212
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: COMMITTED_DERIVED_PROJECTION_BOUNDARY
conflict_with: none
implication: adaptive evidence可供未來 B0-P2 研究，但不能在 Phase 1 擴張 legal matrix 或取得 queue/runner authority。
open_question: Phase 2 是否准入、以及哪些 measured gaps 值得 adaptive research
owner: BC-CP1 Integrator / Owner
```

### B0P1-AUTH-007

```yaml
claim_id: B0P1-AUTH-007
claim: legacy coverage grid 的 81 base coordinates、112 coverage multiplier 與 9,072 expanded coordinates 是 compatibility/Fog Map coverage identities，不是 canonical executable TrialSpec count；legacy combo_id 也不是新 canonical identity。
classification: COVERAGE_IDENTITY_NOT_EXECUTABLE_IDENTITY
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/parameter_catalog.py; tests/test_research_parameter_catalog_projection.py; docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: parameter_catalog.py lines 56-84; test lines 31-39; backlog lines 201-210
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: COMMITTED_COMPATIBILITY_CONTRACT
conflict_with: treating 9,072 as executable legal count
implication: C0 不得用 9,072 當現行 executable capacity denominator。
open_question: coverage-only coordinates 未來若 executable，需先取得哪些 contract 與 TrialSpec identity authority
owner: Parameter Catalog owner / BC-CP1 Integrator
```

## Phase-1 boundary

本 taxonomy 不決定完整 full-scan/adaptive policy，不定案 overfit guard，不建立
RegimePolicyBundle，也不准入 B1。
