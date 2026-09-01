# B0 Phase 1：精確 count／missing authority receipt

## Receipt result

```text
primary_result_code: MISSING_MATRIX_AUTHORITY
proven_executable_subspace: EXACT_COUNT_PROVEN
proven_legal_count: 720
larger_committed_legal_count: NOT_PROVEN
canonical_combination_identity_grain: content-addressed TrialSpec
phase_2_admission: NOT_ADMITTED
```

`MISSING_MATRIX_AUTHORITY` 指完整產品參數宇宙仍缺 authority；它不否定目前四維
executable subspace 的 `720` 已被精確證明。

## Deterministic reproduction

固定 catalog 的 executable cardinalities：

```text
horizon             = 4
stop_loss_pct       = 6
take_profit_pct     = 6
max_group_exposure  = 5
invalid rules       = 0

4 × 6 × 6 × 5 = 720
```

唯讀 `jq` characterization 直接從固定 catalog 讀得 `4,6,6,5` 並以乘積重算為
`720`；未載入 market data、未執行 replay、未建立 campaign 或 production artifact。

## Material claims

### B0P1-COUNT-001

```yaml
claim_id: B0P1-COUNT-001
claim: 在固定 SHA 上，四個 executable dimensions 的完整 Cartesian product 為 4×6×6×5=720，且 committed invalid_combination_rules 為空；720 是目前唯一可證明的 formal executable legal count。
classification: EXACT_COUNT_PROVEN
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/research_parameter_catalog.json; config/regime_research_contract.json; app/research/parameter_catalog.py
source_range_or_section: catalog lines 7-74; regime contract lines 65-127; parameter_catalog.py lines 16-21,87-110,159-168
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CANONICAL_CATALOG_PLUS_GENERATED_CONTRACT_PROJECTION
conflict_with: none
implication: C0 的 current formal matrix-size denominator 必須使用 720，而非 coverage expansion 或傳聞中的兩百萬級。
open_question: 完整產品參數宇宙是否還有尚未提交的維度或 constraints
owner: Parameter Catalog owner
```

### B0P1-COUNT-002

```yaml
claim_id: B0P1-COUNT-002
claim: regime contract 明示 parameter universe declared_complete=false、inventory_status=PARTIAL_BLOCKED_SOURCE_UNKNOWN，並以 SOURCE_INVENTORY_NOT_PROVEN 阻擋兩百萬級外推；因此整體 receipt 的 primary result 是 MISSING_MATRIX_AUTHORITY。
classification: MISSING_MATRIX_AUTHORITY
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/regime_research_contract.json; docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: regime contract lines 65-75,126-134; backlog lines 286-321,444-458
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: GOVERNING_COMMITTED_CONTRACT
conflict_with: claimed two-million-scale stock matrix
implication: 不得為得到更大 count 而捏造維度、限制、allocation semantics 或 donor product rules。
open_question: 缺失 authority 的精確內容是「完整 stock product dimension inventory、各維度 allowed values、conditional constraints 與 identity semantics」
owner: Owner / future Parameter Catalog change owner
```

### B0P1-COUNT-003

```yaml
claim_id: B0P1-COUNT-003
claim: coverage-only 7×4×4 multiplier 與 legacy 81-point coverage grid 可形成 9,072 coverage coordinates，但三個 coverage-only fields 沒有 executable values；9,072 不是 formal executable legal count。
classification: PARTIAL_COVERAGE_COUNT_NOT_EXECUTABLE_COUNT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/research_parameter_catalog.json; app/research/parameter_catalog.py; tests/test_research_parameter_catalog_projection.py
source_range_or_section: catalog lines 75-125,127-168; parameter_catalog.py lines 56-84; test lines 31-39
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CANONICAL_CATALOG_AND_COMPATIBILITY_TEST
conflict_with: treating coverage coordinate count as executable TrialSpec count
implication: coverage accounting與execution capacity必須分開。
open_question: coverage-only fields 何時、是否會取得 executable contract
owner: Parameter Catalog owner / C0 capacity owner
```

### B0P1-COUNT-004

```yaml
claim_id: B0P1-COUNT-004
claim: canonical combination identity grain 是由 normalized immutable TrialSpec content 產生的 trial_spec_id；legacy combo_id 只能留在 migration/compatibility projection，不能當新 canonical FK。
classification: CANONICAL_IDENTITY_GRAIN_ESTABLISHED
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/tasks/2026-08-14_CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1.md; app/research/contracts.py; docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: Card A lines 83-128,150-165; contracts.py lines 281-320; backlog lines 201-210
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CARD_A_CANONICAL_IDENTITY_CONTRACT
conflict_with: legacy combo_id as canonical combination identity
implication: 未來 count/generate/rank/unrank 都必須對 canonical TrialSpec semantics 保持可追溯，不可僅沿用 legacy display ID。
open_question: B1 尚未准入，canonical rank/unrank/chunk contract 未定案
owner: Research Spine owner / future B1 owner
```

### B0P1-COUNT-005

```yaml
claim_id: B0P1-COUNT-005
claim: Trace 沒有在 Phase 1 被固定為 canonical stock source；其 15 strategies、allocation、10 grids 與 1,961,256 等產品規則明確禁止偷渡，狀態為 UNPINNED_CROSS_PROJECT_DONOR。
classification: UNPINNED_CROSS_PROJECT_DONOR
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/RESEARCH_SPINE_BACKLOG.md; https://github.com/bluemaple18-home/NEW-TOP10/issues/13
source_range_or_section: backlog lines 430-458,503-521; Issue #13 sections Trace boundary and Phase 1 source scope
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: GOVERNING_BACKLOG_AND_ISSUE_BOUNDARY
conflict_with: donor-derived stock count
implication: Phase 1 count只使用 NEW-TOP10 committed stock authority。
open_question: Phase 2 若被准入，是否需要固定 Trace generic kernel source
owner: BC-CP1 Integrator / Owner
```

## Verification evidence

```text
read-only characterization:
  authority_mode = SOLE_AUTHORING_AUTHORITY
  supported_sizes = horizon:4, stop_loss_pct:6, take_profit_pct:6, max_group_exposure:5
  coverage_only = regime_gate:7/0 executable, risk_guard:4/0, entry_filter:4/0
  recomputed_product = 720
  contract_expected = 720
  invalid_combination_rules = []
  declared_complete = false
  blocked_reason = SOURCE_INVENTORY_NOT_PROVEN
```
