---
id: REPAIR-TSKG-01-repair
card: REPAIR-TSKG-01
chain_id: TSKG-01
status: DELIVERED_CANDIDATE
base_candidate_sha: fad395589c90254ffbf4f0e7292a36920d019298
review_commit: 7ddb092b449af801a4c86fb051a7c98561b1a29b
repair_card_commit: fecc175
---

# REPAIR-TSKG-01 Repair Evidence

本文件只記錄 F-01～F-07 的 candidate successor 修補與靜態 contract verification。沒有執行任何 project runtime、API、database、benchmark、外部網站或服務；也沒有修改 reviewer evidence。以下 disposition 是 Repair 線的交付狀態，不宣稱 reviewer finding 已 resolved、accepted 或 integrated。

## Inputs、scope 與共同驗證語意

- Base candidate：`fad395589c90254ffbf4f0e7292a36920d019298`
- Review commit（唯讀）：`7ddb092b449af801a4c86fb051a7c98561b1a29b`
- Repair contract：`fecc175`（只提供修復契約）
- Allowlist：Spec、原 TSKG trace/verification、本 evidence、Repair 卡 status/Result，共五檔。
- `CONTRACT_PASS/RUNTIME_NOT_RUN`：文件提供唯一可判定 invariant 與 golden/negative case，但尚未以 runtime 實作執行。
- `PARTIAL/BLOCKED`／`BLOCKED_FOR_SLO_ACCEPTANCE`：保留 blocker，不可 false-positive PASS。

## F-01 P1 — single canonical supply/customer fact

### Finding / before

原 matrix 同時允許 `SUPPLIES_TO(A,B)` 與 `CUSTOMER_OF(B,A)` 成為不同 canonical claims，和 SRS-REL-01 的 single fact 原則衝突；API 沒有跨 customer/supplier label 去重契約。

### Change / after

- `SUPPLIES_TO(supplier,customer)` 是唯一 canonical predicate。
- `SUPPLIED_BY`、`HAS_CUSTOMER`、`CUSTOMER_OF` 只能是 legacy input normalization 或 query-derived role labels，不得各自 promotion。
- company `customers` 只取 outgoing supply facts，`suppliers` 只取 incoming supply facts；response 以 fact/claim/time tuple 去重，相容 multi-source assertions 聚合 evidence。

### Schema invariant

canonical fact key 只使用 canonical predicate/direction/endpoints/identity qualifiers；原 label/endpoints 只留 assertion provenance。每一 derived view 必須回 canonical type、`canonical_fact_id`、`source_claim_id` 與 derivation metadata。

### Golden / negative contract cases

- Golden：`A supplies B`、`B is supplied by A`、`A has customer B`、`B is customer of A` → 同一 `SUPPLIES_TO(A,B)` fact 與一個 compatible claim；API 不重複 item。
- Negative：方向不足不得猜測；canonical store 出現 legacy predicate、同一 fact 因 query label 重複、或無 evidence promotion，全部 reject/fail loud。

### Verification disposition

`CONTRACT_PASS/RUNTIME_NOT_RUN`；證據：Spec AC-03、§6.4、TDS-RELATIONSHIP；verification §3 F-01。

## F-02 P1 — conflict/resolution lineage

### Finding / before

原 schema 以含 qualifiers/valid interval 的 semantic key 表示 claim，無 stable fact、assertion/version、conflict members 或 resolution decision metadata，無法 deterministic 分組與重建 known-at 歷史。

### Change / after

- 分離 `CanonicalFact`、`SourceAssertion/AssertionVersion`、`RelationshipClaim` identity。
- 新增 `ConflictSet` 與 `ResolutionDecision`，固定 member、decision evidence、actor/time/policy、selected/rejected/superseded 與 superseding-decision lineage。
- 定義 candidate/promotion/conflict/selection/rejection/supersession/invalidation state transitions；transition 只能新增 system-time row，不覆寫歷史。

### Schema invariant

同 conflict set members 必須共用 `canonical_fact_id`；decision referenced claims 必須是 members，selected/rejected/superseded 集合不得重疊；SELECT 必須有 selected、evidence、decided_by/at、policy version。

### Golden / negative contract cases

- Golden `TDS-CONFLICT-01`：C1/C2→CS1 OPEN→D1 SELECT C2/REJECT C1；`known_at=t0` 重建原 OPEN conflict，`known_at=t1` 回完整 decision；再次 t0 query canonical JSON byte-equivalent。
- Negative：跨 fact member、缺 decision evidence/actor/policy、集合重疊、直接覆寫 prior decision，全部 reject。

### Verification disposition

`CONTRACT_PASS/RUNTIME_NOT_RUN`；證據：Spec §6.1–6.2、AC-04、TDS-CONFLICT；verification §3 F-02。

## F-03 P1 — temporal wire contract

### Finding / before

原 `valid_from/to` 只說 open interval，沒有 JSON discriminator、inclusion、UNKNOWN/UNBOUNDED 差異、system current 唯一表示或 illegal/empty 判定。

### Change / after

每個 endpoint 固定 `{kind: KNOWN|UNKNOWN|UNBOUNDED}`：KNOWN 必須 UTC timestamp + inclusive boolean；其他 kind 禁止兩欄。business current 只能使用 UNBOUNDED end；UNKNOWN 不得冒充 current。system 不接受 UNKNOWN，current row 只能以 UNBOUNDED end 表示。

### Schema invariant

KNOWN/UNKNOWN/UNBOUNDED 的欄位組合封閉；business reversed/empty 與非法額外欄位 reject；system interval 固定 `[KNOWN inclusive, KNOWN exclusive|UNBOUNDED)`，相同 identity 只能一個 current row。

### Golden / negative contract cases

- Golden：known range、unknown start、unknown end、all-time、closed history 五類都須 parser→authority→projection→API exact semantic round-trip。
- Negative：reversed、exclusive equal、UNKNOWN system end、KNOWN 缺 timestamp/inclusion、UNBOUNDED 帶 timestamp，全部不得進 authority。

### Verification disposition

`CONTRACT_PASS/RUNTIME_NOT_RUN`；證據：Spec §6.3、TDS-TIME；verification §3 F-03。

## F-04 P1 — verification integrity

### Finding / before

原 verification 將章節存在、ID count 與未執行的核心 contract 標為 PASS，沒有 F-01～F-03 invariants/cases。

### Change / after

verification 改為逐 finding 的 invariant + golden/negative matrix；所有 behavioral items 標 `CONTRACT_PASS/RUNTIME_NOT_RUN`。31/31 與 14/14 明確只表示 candidate internal set/trace coverage，不能證明核心語意、runtime 或 baseline completeness。

### Schema invariant

任何未執行 runtime 的 row 不得單獨標 `PASS`；open provenance/performance blocker 必須顯示 blocked 狀態。

### Golden / negative contract cases

- Golden：每個 F-01～F-03 row 可直接定位 spec invariant/case 與未執行狀態。
- Negative：只因章節存在、ID set equal 或計數完整就推論 ontology/round-trip/runtime PASS，屬 evidence failure。

### Verification disposition

`CONTRACT_PASS`（文件靜態自檢）／仍待 reviewer re-review；證據：原 verification §3–6、Repair evidence 本文件。

## F-05 P2 — confidence API

### Finding / before

public graph route 的 `min_confidence` 會把 optional、未校準的 extraction provenance 當 truth filter，可能排除 deterministic/human claims 或隱藏 conflicts。

### Change / after

移除 public confidence filter；truth 可用性只依 claim state、promotion policy、evidence completeness 與 review status。confidence 若因 provenance scope 回傳，必須伴隨 extractor/version，且不可跨 extractor 排序／比較。

### Schema invariant

public route schema 不得含 `min_confidence`／`min_extraction_confidence`；ACTIVE deterministic/human `null` confidence 不得被排除，CONFLICTED claim 不得由 confidence 隱藏。

### Golden / negative contract cases

- Golden：mixed deterministic/human/LLM response 只按 state/policy/evidence/review filter。
- Negative：null confidence 被排除、跨 extractor threshold、reviewed low-confidence 被降為 false、conflict 被 score 隱藏，全部 contract reject。

### Verification disposition

`CONTRACT_PASS/RUNTIME_NOT_RUN`；證據：Spec §9.2、TDS-API-CONFIDENCE；verification §3 F-05。

## F-06 P2 — baseline provenance

### Finding / before

原 trace 只有「父對話」文字，沒有 immutable source locator、canonicalization/digest，且 31/31/14/14 容易成為 candidate 自我證明。

### Change / after

- 固定 source task `019f708e-2c20-7262-8102-6144674d54ce`、turn `019f708e-3fb9-7673-a504-457b8ea06374`、user item `item-1` 與 content prefix。
- 固定 canonicalization：user-item text；CRLF→LF；Unicode NFC；尾端一個以上 newline→恰好一個 LF；UTF-8 bytes；SHA-256。
- 14 個 BL disposition 全部連到原始 section label；internal SRS/BL coverage 與 independent baseline reproducibility 分開。
- 不新增 baseline 全文副本。

### Schema invariant

independent baseline coverage 必須同時具有 immutable locator、合規 canonical digest 與逐 original-section comparison；缺一不可。

### Golden / negative contract cases

- Golden：另一環境依 locator/canonicalization 產生相同 digest，再核對 14 BL section mappings。
- Negative：使用不同 canonicalization digest、只憑 31/31 或 candidate 自建 BL set 宣稱 baseline complete，全部不成立。

### Verification disposition

`PARTIAL/BLOCKED`：`baseline_sha256=PENDING_REPRODUCIBLE_CAPTURE`。主線回報同一 hash tooling blocker連續三次失敗，依停損不得第四試；本線先前取得的不同 canonicalization digest 不符合契約，未採用。是否可 `GO_WITH_NOTES` 由 reviewer 決定。此 blocker 不影響 F-01～F-05 contract 修補。

## F-07 P2 — performance acceptance

### Finding / before

原 benchmark 只有最低 counts/method，未固定 generator seed、topology/distribution、expected payload、cache state、measurement tool contract；reference environment 未核准卻被 verification 標 PASS。

### Change / after

新增 `TSKG-BENCH-v1`：固定 generator contract/seed、exact entities/claims/evidence distribution、topology manifest、query set/expected item+byte/hash manifest、WARM_CACHE_HIT state、measurement contract與完整 run manifest。OQ-PERF-01 明確加入 SLC-07 performance blocking edges。

### Schema invariant

任一 generator/dataset/query/expected-response/cache/measurement/environment manifest 欄位或 hash 不符即不是 acceptance run；每個 measured response 必須 `cache_hit=true` 且 functional response match。

### Golden / negative contract cases

- Golden：owner-approved reference environment + immutable executable/dataset manifests 才可判定 p95/error/cache miss。
- Negative：自選 seed/topology、payload mismatch、cache miss/eviction、漏 slow/error sample、缺 reference environment，run invalid；未核准環境只能 diagnostic。

### Verification disposition

Benchmark contract `CONTRACT_PASS/RUNTIME_NOT_RUN`；SC-07/AC-12/SLC-07 performance acceptance `BLOCKED_FOR_SLO_ACCEPTANCE`，不得 PASS。證據：Spec §9.4、§13–15；verification §3 F-07。

## Final static verification record

完成修改後執行且僅執行 repo/git 靜態檢查：

- Repair parent range changed files 精確等於五檔 allowlist；review evidence、原 TSKG task card與 runtime paths未變更。
- internal SRS set：Spec/trace 31/31 且相等；只記 internal coverage。
- AC set：AC-01..AC-12；BL set：BL-01..BL-14，且逐 row 有 original section label。
- `git diff --check`：successor parent range PASS。
- post-commit `git status --porcelain=v1`：clean。

完整 successor SHA 只在交付回報提供，避免 commit 自參照。所有結果仍是 `DELIVERED_CANDIDATE`，送原 reviewer re-review。
