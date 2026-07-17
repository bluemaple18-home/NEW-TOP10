---
id: TSKG-v1.1
status: DELIVERED_CANDIDATE
type: executable-spec
card: TSKG-01
created: 2026-07-17
source: TSKG-v1.0-authoritative-parent-thread-baseline
---

# Taiwan Stock Knowledge Graph v1.1 可執行規格

## 1. 文件定位與規範用語

本文件把父對話提供的 TSKG v1.0 設計基線轉為可派工、可測試、可追溯的 v1.1 契約。本卡只定義 WHAT、邊界、資料與介面契約、驗收方法及 MVP 切片，不實作 crawler、儲存層、API 或其他 runtime。

- **SHALL／必須**：候選規格被接受後的必要契約。
- **SHOULD／應**：有充分理由才能偏離，且須留下 ADR。
- **MAY／可**：選擇性能力。
- 文件內的 NVIDIA、Meta、Tesla 與 `3017` 只用於 identity／alias／查詢形狀驗證。
- NVIDIA→廣達→奇鋐→雙鴻→健策及 Apple→台積電→家登→辛耘是未附 evidence 的示意圖，**不得**成為種子事實、測試預期或推導依據。
- v1.0 來源優先序是規劃輸入，不代表網站允許自動存取；任何來源在治理 Gate 通過前皆為 `BLOCKED_FOR_INGESTION`。

## 2. Problem、Goal、Actors 與 Scope

### 2.1 Problem

現有台股資料多以股票代碼、報價或單一公司頁為中心，無法用一致 identity、時間語意與公開證據回答公司、產品、產業、主題、ETF 及供應鏈關係。原始 v1.0 已提出概念架構與查詢方向，但欠缺 canonical identity、claim/evidence、衝突、重跑、權威來源、API 錯誤與可驗收契約，工程實作可能產生不可追溯關係、雙向漂移與雙寫不一致。

### 2.2 Goal

建立可持續更新的 Taiwan Stock Knowledge Graph，而非另一個股票報價資料庫，使研究者、Top10 與 LLM 讀取端可用公開資訊查詢：

1. 同供應鏈、上下游、客戶、供應商、競爭者、產品、Theme 與 ETF 關聯。
2. 與 NVIDIA、AI Server 等公司或概念共同受惠的**可解釋關聯候選**。
3. Top10 推薦標的與圖譜關聯的證據、有效時間、freshness 與衝突狀態。

「補漲關聯候選」只表示可追溯的圖關聯集合，不是價格判斷、交易訊號或預測。

### 2.3 Actors

| Actor | 需求 |
|---|---|
| 研究者 | 依公司、代碼、產品、Theme、ETF 或關係查詢，並檢視 provenance |
| Top10 read-only consumer | 以推薦標的展開一跳關係，取得可解釋 context，不接收交易判斷 |
| LLM consumer（Claude／ChatGPT／Gemini） | 取得結構化、具來源及 freshness 的回答材料 |
| Data operator | 以冪等方式重跑 ingestion、觀察失敗、產生 daily change report |
| Data steward／reviewer | 處理 alias collision、entity merge／split、來源衝突及 LLM candidate |
| Source／compliance owner | 決定來源使用條款、robots、速率、保存與刪除政策 |
| API／platform operator | 管理 read model、cache、SLO 與版本相容性 |

### 2.4 In Scope（v1）

- 核准 universe snapshot 中全部上市、上櫃股票與 ETF；目標至少 2,000 個可交易 Security，實際數量以 snapshot manifest 為準。
- Organization／Company、Security／ETF、Theme、Product、Industry、Source、Evidence、RelationshipClaim 與其 identity、alias、時間及 provenance。
- 公開資訊來源治理、離線 raw fixture、deterministic parser／validator、受控 LLM extraction candidate 與人工覆核邊界。
- Relationship 的方向、inverse、對稱、可推導與禁止推導語意。
- 冪等 ingestion、Postgres／Neo4j 權威與 projection 契約、daily diff、失敗恢復。
- Company、graph、theme、customer、supplier、related、search 的 read-only REST 查詢契約。
- Top10／LLM 的 read-only graph context 與補漲關聯候選輸出。

### 2.5 Out of Scope

- 交易策略、打分模型、權重、feature engineering、prediction model、未公開演算法。
- crawler、資料庫、Redis、API、scheduler、Docker 或外部服務的本卡實作／部署。
- 把來源優先序、robots 可抓或示意圖誤當授權或事實。
- v2：新聞、重大公告、法說摘要、ETF 成分變動、月營收、EPS、法人買賣、董監持股、Google Trend、Patent、ESG、Export Data、Supply Chain Risk、Geography、Factory、Production Capacity。
- 修改既有 Top10 生產契約、M13／UQ 行為或排名邏輯。

## 3. BRS → StRS／User Story → Acceptance

### 3.1 Business Requirements

| ID | Business Requirement | 成功觀察 | Priority |
|---|---|---|---|
| BR-01 | 建立跨來源、可持續更新且不依賴名稱字串的台股知識 identity | 同一實體不因 alias 重複，歧義不被誤合併 | Must |
| BR-02 | 所有關係結論可追溯至公開 evidence 並保留有效時間與衝突 | 查詢結果可回到 source/evidence，示意關係不入圖 | Must |
| BR-03 | 提供可重跑、可恢復、可稽核的增量更新 | 同一批重跑不重複，失敗可從 checkpoint 恢復 | Must |
| BR-04 | 支援研究者、Top10 與 LLM 的一致 read-only 查詢 | 核心查詢形狀與 provenance 契約通過驗收 | Must |
| BR-05 | 來源使用與資料保存符合逐來源核准政策 | 未核准來源不能進 ingestion；刪除可追蹤 | Must |
| BR-06 | 以不依賴完整 crawler／scheduler 的垂直切片降低交付風險 | 第一個 slice 可由離線 fixture 完成端到端驗證 | Must |

### 3.2 Stakeholder Requirements 與 User Stories

| ID | Source | User Story | Acceptance |
|---|---|---|---|
| US-01 | BR-01 | 身為研究者，我想以正式名稱、alias 或市場代碼找到唯一或明確歧義的實體，以免把公司、Security 與品牌混為一談。 | AC-01、AC-02 |
| US-02 | BR-02 | 身為研究者，我想檢視每條關係的方向、來源、時間及衝突，以便判斷可用性。 | AC-03、AC-04 |
| US-03 | BR-01、BR-02 | 身為 data steward，我想可逆地 merge／split identity 並保留 lineage，以免歷史 claim 失聯。 | AC-02 |
| US-04 | BR-03、BR-06 | 身為 data operator，我想用相同 input 重跑、從失敗 checkpoint 恢復並得到相同輸出。 | AC-05 |
| US-05 | BR-02、BR-05 | 身為 reviewer，我想讓 LLM 只提出 candidate，再由 deterministic gate 與必要人工覆核決定 promotion。 | AC-06 |
| US-06 | BR-04 | 身為 API consumer，我想查 company、graph、theme、customer、supplier、related 與 search，並取得穩定分頁、錯誤與 provenance。 | AC-07、AC-08 |
| US-07 | BR-03 | 身為 operator，我想每天區分新增、修改、失效、衝突與 resolved change，以便產生 change report。 | AC-09 |
| US-08 | BR-05 | 身為 source owner，我想在任何 ingestion 前核准使用條款、robots、速率、保存與刪除政策。 | AC-10 |
| US-09 | BR-02、BR-04 | 身為 Top10／LLM consumer，我想取得可解釋關聯候選與 sector summary，而不接收交易判定。 | AC-11 |
| US-10 | BR-01、BR-04 | 身為 coverage owner，我想用 manifest 驗證全部上市、上櫃與 ETF 的 coverage，並在受控資料量上量測 cache-hit SLO。 | AC-12 |

### 3.3 Acceptance Scenarios

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | 核准 identity fixture 含 NVIDIA／NVDA／Nvidia、Tesla／TESLA、Meta／Facebook 及市場代碼 `3017` | 執行 resolve 與 company lookup | aliases 解析到各自 canonical entity；`3017` 先解析 Security 再連到 issuer Organization；回傳名稱取自 fixture，不由規格臆造 |
| AC-02 | 同名不同 jurisdiction、alias collision，以及已核准 merge／split event | 執行 resolution 與歷史 as-of 查詢 | collision 回 `AMBIGUOUS`；不自動 fuzzy merge；舊 ID 可 redirect 且 lineage、valid time、claims 不遺失 |
| AC-03 | 一筆具 evidence 的 `SUPPLIES_TO(A,B)` 與一筆無 evidence 的示意 edge | 查正向、inverse 與二跳關係 | 正向只儲存一次，inverse 標示 derived；示意 edge 被拒絕；不得自行推導 transitive `UPSTREAM_OF` |
| AC-04 | 同一 canonical fact 有兩個相容來源及一個互斥來源 | promotion／query | 相容 evidence 聚合在同一 claim identity；互斥版本各自保留並標示 `CONFLICTED`，不得以來源優先序靜默覆寫 |
| AC-05 | 固定 raw artifact、parser version、policy version 與 idempotency key | 同批執行兩次，並在 projection 前模擬失敗後重跑 | authoritative rows、claims、outbox event 不重複；checkpoint 可重入；projection 最終與 authoritative snapshot 一致 |
| AC-06 | LLM 產出未知 entity、缺 evidence locator、無法校準 confidence 或 alias collision candidate | promotion gate | deterministic validation fail loud；高影響歧義進 `PENDING_REVIEW`；LLM 不直接寫 authoritative store |
| AC-07 | 核准 company fixture 與可追溯關係 | 呼叫 `/company/3017` 及 `/company/3017/graph` | response 具有 company、products、themes、customers、suppliers、competitors、upstream、downstream、etfs、freshness、provenance；未證實集合為空而非臆造 |
| AC-08 | 有超過一頁結果、過期 cursor、未知 stock_id 與 conflicted claims | 查詢 API | cursor 穩定且 opaque；過期回標準錯誤；未知回 404；conflict 不被隱藏且 freshness 可判讀 |
| AC-09 | 基線 snapshot 與包含 add、modify、invalidate、conflict、resolve 的下一 snapshot | 執行 daily diff | change event 種類、before/after hash、原因、run ID 與計數符合預期；未核准 hard delete 不發生 |
| AC-10 | 來源 registry 缺 terms/robots/rate/retention 任一決策 | 嘗試建立 ingestion run | run 在讀取來源前即被阻擋；robots 允許不能取代 terms／legal basis 核准 |
| AC-11 | Top10 input 與具 evidence 的一跳關係 | expand graph | 只回傳 Related Stocks、路徑、claim/evidence、sector summary 與限制聲明；不輸出買賣、報酬或補漲預測 |
| AC-12 | 核准 universe manifest 與 benchmark dataset | 執行 coverage gate 與 cache-hit benchmark | coverage 對帳無漏失；指定 query shape 的 p95 <300ms，並記錄資料量、暖機、percentile、錯誤率與環境 |

## 4. System Requirements（SRS）

每條 SHALL 為單一可驗證契約；完整 traceability 見 `docs/evidence/TSKG-01/requirements_traceability.md`。

| ID | SHALL Requirement | Source | Verify |
|---|---|---|---|
| SRS-ID-01 | 每個 canonical entity 具有不可因名稱、alias、market 或 merge 改變的 opaque `entity_id`。 | US-01 | AC-01、AC-02 |
| SRS-ID-02 | identity resolver 依核准 deterministic key 與優先序解析 Organization、Security、ETF、Theme、Product、Industry。 | US-01 | AC-01 |
| SRS-ID-03 | alias normalization 保留原值並產生可重算 normalized value、normalizer version 與 source evidence。 | US-01 | AC-01 |
| SRS-ID-04 | alias collision 或不足以唯一識別時回傳候選與 `AMBIGUOUS`，不得自動 fuzzy merge。 | US-01、US-03 | AC-02 |
| SRS-ID-05 | merge／split 以 versioned event、redirect 與 lineage 表達，保留舊 ID 及歷史 as-of 結果。 | US-03 | AC-02 |
| SRS-SCH-01 | canonical schema 覆蓋 Organization／Company role、Security／ETF subtype、Theme、Product、Industry、Source、Evidence、RelationshipClaim。 | US-01、US-02 | AC-01、AC-04 |
| SRS-REL-01 | 每條 semantic relation 以一筆 canonical RelationshipClaim 儲存，不以 inverse 複製第二份事實。 | US-02 | AC-03 |
| SRS-REL-02 | 每個 relationship type 定義 source/target type、canonical direction、inverse、symmetry、attributes 及 valid time。 | US-02 | AC-03 |
| SRS-REL-03 | symmetric relation 以 canonical endpoint ordering 去重，反向查詢標示 derived。 | US-02 | AC-03 |
| SRS-REL-04 | derived relation 只可由白名單 rule 產生，回傳 rule/version/input claims；未列規則及 transitive supply-chain 推導一律禁止。 | US-02、US-09 | AC-03、AC-11 |
| SRS-EVD-01 | 每條 promoted fact／claim 至少連結一筆可定位 Source 與 Evidence；缺 evidence 不得成為 active fact。 | US-02、US-05 | AC-03、AC-04、AC-06 |
| SRS-EVD-02 | Evidence／Claim 同時保存 observed/retrieved、source published（若有）、valid time 與 system time。 | US-02 | AC-04 |
| SRS-EVD-03 | extraction confidence 與 truth status 分離，並保存 extractor/model、prompt/schema、validator 及 policy version。 | US-02、US-05 | AC-04、AC-06 |
| SRS-EVD-04 | 多來源相容 evidence 可聚合；互斥 assertion 必須共存並進入 conflict state，不得靜默覆寫。 | US-02、US-03 | AC-04 |
| SRS-ETL-01 | ingestion 每一 stage 定義 versioned input/output artifact、schema gate 與 fail-loud error context。 | US-04 | AC-05 |
| SRS-ETL-02 | ingestion、claim promotion、outbox 與 projection 使用可重算 idempotency key，使相同 input/version 重跑不重複。 | US-04 | AC-05 |
| SRS-ETL-03 | normalized authoritative record 與 graph projection 必須有單一權威方向；禁止 request-level best-effort dual write。 | US-04 | AC-05 |
| SRS-ETL-04 | run 保存 checkpoint、status、error、artifact hash 與 retry count，僅重跑安全 stage 並可由 authority 重建 projection。 | US-04 | AC-05 |
| SRS-EXT-01 | LLM extraction 只能輸出 schema-constrained candidate，不得直接 merge identity、promote claim 或寫 authority。 | US-05 | AC-06 |
| SRS-EXT-02 | deterministic validator 處理 schema、enum、hash、referential、direction、time 與 evidence completeness；語意歧義與衝突交人工 review。 | US-05 | AC-06 |
| SRS-API-01 | company lookup 回傳 baseline 指定集合及 freshness/provenance，無證據集合為空且不得補寫推測。 | US-06 | AC-07 |
| SRS-API-02 | API 提供 company、graph、theme、customer、supplier、related、search 的 versioned read-only contract。 | US-06 | AC-07、AC-08 |
| SRS-API-03 | collection 與 graph expansion 使用 opaque cursor、stable snapshot、bounded depth/limit 與明確 direction。 | US-06 | AC-08 |
| SRS-API-04 | API 以一致 error envelope 回報 invalid、not found、ambiguous、conflict、stale cursor 及 unavailable，並回 freshness/provenance。 | US-06 | AC-08 |
| SRS-API-05 | cache-hit SLO 只適用於定義的資料量、query shape、暖機、percentile 與 reference environment。 | US-06、US-10 | AC-12 |
| SRS-DIF-01 | daily diff 區分 ADDED、MODIFIED、INVALIDATED、CONFLICTED、RESOLVED、MERGED、SPLIT。 | US-07 | AC-09 |
| SRS-DIF-02 | change report 保存 run、基線、before/after hash、原因、計數、failed/quarantined items 與 freshness。 | US-07 | AC-09 |
| SRS-GOV-01 | 每個來源在存取前須有 terms/legal、robots、allowed method/path、rate/concurrency、owner 與 review date 決策。 | US-08 | AC-10 |
| SRS-GOV-02 | Source／Evidence 依核准 retention、redaction、deletion/tombstone 及 audit policy 處理，刪除可傳播至 projection/cache。 | US-08 | AC-10 |
| SRS-INT-01 | related／Top10 expansion 只輸出可解釋候選、path 與 evidence，不包含交易判定、分數、權重或 prediction。 | US-09 | AC-11 |
| SRS-COV-01 | coverage 以 versioned universe manifest 對帳上市、上櫃、ETF，保留 included/excluded reason 與 source snapshot。 | US-10 | AC-12 |

## 5. Canonical Data Contract

### 5.1 Identity 與 Entity

`Customer`、`Supplier`、`Partner`、`Competitor` 是 Organization 在 claim 中的角色，不是互斥 entity type。`Company` 是 `Organization.organization_kind=COMPANY`；ETF 是 `Security.security_type=ETF`，不再建立同名平行 ETF node。

| Entity | Required fields | Identity key／規則 |
|---|---|---|
| Organization | `entity_id`, `canonical_name`, `organization_kind`, `jurisdiction`, `status` | 優先使用已核准 legal identifier；不可用股票代碼直接當 Organization ID |
| Security | `entity_id`, `security_type`, `market`, `code`, `issuer_id`, `valid_from/to` | active interval 內 `(market, code)` 唯一；代碼保留前導零；`issuer_id` 指向 Organization |
| Theme | `entity_id`, `canonical_name`, `taxonomy_version`, `status` | `(taxonomy_version, normalized_name)`；synonym 是 alias，不是新 theme |
| Product | `entity_id`, `canonical_name`, `product_taxonomy_version`, `status` | taxonomy path + normalized name；無足夠分類時保持 candidate |
| Industry | `entity_id`, `canonical_name`, `classification_system`, `code`, `version` | `(classification_system, version, code)` |
| Source | `source_id`, `name`, `publisher`, `source_type`, `governance_status`, `policy_version` | source registry 指派的 immutable ID |
| Evidence | `evidence_id`, `source_id`, `artifact_hash`, `locator`, `retrieved_at`, `content_hash`, `usage_policy_id` | `(source_id, artifact_hash, locator, content_hash)` 去重 |
| RelationshipClaim | 見 6.1 | semantic identity key 去重，不依資料庫 edge ID |

原始 `Company(stock_id,name,market,industry,sub_industry,country,website,description)` 映射如下：`stock_id/market` 屬 Security；`name/country/website/description` 屬 Organization；industry/sub-industry 轉為具 evidence 的 classification claim。這避免公司改名、換代碼或同公司多 Security 時 identity 漂移。

### 5.2 Alias normalization 與 dedup

1. 保存 `raw_alias`、語言、script、source/evidence、valid time。
2. normalized alias 使用 Unicode NFKC、trim/collapse whitespace、Latin casefold 與核准 punctuation map；不得翻譯或移除具語意字元。
3. 規則優先序：verified legal identifier > source-scoped identifier mapping > `(market, security_code, valid_time)` > exact normalized legal name + jurisdiction + corroborating attribute。
4. 名稱模糊比對只能產生 merge candidate；不得自動 promotion。
5. `NVIDIA/NVDA/Nvidia→NVIDIA`、`Tesla/TESLA→Tesla`、`Meta/Facebook→Meta` 是 identity fixture 的預期 alias group；fixture 必須附 identity evidence，不代表任何供應鏈關係。
6. v1.0 列出的 NVIDIA、AMD、Apple、Meta、Microsoft、Amazon、Tesla、Google、Broadcom、Qualcomm、TSMC、ASE、Foxconn 只能先作 Organization identity fixture candidate；「customer／supplier」分類本身不構成 relationship claim。
7. `3017` lookup 先在指定／推定 market 找 Security；若跨 market 多筆則回 `AMBIGUOUS`；公司名稱取自核准 fixture。

### 5.3 Merge／split

- Merge event：`event_id`, `survivor_id`, `absorbed_ids`, `reason_code`, `evidence_ids`, `reviewer`, `effective_at`, `system_at`, `policy_version`。
- Split event：`event_id`, `source_entity_id`, `result_entity_ids`, claim reassignment map, evidence, reviewer 及時間。
- 舊 ID 永不重用；預設 redirect 到 survivor，但 `as_of` 查詢可還原歷史 identity。
- 不能確定 claim 歸屬時，claim 進入 `PENDING_REVIEW`，不得複製到所有 split 結果。

## 6. Relationship Claim 與 Evidence Contract

### 6.1 RelationshipClaim schema

| Field | Required | Semantics |
|---|---|---|
| `claim_id` | yes | opaque immutable ID |
| `relationship_type` | yes | versioned enum |
| `subject_id`, `object_id` | yes | canonical direction endpoints |
| `qualifiers` | yes | type-specific JSON，空物件也須存在 |
| `evidence_ids` | yes | 至少一筆 active Evidence |
| `claim_state` | yes | `CANDIDATE/PENDING_REVIEW/ACTIVE/CONFLICTED/INVALIDATED/RETRACTED/SUPERSEDED` |
| `valid_from`, `valid_to` | yes | business time；未知界線用明確 open interval，不以 ingestion time 假冒 |
| `system_from`, `system_to` | yes | authority 內可見時間 |
| `observed_at`, `retrieved_at` | yes | 觀測與擷取時間 |
| `source_published_at` | no | 來源可取得時保存 |
| `extraction_confidence` | conditional | `0..1`；只表示 extraction，不表示真實性 |
| `extractor_type/version` | yes | deterministic／LLM／human 及版本 |
| `model/prompt/schema_version` | conditional | 使用 LLM 時必填；不得存未核准敏感 prompt content |
| `validator_version`, `policy_version` | yes | promotion 決策可重現 |
| `semantic_key` | yes | type + endpoints + normalized qualifiers + valid interval hash |

### 6.2 Direction、inverse、symmetry 與 derivation

| Canonical type | Subject → Object | Inverse query label | Symmetric | Derivation policy |
|---|---|---|---|---|
| `ISSUER_OF` | Organization → Security | `ISSUED_BY` | no | inverse query-only；不得由同名推導 |
| `PRODUCES_PRODUCT` | Organization → Product | `PRODUCED_BY` | no | evidence required |
| `USES_PRODUCT` | Organization → Product | `USED_BY` | no | evidence required |
| `SUPPLIES_TO` | Organization → Organization | `SUPPLIED_BY` | no | 不得由 `CUSTOMER_OF` 或示意圖自動建立 |
| `CUSTOMER_OF` | Organization → Organization | `HAS_CUSTOMER` | no | 只依來源明確語意；不與 `SUPPLIES_TO` 視為同一 claim |
| `COMPETES_WITH` | Organization → Organization | same | yes | endpoint ID 排序後只存一筆；原始 `COMPETITOR_OF` 正規化到此型別 |
| `PARTNERS_WITH` | Organization → Organization | same | yes | 原始 `PARTNER_OF` 正規化；不得推導供應關係 |
| `SAME_GROUP_AS` | Organization → Organization | same | yes | 需定義 group/effective time qualifier |
| `BELONGS_TO_THEME` | Organization/Security/Product → Theme | `HAS_MEMBER` | no | 需 evidence 或核准 taxonomy rule |
| `BELONGS_TO_INDUSTRY` | Organization/Security/Product → Industry | `HAS_MEMBER` | no | classification system/version 必填 |
| `HELD_BY_ETF` | Security → ETF(Security) | `HOLDS_SECURITY` | no | `as_of`, weight/shares（若來源有）為 qualifiers；原始 `BELONGS_TO_ETF` 正規化到此型別 |
| `UPSTREAM_OF` | Organization/Product → Organization/Product | `DOWNSTREAM_OF` | no | 預設不可 transitive 推導；每條結論需 evidence 或白名單 rule inputs |
| `RELATED_TO` | Entity → Entity | same | yes | 只作明確 evidence 的弱語意，不能替代未知具體關係；MVP SHOULD quarantine |

只有 query layer 產生 inverse view，回傳 `derived=true`, `derivation_kind=INVERSE`, `source_claim_id`。其他 derived claim 必須具 `rule_id`, `rule_version`, `input_claim_ids` 與重新計算方式。任何未列白名單的傳遞律、共同客戶推論或「A 供應 B 且 B 供應 C，所以 A 供應 C」一律禁止。

### 6.3 Evidence／Source

Evidence 必須能定位到公開來源的特定頁、段落、表格或檔案區段；只保存核准政策允許的 bytes／snippet。若不允許保存內容，保留 hash、locator、metadata 與可稽核的 retrieval record，不以規格繞過權利限制。

同一 semantic claim 的多來源：

- qualifiers 與有效期相容：附加 evidence，不新增 inverse/duplicate claim。
- 互斥 qualifiers、方向或有效期：保留各 assertion，將 conflict set 標為 `CONFLICTED`。
- 來源優先序只能協助 review 排序，不可自動刪除低優先來源。
- 來源撤回／過期：以 `INVALIDATED`／`RETRACTED` 和 system time 結束，不 hard delete。

## 7. Theme taxonomy

v1.0 起始集合為：AI、AI Server、GPU、ASIC、HBM、CPO、CoWoS、Robot、Industrial PC、IPC、Edge AI、Power、Military、Automotive、Satellite、Green Energy、Semiconductor、Optics、Packaging、Testing、Memory、Cloud、Networking。

- 集合是 taxonomy seed，不代表任何公司 membership。
- `Industrial PC` 與 `IPC` 先作 alias candidate，是否同義由 taxonomy owner 核准。
- 每次 taxonomy 變更產生 version；rename、merge、split 使用與 entity lifecycle 相同的 lineage 原則。
- Theme membership 必須有 evidence 或已核准 deterministic classification rule 與 input evidence。

## 8. ETL、Authority、Idempotency 與 Recovery

### 8.1 Versioned stage contract

概念流程保留 v1.0 意圖，但 canonical promotion 順序為：

`Source Gate → immutable RawArtifact → Parser → Extraction Candidate → Normalizer/Resolver → deterministic Validation → optional Human Review → Postgres Authority → Outbox → Neo4j Read Projection → Cache`。

| Stage output | Minimum contract | Gate |
|---|---|---|
| `RawArtifact` | source/run ID, retrieval metadata, content hash, media type, policy ID, immutable locator | source governance + hash gate |
| `ParsedDocument` | raw hash, parser/version, blocks/tables/pages, warnings | schema + recompute gate |
| `ExtractionCandidate` | entity/claim candidates, evidence locator, extractor versions/confidence | schema + evidence completeness |
| `NormalizedBundle` | canonical IDs or unresolved candidates, claims, aliases, validation report | identity + referential + direction gate |
| `PromotionBatch` | approved state transitions, semantic/idempotency keys, review decisions | policy + trace gate |
| `OutboxEvent` | authority transaction ID, aggregate/version, payload hash | atomic authority commit |
| `GraphProjection` | authority watermark, node/edge counts, checksum/reconciliation report | projection recompute gate |

### 8.2 Authority contract（候選 ADR-01）

- **候選預設**：Postgres 是 normalized entity、alias、claim、evidence metadata、run、review decision、outbox 與 change event 的唯一 system of record；Neo4j 是可重建 read projection；Redis 只可作可丟棄 cache。
- Raw artifact bytes 的 storage technology 尚待 ADR，但 content hash 與 immutable locator 是 authority record 的必要欄位。
- 不允許 parser 同時直接寫 Postgres 與 Neo4j；Neo4j 只能消費 committed outbox／snapshot。
- projection failure 不 rollback 已提交 authority；重播 outbox 或由 snapshot 重建，並以 watermark/checksum 對帳。
- 這是可回復候選架構決策，不是使用者需求；接受前不得視為已定技術選型。

### 8.3 Idempotency 與 rerun

- `run_key = hash(source_id + retrieval_window + policy_version + connector_version)`。
- `artifact_key = hash(source_id + canonical_locator + content_hash)`。
- `parse_key = hash(artifact_hash + parser_version + schema_version)`。
- `promotion_key = hash(normalized_bundle_hash + policy_version + review_decision_version)`。
- 重跑相同 key 回傳既有成功 artifact 或安全重算後比對 checksum；不得新增重複 active claim/outbox event。
- retry 只針對聲明為 retry-safe 的 stage，採有限次數；超限進 quarantine，保留 error class、message、input hash 與 last checkpoint。

### 8.4 LLM／deterministic／human 邊界

v1.0 extractor label 必須先映射到 canonical schema，不能直接創造新 entity type：

| Extracted label | Canonical handling |
|---|---|
| Company | Organization candidate (`organization_kind=COMPANY`) |
| Customer／Supplier／Competitor／Partner | Organization candidate + 對應 RelationshipClaim candidate；角色不是 entity type |
| OEM／ODM | Organization candidate + evidence-backed role qualifier；taxonomy 未核准前保持 candidate |
| Industry／SubIndustry | versioned Industry candidate／hierarchy candidate |
| Theme | Theme candidate；只能對照核准 taxonomy version |
| Product | Product candidate |
| Technology | Theme 或 Product classification candidate；歧義時送 review |
| Country | Organization jurisdiction/country controlled-value candidate；v1 不自動新增 Country entity |
| Brand | Organization/Product alias or ownership claim candidate；歧義時送 review |

| Decision | LLM | Deterministic | Human |
|---|---|---|---|
| 從 PDF/文字提出 entity/relationship candidate | 可 | 驗 schema/evidence | 抽查或高風險覆核 |
| exact alias normalize、ID lookup、hash、enum、time、direction | 不可取代 | 必須 | 只處理 exception |
| fuzzy merge／split | 只可建議 | 產生候選與 collision | 必須核准 |
| conflict truth resolution | 可摘要證據 | 建 conflict set | 必須核准或保持 conflict |
| claim promotion | 不可直接執行 | 低歧義且 policy 明確時 gate | policy 指定情境必須核准 |

## 9. API Contract

### 9.1 General

- 所有 logical routes 置於 `/v1` version prefix，例如 `GET /v1/company/{stock_id}`；未 versioned legacy alias 是否提供由 ADR 決定。
- read-only API 的時間參數：`as_of`（business time）與 `known_at`（system time，授權後才可用）。
- 所有 response 有 `request_id`, `data`, `page`（適用時）, `freshness`, `provenance_summary`, `warnings`。
- `freshness` 至少含 `authority_watermark`, `last_successful_ingestion_at`, `source_observed_through`, `projection_lag_seconds`, `is_stale`。

### 9.2 Routes

| Method / logical route | Purpose | Core parameters |
|---|---|---|
| `GET /company/{stock_id}` | company aggregate | `market`, `as_of`, `include`, bounded per-section `limit/cursor` |
| `GET /company/{stock_id}/graph` | bounded graph expansion | `direction`, `relationship_types`, `depth` default 1/max 2, `limit` default 50/max 200, `cursor`, `min_confidence` |
| `GET /theme/{theme}` | members/claims of canonical theme | `as_of`, `limit`, `cursor` |
| `GET /customer/{alias}` | organizations with evidence-backed customer relation | `as_of`, `limit`, `cursor` |
| `GET /supplier/{alias}` | organizations with evidence-backed supply relation | `as_of`, `limit`, `cursor` |
| `GET /related/{stock_id}` | explainable related candidates | allowed relation types, max paths, `as_of`, `cursor` |
| `GET /search` | identity resolution/search | `q`, optional `entity_type`, `market`, `limit`, `cursor` |
| `GET /claims/{claim_id}` | full claim/evidence metadata | `known_at` when authorized |

`/company/{stock_id}` data shape：

```json
{
  "company": {"entity_id": "...", "security": {"market": "...", "code": "3017"}},
  "products": {"items": [], "next_cursor": null},
  "themes": {"items": [], "next_cursor": null},
  "customers": {"items": [], "next_cursor": null},
  "suppliers": {"items": [], "next_cursor": null},
  "competitors": {"items": [], "next_cursor": null},
  "upstream": {"items": [], "next_cursor": null},
  "downstream": {"items": [], "next_cursor": null},
  "etfs": {"items": [], "next_cursor": null}
}
```

每個 relation item SHALL 含 `claim_id`, canonical `relationship_type`, `direction`, counterparty/entity, `valid_time`, `claim_state`, `evidence_refs`, `derived` 與 `derivation`（若有）。空陣列表示目前沒有符合條件且可回傳的 active claim，不表示現實世界不存在。

### 9.3 Pagination、snapshot 與 error

- cursor 是 opaque、signed/versioned token，綁定 normalized query、authority snapshot、sort key 與 expiry；client 不得解析。
- 預設 deterministic sort：relevance（search only）後接 canonical ID，其他 routes 依 relationship type、counterparty ID、claim ID。
- 下一頁沿用同一 snapshot；過期／snapshot 已清除回 `410 CURSOR_EXPIRED`，不得悄悄換新 snapshot。
- graph depth 上限 2；v1 不提供無界 BFS。

Error envelope：

```json
{
  "error": {
    "code": "AMBIGUOUS_ENTITY",
    "message": "Query resolves to multiple entities",
    "request_id": "...",
    "details": {"candidate_ids": ["..."]},
    "retryable": false
  }
}
```

標準 mapping：400 `INVALID_ARGUMENT`、404 `ENTITY_NOT_FOUND`、409 `AMBIGUOUS_ENTITY`／`CLAIM_CONFLICT`、410 `CURSOR_EXPIRED`、429 `RATE_LIMITED`、503 `PROJECTION_UNAVAILABLE`／`STALE_BEYOND_POLICY`。

### 9.4 Cache-hit SLO benchmark

`<300ms` 只作 cache-hit read SLO，不是所有 request 或外部來源 SLA：

- Dataset：至少 2,000 個 Security、10,000 個總 entities、100,000 active claims、100,000 evidence metadata；manifest 記錄實際 counts/hash。
- Shapes：company aggregate（每 section limit 20）、depth=1 graph（limit 50）、theme first page（limit 50）。
- Method：每 shape 先 200 次暖機，再量 1,000 次；concurrency=8；server-side latency p95 <300ms、error rate=0；分別報 p50/p95/p99。
- Environment：固定 container/runtime、CPU/RAM、cache policy、dataset hash、commit、冷／暖狀態與量測工具版本；禁止把開發者網路 latency 混入 server-side 指標。
- Reference hardware 尚待 OQ-PERF-01 核准；未核准前可執行相對 benchmark，但不得宣稱 production SLO accepted。

## 10. Daily Diff 與 Change Report

| Event | Meaning |
|---|---|
| `ADDED` | 新 semantic identity／claim 首次進 authority |
| `MODIFIED` | 同一 identity 的可變屬性或 qualifier 產生新 version；保留 before/after |
| `INVALIDATED` | 來源、有效期或 validation 使 claim 不再 active |
| `CONFLICTED` | 新 assertion 與既有 assertion 互斥，兩者共存 |
| `RESOLVED` | 人工／政策決策解除 conflict，保留 decision evidence |
| `MERGED` | 多 entity identity 合併到 survivor |
| `SPLIT` | 一 entity 拆分並有 claim reassignment map |

Change report SHALL 包含 `report_id`, `run_id`, baseline/current snapshot IDs, window, source watermarks, event counts, events with before/after hash, quarantined/failed counts, projection watermark、freshness 及 policy/version。沒有變化也須產生零事件 report。硬刪除需另有核准 policy；一般失效以 tombstone/state transition 表達。

## 11. Source Governance

### 11.1 v1.0 priority baseline（不是存取授權）

| Priority | Source baseline | Intended information | Default ingestion status |
|---|---|---|---|
| P1 | 台灣產業價值鏈資訊平台 | upstream/downstream/products/competitors/industry | `BLOCKED_FOR_INGESTION` until source gate |
| P2 | MoneyDJ | profile/products/customer/supplier/competitor | same |
| P3 | 公開資訊觀測站 | annual report/investor presentation/major customer/supplier | same |
| P4 | Yahoo 股市 | basic info/industry/sector | same |
| P5 | 公開法說 PDF | LLM extraction candidates | same |

每個 Source registry entry 在任何外部存取前須記錄：owner、publisher、terms/legal basis、robots result、allowed method/path/media、authentication constraints、rate/concurrency、user agent/contact、raw/snippet/metadata retention、redaction/deletion、redistribution、review date、decision evidence 及 `APPROVED/BLOCKED/EXPIRED`。robots 只是一項技術政策訊號，不構成著作權、契約或個資授權。

## 12. Architecture Decisions 與候選 constraints

下列皆源自 v1.0 候選技術，不能當成使用者需求：

| ADR | Candidate | v1.1 status / reversible boundary |
|---|---|---|
| ADR-01 | Neo4j + Postgres | 候選：Postgres authority、Neo4j projection；接受前 open |
| ADR-02 | Redis | optional disposable cache；API contract 不依賴 Redis semantics |
| ADR-03 | Temporal or Airflow | open；MVP fixture slices 不依賴 scheduler |
| ADR-04 | Scrapy／Playwright／BeautifulSoup | open per approved source；source connector interface 隔離 |
| ADR-05 | pdfplumber／Marker | open per media benchmark；ParsedDocument contract 隔離 |
| ADR-06 | OpenAI／Gemini／Claude | open provider；ExtractionCandidate schema 隔離 |
| ADR-07 | FastAPI、Python 3.13 | candidate runtime；OpenAPI/JSON contract 不綁 framework |
| ADR-08 | Docker Compose | candidate local deployment；不構成 production topology |

## 13. Success Criteria 與 Test Datasets

| ID | Measurable criterion | Dataset／method |
|---|---|---|
| SC-01 | 100% promoted claims 具有至少一 Evidence、Source、valid/system time、extractor/validator/policy version | TDS-CLAIM schema scan |
| SC-02 | identity fixture 的 alias 正確解析；所有 collision 回 ambiguous；無 fuzzy auto-merge | TDS-IDENTITY，含 NVIDIA/Meta/Tesla/3017 |
| SC-03 | relationship direction、inverse、symmetry、禁止傳遞推導 100% 符合 matrix | TDS-RELATIONSHIP synthetic fixtures |
| SC-04 | 同 batch 重跑兩次的 authority/projection logical checksum 相同且 duplicate active claims=0 | TDS-RERUN |
| SC-05 | expected daily change events 與 report counts 100% 相符 | TDS-DIFF golden manifest |
| SC-06 | universe manifest 中 in-scope Security coverage=100%，每筆 included/excluded reason 完整 | TDS-UNIVERSE approved snapshot；目標 ≥2,000 Security |
| SC-07 | cache-hit query shapes p95 <300ms、error rate=0 | 9.4 benchmark contract |
| SC-08 | Top10／LLM response 中 100% relation paths 可回 claim/evidence，且 prohibited trading fields=0 | TDS-INTEGRATION contract fixtures |

Test dataset definitions：

- **TDS-IDENTITY**：synthetic/offline identity fixture；至少含 12 entities、上述 alias groups、同名跨 jurisdiction collision、`3017` Security→issuer link。名稱取自 fixture，不在 spec 宣稱真實 company mapping。
- **TDS-RELATIONSHIP**：每種 canonical relation 至少一正向、一 inverse query、symmetric dedup、invalid direction、missing evidence、prohibited transitive case；全部為 synthetic。
- **TDS-CLAIM**：active、conflicted、invalidated、open-ended valid interval、多 evidence、missing locator、LLM version 欄位缺漏案例。
- **TDS-RERUN**：固定 RawArtifact 與 expected stage hashes，含 projection 前故障注入。
- **TDS-DIFF**：兩個 synthetic snapshots，覆蓋七種 event 與零變更 report。
- **TDS-UNIVERSE**：source owner 核准的上市／上櫃／ETF snapshot manifest；含 source date、hash、counts、exclusions。
- **TDS-INTEGRATION**：synthetic Top10 IDs 與 evidence-backed one-hop paths；不含預測或真實供應鏈聲明。

## 14. MVP Vertical Slices、Dependencies 與 Frontier

每張 slice 是可獨立驗證的完整路徑；涉及邏輯／轉換者採 public-contract TDD（RED→GREEN→驗證），不以內部實作為測試目標。

| Slice | Input → Output | Dependencies / blocking edges | Acceptance / deterministic verification | Frontier |
|---|---|---|---|---|
| SLC-01 Offline identity-to-company-query | TDS-IDENTITY raw fixture → parsed/normalized bundle → `/company/3017` local response | accepted v1.1 schema；不依賴 crawler/DB/scheduler | AC-01/02/07；schema_gate + trace_gate；aliases、ambiguity、empty evidence-backed sections | **CURRENT** |
| SLC-02 One approved public fixture-to-claim | 已核准單一 local RawArtifact → normalized claim/evidence → local query | SLC-01；Source Gate `APPROVED`；blocking: OQ-SRC-01 for selected source | AC-03/04/10；artifact hash、evidence locator、no unsupported claims | blocked |
| SLC-03 Relationship graph query | SLC-02 claims → forward/inverse/symmetric bounded graph response | SLC-02 | AC-03/07/08；direction matrix、no duplicate inverse、no transitive inference | blocked |
| CP-A Contract checkpoint | SLC-01..03 artifacts → review report | SLC-01..03 | identity/claim/API contracts remain compatible；diff/trace gates | checkpoint |
| SLC-04 Idempotent rerun + daily diff | fixed fixture + prior snapshot → rerun checksum + change report | SLC-02 | AC-05/09；recompute_gate、golden change manifest、failure injection | blocked |
| SLC-05 Conflict/review path | conflicting candidates → conflict set → reviewed/resolved response | SLC-02；review policy decisions | AC-04/06；trace_gate；no silent overwrite | blocked |
| SLC-06 Authority-to-graph projection | promotion batch → Postgres authority/outbox → reconciled Neo4j projection | SLC-03/04/05；ADR-01 accepted | AC-05；transaction/idempotency/rebuild/checksum tests | blocked |
| CP-B Persistence checkpoint | authority + projection + diff → recovery drill report | SLC-04..06 | clean rebuild and watermark reconciliation | checkpoint |
| SLC-07 REST + cache-hit read path | reconciled projection → versioned REST/cache response | SLC-06；ADR-02/07 decision | AC-07/08/12；OpenAPI contract + benchmark harness | blocked |
| SLC-08 Universe expansion | approved universe/source fixtures → coverage manifest + read queries | SLC-07；OQ-UNIV-01 and per-source governance approvals | AC-10/12；coverage=100%, exclusions explicit | blocked |
| SLC-09 Top10/LLM read-only context | Top10 IDs → graph expansion → related candidates/sector summary | SLC-07, coverage threshold from SLC-08；separate Top10 integration card | AC-11；prohibited-field scan + claim/evidence trace | blocked |

Current frontier 只有 **SLC-01**：其 blockers 已由 synthetic offline fixture 與本 spec 消除，不依賴未決 scheduler、完整 crawler、外部服務或 database。SLC-02 在特定來源治理核准前不得開始。每完成 2–3 個 slices 必須停在 CP-A／CP-B 驗證，不可跳過 blocking edge。

## 15. Assumptions、Dependencies、Open Questions、Risks

### 15.1 Assumptions（保守且可回復）

- A-01：父對話補充內容是 v1.0 authoritative design baseline；任務卡的安全、provenance、驗收與 forbidden scope 優先。
- A-02：所有資料僅限公開資訊；「公開可見」仍不等於允許自動收集、保存或再散布。
- A-03：Customer/Supplier/Partner/Competitor 是 Organization relationship role；Company/ETF 分別是 Organization kind/Security subtype。
- A-04：來源 P1–P5 僅是 review priority baseline，不是信任分數或 ingestion permission。
- A-05：Postgres authority + Neo4j projection 是可回復候選預設；ADR-01 未接受前只可做離線 contract slices。
- A-06：2,000+ 是最低 coverage 目標；正式 expected count 由 versioned universe manifest 決定。

### 15.2 Dependencies

- D-01：source/compliance owner 與逐來源 decision record。
- D-02：universe owner 提供可重現上市／上櫃／ETF snapshot manifest。
- D-03：taxonomy owner 核准 Theme／Product／Industry version 與 alias。
- D-04：data steward policy 定義 merge/split/conflict review 權限與 audit retention。
- D-05：API/platform owner 核准 reference environment、auth、rate limit 及 freshness policy。
- D-06：後續獨立卡實作 runtime；本卡不授權。

### 15.3 Open Questions / ADRs

| ID | Question / decision needed | Blocks |
|---|---|---|
| OQ-SRC-01 | P1–P5 各來源的 terms/legal basis、robots、允許 method/path、rate、raw/snippet retention 與 redistribution 為何？ | 對應 source adapter、SLC-02/08；不阻擋 SLC-01 |
| OQ-UNIV-01 | 哪個核准 snapshot 是上市、上櫃與 ETF 的 coverage authority？停牌、下市過渡與多 Security issuer 如何列入？ | SLC-08、正式 coverage acceptance |
| OQ-ARCH-01 | 是否接受 Postgres authority、Neo4j projection、outbox/rebuild 契約？ | SLC-06 |
| OQ-ARCH-02 | raw artifact storage、crawler/parser、PDF parser、LLM provider、API framework、cache 與 local deployment 各採何 ADR？ | 對應實作 slice；不阻擋 schema contract |
| OQ-SCHED-01 | Temporal 或 Airflow（或其他）何者符合 retry、backfill、audit 與操作成本？ | production scheduling；不阻擋 SLC-01..07 manual run |
| OQ-TAX-01 | Theme seed 的 owner、層級、同義詞及 version lifecycle；Industrial PC/IPC 是否同義？ | taxonomy promotion、SLC-08 |
| OQ-CONF-01 | 不同 extractor 的 confidence 如何校準？哪些 relation/policy 可自動 promotion？ | automated promotion；未決時全部高風險進 review |
| OQ-RET-01 | 各 source media 的 raw/snippet/metadata retention、刪除 SLA 與 legal hold？ | source approval、production storage |
| OQ-API-01 | API 是 internal-only 或 external；auth scope、consumer quota、PII/security/log policy？ | SLC-07 production exposure |
| OQ-PERF-01 | reference hardware/container profile 與 production traffic envelope？ | production SLO acceptance；不阻擋 contract benchmark |
| OQ-FRESH-01 | 各 source 的 expected freshness 與 stale-beyond-policy threshold？ | 503 stale policy、daily operations acceptance |
| OQ-RELATED-01 | `RELATED_TO` 是否保留；若保留，允許的語意、evidence 與 consumer 顯示方式？ | `RELATED_TO` promotion；MVP 預設 quarantine |

### 15.4 Risks 與 mitigations

| Risk | Impact | Contract mitigation |
|---|---|---|
| 示意或 LLM hallucination 進入供應鏈 | 高：錯誤研究結論 | evidence mandatory、candidate-only、human review、prohibited fixtures |
| Alias／公司／Security 混淆 | 高：錯誤關聯與重複 entity | 分離 schema、collision fail-closed、merge/split lineage |
| inverse 雙存與 dual write 漂移 | 高：查詢不一致 | single canonical claim、query-derived inverse、single authority + projection |
| 來源政策變動 | 高：合規與刪除風險 | source gate、policy version、expiry、tombstone propagation |
| 關係過度推導被誤認為事實 | 高：補漲候選變交易暗示 | rule whitelist、input claims、禁止 transitive inference、限制聲明 |
| 2,000+ coverage 掩蓋 freshness/quality | 中高 | manifest 對帳與 claim/evidence/freshness 分開量測 |
| 技術選型綁死需求 | 中 | API/stage schemas 隔離 implementation，所有候選技術走 ADR |

## 16. Requirement Quality Exit Gate

- [x] Problem、Goal、Actors、In/Out Scope 明確。
- [x] 每條 SRS 可追溯至 User Story／BRS 與 Acceptance Scenario。
- [x] canonical entities、relationship、evidence、time、conflict、merge/split 契約完整。
- [x] 候選技術與使用者需求分離，未定項有 ADR／Open Question。
- [x] success criteria 與 test datasets 可量測，`<300ms` 限定 cache-hit benchmark。
- [x] slices 垂直、dependency/blocking edge/frontier/checkpoint 明確。
- [x] 高影響歧義沒有假裝已解決；每一項標出所阻擋 slice。
