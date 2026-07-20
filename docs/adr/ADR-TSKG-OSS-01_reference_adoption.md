---
adr_id: ADR-TSKG-OSS-01
card_id: TSKG-OSS-ADR-01
status: PROPOSED_CANDIDATE
decided_on: 2026-07-20
source_sha: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
primary_decision: ADAPTER_FIRST_INTERNAL_PATTERNS
next_implementation_card: TSKG-MFO-RM-01
---

# ADR-TSKG-OSS-01：參考資產採用與下一個實作 frontier

## Status

`PROPOSED_CANDIDATE`。本 ADR 尚待獨立 review 與主線接受；它不批准 ingestion、endpoint、SourcePolicy、production runtime 或下一張卡的建立。

## Context

TSKG v1.1 要求來源在存取前通過 terms／legal、method/path、rate、retention 等治理，並把 Top10／LLM 限定為具 evidence 的 read-only consumer；未核准來源必須保持 `BLOCKED_FOR_INGESTION`。[`docs/specs/TSKG_v1.1.md` §2.5、§3 AC-10、§4 SRS-GOV-01/02、§11、§14]

市場資金 handoff 已把每日法人數值定義為可刪除、重算、版本化的 observation layer，而不是 `RelationshipClaim`、圖譜 truth、策略、feature、score 或 prediction；`SecurityFlowObservation` 與 `ThemeFlowObservation` 仍是候選邊界，Theme 聚合另依賴固定 membership snapshot。[`docs/handoff/handoff_20260720_tide_tskg_concepts.md`「Constraints & Preferences」、「可吸收的核心概念」§1–3、「建議後續切片」]

Repo 中的 FinMind fetcher／integrator／FetchStage 與 direct T86 market-context path 都存在 caller；但只有 direct T86 parser/status 有 synthetic verifier，兩條路徑都沒有 production source approval。FinMind 的逐股欄位與缺值補零語意不等同 `SecurityFlowObservation` 的 TWD observation；direct T86 現有產物是市場總量，不是逐證券 observation。[`docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md` §1、§3–7；`docs/evidence/TSKG-OSS-01/verification.md` §2–5]

TWSE source dossier 對免費 T86 automation、target operation、rate、retention、correction 與 redistribution 維持 `KEEP_BLOCKED`；官方頁面、OpenAPI landing 或 README 中的 endpoint 描述都不等於核准的 machine distribution。[`docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md` §1、§3、§5–8]

外部 scout 與其獨立 review 支持「只借鏡、不可把 code license 擴張為 data rights 或 endpoint authorization」：TWSEMCPServer 最直接但仍是 MCP stack；FinMind 的 Apache-2.0 code 與資料使用說明分層；twstock 只提供相鄰的 request discipline；其餘候選不是 T86 專用、維護停滯、授權不明或僅是 issue discussion。[`docs/research/TSKG-OSS-02_external_open_source_reference_scout.md` §1–6；`docs/evidence/TSKG-OSS-02/verification.md` §2–8；`docs/evidence/REVIEW-TSKG-OSS-01-02/review.md`「Verdict」、「Spec Axis」、「Remaining Risks」]

兩張 acceptance review 證明研究資產的 host-path cleanup 與 final lineage repair 可供本 ADR 使用，但不把其 acceptance 擴張成 underlying source／production approval。[`docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`「Verdict」、「Remaining risks」；`docs/evidence/REVIEW-TSKG-OSS-ACCEPT-02/review.md`「Verdict」、「Integrable chain」]

## Decision

Primary decision: `ADAPTER_FIRST_INTERNAL_PATTERNS`

唯一主方案是保留 repo 內已驗證的 parser defensive shape、source status/error shape 與 synthetic/offline verifier shape，建立 source-neutral 的 observation → read-model 邊界；任何外部 OSS、FinMind service 或 TWSE/MOPS endpoint 只可作 reference 或保持 blocked，不得成為本決策授權的 dependency 或 ingestion source。

### 四方案比較

| Option | 判定 | 原因 |
|---|---|---|
| `ADAPTER_FIRST_INTERNAL_PATTERNS` | **PRIMARY / SELECTED** | 可避免第二套 runtime/parser/source client，且下一切片可完全用 synthetic fixture 與 offline verifier 驗證；符合 source gate fail-closed。[TSKG v1.1 §8、§11、§14；OSS-01 §6] |
| `THIRD_PARTY_DATA_DEPENDENCY` | REJECTED | FinMind service 的 data-use、token/rate、retention、late correction、單位與 production approval 未完成；code license 不授予 data rights。[OSS-01 §6–8；OSS-02 §3.1] |
| `OSS_STACK_ADOPTION` | REJECTED | TWSEMCPServer 是 MCP server，README/CLAUDE 只證明 reference directness；tsec/tsrtc 等有維護或 license 缺口。直接移植會引入第二套 runtime/source client。[OSS-02 §3.4–3.7；REVIEW-TSKG-OSS-01-02「Spec Axis」] |
| `WAIT_FOR_SOURCE_APPROVAL` | REJECTED AS PRIMARY | Live ingestion 必須等待，但 source-neutral observation projection 可離線完成；全面等待會不必要地阻擋可逆、無 endpoint 的最小切片。[TSKG v1.1 §3 BR-06、§14；Tide handoff「建議後續切片」] |

混合成分只限於 selected primary 的附屬策略：internal verified patterns 可 reuse，外部設計只能 reference，所有 live source 仍 blocked。它們不是第二個 primary。

## Adoption matrix

狀態詞只描述本 ADR 的採用姿態，不改寫既有 runtime 的存在狀態。

<!-- adoption-matrix:start -->
| Asset | Adoption status | Code / license | Data rights | Endpoint authorization | Production approval | 依據 |
|---|---|---|---|---|---|---|
| Repo `FinMindFetcher.get_institutional_investors` | `DO_NOT_ADOPT` | 既有 repo code 存在；不新增或複製 external code | FinMind data-use 邊界未核定 | FinMind service/token/rate 未核定 | 不作 TSKG ingestion | OSS-01 §3、§5–8；OSS-02 §3.1 |
| Repo `FinMindIntegrator.integrate_chip_data` | `REFERENCE_ONLY` | 只讀其 augmentation／name-pivot 手法 | 缺值補零、share-like 欄位不可當 TWD observation | 不授權其上游 service | 不沿用產出語意 | OSS-01 §4.1、§6 |
| Repo `FetchStage` FinMind hook | `DO_NOT_ADOPT` | 只保留 optional isolation 的教訓 | silent skip 會掩蓋 evidence 缺漏 | 不授權外部 call | fail-loud observation gate 不得照搬 skip | OSS-01 §3、§6 |
| Repo direct T86 parser pattern | `REUSE_INTERNAL` | 只 reuse defensive row/field parsing shape；不複製 endpoint | 現有市場總量不轉成逐證券資料權利 | direct T86 URL 仍 blocked | 僅 synthetic parser pattern | OSS-01 §3–6；MFO-SRC-01 §6.1 |
| Repo market-context `SourceStatus` pattern | `REUSE_INTERNAL` | reuse status/error/provenance shape | status 不替代 data rights | 不授權任何 source | source-neutral status only | OSS-01 §5–6 |
| Repo offline verifier monkeypatch pattern | `REUSE_INTERNAL` | reuse synthetic、single-source failure、JSON round-trip shape | fixture 不宣稱真實資料權利 | 外部 call 必須為 0 | 可作下一卡驗收形狀 | OSS-01 §3、§6；OSS-01 verification §2、§5 |
| `SecurityFlowObservation` | `REUSE_INTERNAL` | source-neutral contract shape，非 external code | 只接受 synthetic／已驗證 normalized input | 不含 connector 或 endpoint | 僅 offline read-model frontier | Tide handoff「建議觀測實體」與「建議後續切片」 |
| `ThemeFlowObservation` | `BLOCKED_PENDING_SOURCE_APPROVAL` | 保留概念，不實作聚合 | Theme membership authority／snapshot 未核准 | source 尚未核准 | MFO-02/03 與 UI 都 blocked | Tide handoff §2、「建議後續切片」；UI-MFR-00「Blocking Edges」 |
| TWSEMCPServer | `REFERENCE_ONLY` | MIT 僅支持 code reference；不 vendoring/MCP adoption | 不授予 TWSE data reuse | README/CLAUDE endpoint 描述不是官方授權 | 不進 production dependency | OSS-02 §3.6；REVIEW-TSKG-OSS-01-02「Spec Axis」 |
| FinMind external service | `DO_NOT_ADOPT` | Apache-2.0 code 與 service/data 分層 | 教育／非商業說明及下游用途未解 | token/request contract 不等於批准 | 不作 TSKG source | OSS-02 §3.1；OSS-01 §7 |
| FinMind code patterns | `REFERENCE_ONLY` | 只參考 loader/augmentation interface | 不攜帶資料使用權 | 不攜帶 service authorization | 不安裝、不新增 dependency | OSS-02 §3.1、§6 |
| twstock | `REFERENCE_ONLY` | MIT；只參考 request discipline/proxy/code-update abstraction | 不授予 TWSE/TPEX data rights | request-limit note 不是 endpoint approval | 不作 T86 source/client | OSS-02 §3.2 |
| twstocks-crawler | `DO_NOT_ADOPT` | PyPI 顯示 MIT，但原始 repo／描述證據不足 | 無 T86 data-rights 證據 | 無 direct T86 operation 證據 | 不採用 | OSS-02 §3.3、§4 |
| tsec | `DO_NOT_ADOPT` | license 未見且維護停滯 | 無 target data-rights 證據 | 舊 crawler path 易漂移 | 不移植 | OSS-02 §3.4 |
| tsrtc | `DO_NOT_ADOPT` | license 未見且維護停滯 | 即時盤資料不等於 T86 rights | 非 T86 endpoint contract | 不移植 | OSS-02 §3.5 |
| T86 issue discussion | `REFERENCE_ONLY` | discussion 不是可複製實作 | 不提供資料授權 | 只證明 path 漂移風險 | 只作 negative test/risk reference | OSS-02 §3.7 |
<!-- adoption-matrix:end -->

### Approval layers

| Layer | 本 ADR 可決定 | 本 ADR 明確不決定 |
|---|---|---|
| Code license | 內部 pattern reuse；MIT/Apache 資產只讀 reference | vendoring、dependency、整套 stack adoption 或 license compliance sign-off |
| Data rights | synthetic fixture 與 metadata-only evidence 的離線驗證 | MOPS／TWSE／FinMind 資料收集、保存、改作、再散布、Top10/LLM/API 下游用途 |
| Endpoint authorization | source adapter port 必須隔離且 fail closed | path/method/auth/rate/UA/retry/backoff；README、CLAUDE、CSV button、OpenAPI landing 均不構成批准 |
| Production approval | source-neutral pure projection 與 offline verifier 的未來實作可評估 | connector、scheduler、runtime wiring、API、DB、cache、UI、live artifact 或 production active 聲明 |

因此必須持續保留四句判斷：程式存在不等於 production active；OSS License 不等於資料可再利用；README／CLAUDE endpoint 描述不等於官方授權；MOPS／TWSE ingestion、rate、retention、redistribution 仍未批准。[TSKG v1.1 §11；MFO-SRC-01 §1、§5–8；OSS-01 §5–7；OSS-02 §3.1、§3.6]

## Responsibility boundary

```text
source adapter
  -> raw snapshot / provenance
  -> source normalizer
  -> SecurityFlowObservation contract
  -> graph projection boundary (association-only, by security_id)
  -> Top10 / LLM read model
```

| Layer | Responsibility | Current posture |
|---|---|---|
| Source adapter | 依已核准 path/method/auth/rate 取得 bytes | `BLOCKED`：MOPS／TWSE／FinMind 均未獲本 ADR 批准 |
| Raw snapshot / provenance | immutable locator/hash/retrieved time/policy reference | synthetic fixture 可做；live bytes、retention、deletion、redistribution `BLOCKED` |
| Source normalizer | source-specific row/name/unit/null/correction mapping | interface 與 negative fixture 可做；任何 real-source mapping acceptance `BLOCKED` |
| Observation contract | 驗證 `observation_id/security_id/trade_date/investor_type/net_buy_value_1d/formula_version/source/evidence/freshness` | 足夠作下一張 source-neutral offline input boundary；不批准 5d/20d、acceleration、anomaly 公式 |
| Graph projection boundary | 只以 `security_id` 關聯既有 entity，deterministic grouping/ordering 並傳遞 freshness/provenance；observation 與 claim 分層 | **NEXT FRONTIER**：pure association/read projection + synthetic fixture + offline verifier；Theme aggregation、graph diffusion 與 DB projection deferred |
| Top10 / LLM read model | 提供觀測值、日期、freshness、provenance 與 warnings | source-neutral schema 可做；production integration、ranking mutation 與策略語意 `BLOCKED` |

此邊界延續 TSKG 的 single-authority／rebuildable projection 原則，但不接受或修改 Postgres／Neo4j 候選 ADR，也不建立第二套 graph/runtime。[`docs/specs/TSKG_v1.1.md` §8.1–8.2、§12、§14]

## Top10 / LLM non-strategy read model

最小輸出只能包含：`security_id`、`trade_date`、每 investor type 的 `observation_id` 與 `net_buy_value_1d`、`formula_version`、`freshness/is_stale`、`provenance_refs`、`warnings`。若未來與 graph context 合併，只能附 evidence-backed path 與 observation date。

明確禁止欄位或語意：`rank`、`score`、`weight`、`feature_importance`、`signal`、`prediction`、`expected_return`、`buy/sell`、`補漲`、`即將上漲`。本 ADR 不定義排序、模型特徵、公式、門檻、圖擴散或交易行為。[TSKG v1.1 §2.5、SRS-INT-01、AC-11；Tide handoff §3；UI-MFR-00「Acceptance Boundary」]

## Next implementation card

Next implementation card: `TSKG-MFO-RM-01`

- Root question：能否把已通過 source-neutral validation 的 synthetic `SecurityFlowObservation`，以 deterministic pure projection 轉成不含策略語意的 Top10／LLM read model，同時完整傳遞 freshness 與 provenance？
- Allowlist 類型：一個新的 source-neutral projection module、synthetic fixture、unit/contract tests、offline verifier、該未來 implementation card 與 verification evidence；不得包含 connector、現有 fetcher、requirements、config、runtime wiring、API、DB、UI、TSKG spec 或既有 observation contract 修改。
- Input contract：validated rows；必填 `observation_id`、`security_id`、`trade_date`、`investor_type`、integer-TWD `net_buy_value_1d`、`formula_version`、`source_id/evidence_id`、`observed_at/retrieved_at`、`freshness/is_stale`。fixture 明示 synthetic，不含 live endpoint payload。
- Output contract：依 `security_id/trade_date` 的 canonical read model；investor observations deterministic order；保留 observation IDs、值、公式版本、freshness、provenance refs、warnings；prohibited strategy fields 必須為 0。
- Acceptance：相同 logical input 在重排與重跑後輸出 canonical hash 相同；duplicate key、非法 investor type、非 integer-TWD、缺 provenance、非法日期 fail loud；stale/partial 以 warning 表達而非補零；external call=0；現有 runtime caller change=0；受影響 tests、offline verifier、prohibited-field scan、host-path gate、`git diff --check` 全通過。
- Stop conditions：需要 live source、source-specific endpoint/schema 判定、FinMind/TWSE/MOPS ingestion、rate/retention/redistribution、公式 ownership、Theme membership、graph diffusion、API/UI 或 Top10 ranking mutation時停止；fixed input contract 有衝突時不得自行補猜。

本 ADR 只指定這一張下一卡，不建立它，也不授權執行。

## Deferred forks

依序另行決策，不得混入 `TSKG-MFO-RM-01`：

1. `SOURCE_APPROVAL`：MOPS／TWSE／TPEx／FinMind 的 data rights 與 owner decision。
2. `LIVE_CONNECTOR`：核准 source 的 adapter、auth/path、schema/version。
3. `RATE_RETENTION`：rate/concurrency/retry、raw/snippet/metadata retention、deletion、redistribution。
4. `LATE_CORRECTION`：business-date complete marker、revision/backfill/tombstone。
5. `THEME_FLOW_AGGREGATION`：taxonomy/membership snapshot、coverage、aggregation method。
6. `GRAPH_DIFFUSION_RESEARCH`：只在 evidence-backed graph 與 offline research export 後評估，不進 canonical truth。
7. `UI_MARKET_FLOW_RADAR`：維持 `UI-MFR-00 BACKLOG / NOT AUTHORIZED`，直到 blocking edges 解除。

依據：[`docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md` §8–9；`docs/handoff/handoff_20260720_tide_tskg_concepts.md`「建議後續切片」；`docs/tasks/2026-07-20_UI-MFR-00_market_flow_radar_backlog.md`「Blocking Edges」、「Current Frontier」]

## Consequences

### Positive

- 避免新增第二套 parser、graph、source client、MCP runtime 或 external dependency。
- 讓下一切片可用 synthetic fixture 完成 deterministic acceptance，不把 source approval 與純 projection 綁在一起。
- 對 Top10／LLM 保留可解釋 observation context，同時阻止 prediction／ranking 語意滲入 knowledge graph。

### Costs and limitations

- 本 ADR 不產生 live freshness、coverage 或 production data value；所有真實 source 仍 blocked。
- source-specific normalizer、late correction、Theme aggregation 與 graph diffusion 延後，未來可能要求獨立 ADR／contract card。
- internal parser/status/verifier 的 reuse 只代表形狀可借鏡，不代表現有 runtime 已符合新 observation contract。

## Rejected alternatives

- 拒絕把 FinMind/TWSE 現有 caller 當成 source approval，因存在、可執行、已測試、production-approved 是四個不同判斷。[OSS-01 §5、§7]
- 拒絕安裝、vendoring 或大幅移植 TWSEMCPServer／twstock／其他 crawler stack，因 reference directness 與 license 不足以越過 data/endpoint/production gates。[OSS-02 §2–4]
- 拒絕重寫 `SecurityFlowObservation` 或 TSKG v1.1 contract；下一卡只消費最小 validated input boundary，任何缺口留給獨立 contract/source fork。
- 拒絕在 source approval 前啟動 ingestion、API、DB、scheduler、UI 或 ranking/model 變更。
