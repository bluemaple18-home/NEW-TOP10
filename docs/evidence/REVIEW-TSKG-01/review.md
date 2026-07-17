---
id: REVIEW-TSKG-01-review
card: REVIEW-TSKG-01
status: REVIEW_NO_GO
verdict: NO_GO
base_sha: 2855510f740334b2636dfd0c391d93d7e4675706
reviewed_candidate_sha: fad395589c90254ffbf4f0e7292a36920d019298
review_card_commit: 117d506428812fc674ede836e52e436d6126a0c1
source_baseline_thread: 019f708e-2c20-7262-8102-6144674d54ce
reviewed_at: 2026-07-17
---

# Findings

## [P1] F-01：同一供應商／客戶事實可形成兩個 canonical claims

- Axis：Spec
- Category：correctness / ontology
- Path：`docs/specs/TSKG_v1.1.md:217`
- Evidence：`SRS-REL-01` 要求每個 semantic relation 只存一筆 canonical claim（line 126），但 relationship matrix 同時保留 `SUPPLIES_TO(A,B)` 與 `CUSTOMER_OF(B,A)`，並明定兩者不是同一 claim（lines 217–218）。目前沒有 required qualifier、互斥 promotion rule 或 query mapping 能證明兩者表示不同商業事實。
- Trigger：兩個來源分別以「A supplies B」與「B is a customer of A」描述同一交易關係時。
- Risk：同一事實會雙存、重複計數或各自進入不同 lifecycle；`/customer`、`/supplier`、graph expansion 與 daily diff 可能回傳重複或互相矛盾的結果，直接違反單一 canonical fact 與 inverse 不雙存的核心約束。
- Suggested fix：優先 canonicalize 為單一 `SUPPLIES_TO(supplier, customer)` claim，將 customer/supplier 視圖改為 query-derived labels；若業務確實需要兩種 predicate，必須定義不重疊的語意、必填 qualifiers、source-to-predicate normalization、衝突規則及 API 去重方式。
- Validation gap：缺少同一來源句義以兩種方向輸入後只能得到一個 canonical fact（或可證明為兩個互斥 predicate）的 golden fixture。
- Confidence：high

## [P1] F-02：Conflict set 與 resolution lineage 無法由 schema 表達

- Axis：Spec
- Category：correctness / temporal lineage
- Path：`docs/specs/TSKG_v1.1.md:192`
- Evidence：`RelationshipClaim` 只有 `claim_id`、`claim_state` 與 `semantic_key`，沒有 `conflict_set_id`、stable fact identity、resolution decision、decision evidence、selected/rejected assertion 或 supersession lineage。更嚴重的是 `semantic_key` 包含 qualifiers 與 valid interval（line 208），而規格要求 qualifiers、方向或有效期互斥的 assertions 被放入同一 conflict set（lines 234–239）；這些 assertions 天然會得到不同 key。`RESOLVED` change event 又要求保留 decision evidence（line 390），但沒有對應 canonical field/state transition。
- Trigger：兩個來源對同一邏輯事實提供不同方向、qualifier 或有效期間，之後 reviewer 選定、維持 unresolved 或撤銷其中一個 assertion。
- Risk：實作者無法 deterministic 地分組、查詢或解決衝突，也無法重建誰在何時依何證據做了決策；AC-04、SLC-05、as-of query 與 `RESOLVED` daily diff 皆不可驗收。
- Suggested fix：分離 stable `canonical_fact_key`、assertion/version key 與 claim ID；新增 conflict-set identity、member assertions、resolution decision ID/state、decision evidence、decided_by/at、policy version、selected/rejected/superseded lineage，並定義完整狀態轉移表與 API 呈現。
- Validation gap：缺少「建立兩個互斥 assertion → 同 conflict set → resolution → 歷史 known_at 仍可看到原衝突與決策」的 round-trip fixture。
- Confidence：high

## [P1] F-03：Unknown 與 unbounded valid time 沒有 deterministic wire encoding

- Axis：Spec
- Category：correctness / temporal
- Path：`docs/specs/TSKG_v1.1.md:200`
- Evidence：`valid_from`、`valid_to` 被列為 required，但只說未知界線用「明確 open interval」；規格沒有定義 JSON/schema 表示、邊界 inclusive/exclusive、`unknown` 與 `-∞/+∞` 的差異，也沒有說 current open `system_to` 如何編碼。單純 `null` 無法同時保留 unknown 與 unbounded 兩種語意。
- Trigger：來源沒有開始日、來源只說「目前仍有效」、或 assertion 的開始未知但結束已知時，資料經 parser、authority、projection 與 API round-trip。
- Risk：不同實作者會把 unknown 當成無界、把 ingestion time 當 business time，導致 as-of 查詢、active 判定、conflict overlap 與 daily diff 結果不一致。
- Suggested fix：定義可序列化 interval contract，例如每一端使用 `KNOWN/UNKNOWN/UNBOUNDED` discriminator、條件式 timestamp 與 inclusion flag；另定義 system-time current row 的唯一表示與非法組合。
- Validation gap：缺少 known、unknown start/end、past/future unbounded、open-ended current、invalid/empty interval 的 schema 與 round-trip matrix。
- Confidence：high

## [P1] F-04：Verification 以「有章節」代替核心契約可執行性

- Axis：Standards
- Category：testing / evidence integrity
- Path：`docs/evidence/TSKG-01/verification.md:34`
- Evidence：verification 將 canonical schema、relationship、evidence/time/confidence、API 與 test datasets 標為 `PASS`（lines 34–44），但沒有驗證 F-01 至 F-03 的 canonicalization、conflict linkage 或 time serialization；static checks 只證明 ID set/count 與章節存在（lines 50–59）。
- Trigger：主線或下一張 implementation 卡把這份 verification 當作 executable-spec exit gate。
- Risk：不可單一實作與不可 round-trip 的契約會被誤判為已完成，將歧義推入 runtime 後才以資料漂移或無法 migration 的形式爆發。
- Suggested fix：先修正核心契約，再讓 verification 逐項引用可判定的 schema invariant、negative case 與 expected serialization；存在未決核心語意時應標 `FAIL/BLOCKED`，不可僅因章節存在而標 `PASS`。
- Validation gap：缺少 relationship equivalence、conflict resolution lineage、temporal encoding 與 mixed extractor confidence 的 negative/golden contract cases。
- Confidence：high

## [P2] F-05：`min_confidence` 把 extraction quality 混入 graph truth filtering

- Axis：Spec
- Category：correctness / API
- Path：`docs/specs/TSKG_v1.1.md:323`
- Evidence：`extraction_confidence` 是 conditional 且明定不代表真實性（line 204），deterministic/human claims 可沒有該值；graph API 卻提供未定義的 `min_confidence`，relation response item 也未要求回傳 confidence（line 347），而 confidence calibration 仍是 OQ-CONF-01（line 498）。
- Trigger：同一查詢同時包含 deterministic、human-reviewed 與 LLM-extracted active claims，client 傳入 `min_confidence`。
- Risk：實作者可能排除沒有 confidence 的高可信 deterministic/human claims，或把模型抽取機率誤當 truth score；不同 extractor 的未校準數值也不可比較。
- Suggested fix：在 calibration ADR 完成前移除 public `min_confidence`；或明確改名為 `min_extraction_confidence`，定義 null/mixed-extractor 行為，且以 claim state、promotion policy、evidence/review status 作 truth 可用性篩選。
- Validation gap：缺少 deterministic/human null confidence、不同 extractor scale、reviewed low-confidence 與 conflicted claim 的 API filter matrix。
- Confidence：high

## [P2] F-06：31/31 只證明內部 ID 覆蓋，v1.0 baseline 追溯不可離線重現

- Axis：Standards
- Category：traceability / regression
- Path：`docs/evidence/TSKG-01/requirements_traceability.md:16`
- Evidence：baseline authority 只寫「父對話」，沒有 source thread/turn ID、canonical input digest 或 repo evidence；31/31 是 candidate 自己的 SRS set equality，14/14 baseline disposition 也是 candidate 自行彙整的 BL 清單（lines 89–98）。本次 reviewer 透過 delegation 的 source thread 才能另行核對；candidate artifact 本身無法做到相同驗證。
- Trigger：未取得原父對話的後續 reviewer、另一台機器或未來 repair 卡要確認是否漏掉 v1.0 Goal、Non-Goals、API、Top10 或 Success Criteria。
- Risk：新增／遺漏 baseline 項目不會使 31/31 或 14/14 失敗，追溯結果容易成為自我證明。獨立核對顯示主要 v1.0 goals/non-goals 已被涵蓋，但證據鏈仍不具可重現性。
- Suggested fix：在 evidence allowlist 保存 canonical v1.0 input（或至少 immutable source thread + turn ID、canonicalization rule、content SHA-256），並將每個 BL 項目連到原始 section/line，而非只連 candidate paraphrase。
- Validation gap：缺少由原始 baseline 自動／人工抽出的 expected BL set 與 candidate disposition set 的獨立比較。
- Confidence：high

## [P2] F-07：`<300ms` acceptance 尚未固定 reference environment 與 benchmark dataset

- Axis：Standards
- Category：performance / testing
- Path：`docs/specs/TSKG_v1.1.md:376`
- Evidence：規格列出最低 counts、query shapes、暖機、次數與 concurrency，但 graph topology、response distribution、fixture/generator seed、cache implementation state 與實際 CPU/RAM/container 值未固定；line 380 明確表示 reference hardware 尚待 OQ-PERF-01，verification 卻把此 gate 標為可量測 `PASS`（`docs/evidence/TSKG-01/verification.md:41`）。
- Trigger：SLC-07 或不同實作者以各自生成的 100,000 claims 與不同硬體宣稱 p95 `<300ms`。
- Risk：相同 counts 可形成完全不同 graph fan-out 與 payload，結果不可跨 commit／實作者比較，也不能作 acceptance gate。
- Suggested fix：固定 benchmark manifest/generator version/seed、關係分布與 expected response sizes，填入 reference container、CPU/RAM、cache policy 與測量工具；在此之前將 SLO acceptance 明確標為 blocked，並把 OQ-PERF-01 加入 SLC-07 blocking edges。
- Validation gap：缺少可重建 dataset hash 的 fixture/generator，以及在固定 reference environment 的 repeatability run。
- Confidence：high

# Axis verdicts

## Spec axis：NO_GO

F-01、F-02、F-03 是核心 ontology、conflict lineage 與 temporal contract 的 P1 阻塞；F-05 另造成 API filtering 歧義。candidate 尚不能作為單一、可測試的 runtime contract。

## Standards axis：NO_GO

F-04 顯示 verification 對核心語意做出 false-positive `PASS`；F-06 與 F-07 則使 baseline traceability 與 SLO acceptance 無法由 candidate artifact 離線重現。

# 六項必查風險結果

1. `SUPPLIES_TO`／`CUSTOMER_OF`：FAIL，見 F-01。
2. Conflict set／resolution／lineage：FAIL，見 F-02。
3. API `min_confidence`：FAIL，見 F-05。
4. valid time unknown/open/unbounded：FAIL，見 F-03。
5. 31/31 traceability：PARTIAL；內部 SRS ID set 31/31 成立，主要 v1.0 Goal／Non-Goals／API／Top10／Success 也經來源 task 獨立核對，但 artifact provenance 不可重現，見 F-06。
6. SLC-01 frontier：PASS_WITH_CONDITION；其離線 fixture path 確實不依賴 ADR-01、database、scheduler 或 crawler，但依賴「accepted v1.1 schema」。本輪 NO_GO 前不得把該 dependency 視為已滿足。

# Validation evidence

- Reviewed range：`2855510f740334b2636dfd0c391d93d7e4675706..fad395589c90254ffbf4f0e7292a36920d019298`，4 個 docs 檔案；review card commit 未納入 candidate。
- `git diff --check 2855510f740334b2636dfd0c391d93d7e4675706 fad395589c90254ffbf4f0e7292a36920d019298`：PASS。
- Candidate changed-file allowlist：PASS；原 TSKG-01 卡只變更 status／Result，未修改 runtime。
- Spec 與 trace matrix 的 unique SRS set：31/31 且集合相等。
- 原 v1.0 baseline：已從 source thread `019f708e-2c20-7262-8102-6144674d54ce` 完整核對 Goal、Scope、Architecture、Entity/Relationship、Sources、ETL、API、Top10、Daily Update、Future v2、Non-Goals 與 Success Criteria；未存取外部網站。

# Final verdict

`NO_GO`

需要 Repair 卡先修復 P1 契約與 verification，再對同一 candidate successor 做獨立 re-review；本 review 不修改 candidate。
