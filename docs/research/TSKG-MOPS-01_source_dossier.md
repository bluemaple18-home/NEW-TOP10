---
card_id: TSKG-MOPS-01
status: DELIVERED_CANDIDATE
access_date: 2026-07-20
operation_level: read_only
source_scope: MOPS_TWSE_official_pages_only
decision_authority: source_compliance_owner_required
---

# TSKG-MOPS-01：MOPS source-governance dossier

## 1. 結論

本次成功讀取 11 個官方頁面，另有 3 個 URL 讀取失敗。官方證據足以確認 MOPS 的用途、共同建置單位、TWSE 聯絡窗口，以及另外存在政府開放資料、OpenAPI 文件入口和需申請的 MOPS 主動派送服務；但不足以形成任何可執行的 `APPROVED` policy。

三個 access channel 的範圍不可互相沿用：

- MOPS 互動式網站是供投資人查閱公司揭露的服務，但未成功取得 MOPS-specific terms、robots、rate、UA、retention、deletion 或 redistribution 契約。
- 政府資料開放平臺只對逐一上架並明示授權的 dataset 適用 OGL 1.0；不能擴張到整個 MOPS、任意頁面、附件或財報。
- Data E-Shop 的 MOPS 主動派送是另行申請的服務；會員下載與自動化使用受其獨立條款約束，不能反推互動網站或 open-data API 的權限。

因此本卡只給研究建議，三個通道均為 `KEEP_BLOCKED`。OQ-SRC-01 未解除，SLC-02 仍 blocked。

## 2. External-tool gate

```text
external_tool_gate:
tool/service: web search/open；MOPS、TWSE、官方連結的政府資料開放平臺
operation_level: read_only
connection_status: 公開頁面；不登入、不註冊、不要求 OAuth
schema_checked: web search/open 已暴露；未呼叫任何資料 API schema 或資料 endpoint
confirmation_required: false（唯讀研究已由任務卡明確授權）
execution_status: 11 retrieved / 3 failed；0 remote writes
evidence: 本文件第 4 節 source tracker
remaining_risk: MOPS-specific terms、robots 與多項操作／保存政策仍未取得
```

未呼叫公司資料查詢、OpenAPI data endpoint、下載連結、PDF、CSV、JSON、HTML raw artifact、表單、登入或付費流程；未執行 rate-limit 測試。

## 3. Source authority 與 channel 定義

### 3.1 Source／publisher／owner

TWSE 官方專文指出，MOPS 由金融監督管理委員會證券期貨局指導，並由臺灣證券交易所、證券櫃檯買賣中心等單位共同合作建置；TWSE 的服務介紹也把 MOPS 列為其投資人資訊平台，功能是提供上市櫃公司自行輸入的財務、業務與重大資訊供查閱。這支持「共同治理／TWSE 維運窗口」，不支持把所有資料著作權或法律責任單獨歸給 TWSE。

官方窗口：TWSE 投資人服務中心 `(02) 2792-8188`；MOPS 申報系統維護電話 `8101-5852`、`8101-5877`；資訊契約與連線事項電話 `8101-3393`。主動派送服務另列 `(02) 8101-3393`、`(02) 8101-3494` 與 `dataeshop@twse.com.tw`。

### 3.2 三個 channel

| Channel | 官方證據支持的存在性 | 本 dossier 的範圍邊界 |
|---|---|---|
| `interactive_web` | `FOUND`：TWSE 服務頁與 MOPS 優化專文均明示投資人透過網際網路查詢 | 人工瀏覽／互動查詢；不含 crawler、batch、資料 API |
| `official_api_or_open_data` | `FOUND`：政府資料集頁明示 OAS 文件 URL；官方 Swagger landing page可開啟 | 只限具明確 dataset identity、distribution 與 license 的資料；本卡未呼叫 endpoint |
| `manual_file_download` | `FOUND`：TWSE 服務頁描述 MOPS 含電子書、年報等；Data E-Shop 另有下載／派送 | MOPS 人工附件下載與 Data E-Shop 是不同子通道；本卡未下載任何檔案 |

## 4. Source tracker

Access date 均為 `2026-07-20`。`retrieved_limited` 計入成功數，但只可證明 landing page 可達，不承載正文結論。

| ID | Status | Tool | Official URL | 用途／結果 |
|---|---|---|---|---|
| S01 | `retrieved_limited` | web open | https://mops.twse.com.tw/mops/ | 新版 MOPS 首頁可達但 parser 無正文；只證明入口存在 |
| S02 | `failed` | web open | https://mops.twse.com.tw/robots.txt | 工具回 non-retryable unsafe；未取得內容，不推論 allow/disallow |
| S03 | `retrieved` | web open | https://www.twse.com.tw/zh/terms/use.html | TWSE 網站使用條款、自動下載限制、IP 與聯絡資料 |
| S04 | `failed` | web open | https://www.twse.com.tw/zh/openapi/ | 猜測路徑被工具判為 non-retryable unsafe；以 S05、S06 回復 |
| S05 | `retrieved_limited` | web search/open | https://openapi.twse.com.tw/ | 官方 Swagger landing page 可達但 parser 無正文；不呼叫 spec/data endpoint |
| S06 | `retrieved` | web search/open | https://data.gov.tw/dataset/28567 | 「公開發行公司基本資料」dataset identity、檔案資料、更新頻率、OGL、OAS URL、聯絡人 |
| S07 | `retrieved` | web search/open | https://data.gov.tw/license | OGL 1.0 授權範圍、顯名、版本、停止提供與免責 |
| S08 | `retrieved` | web search/open | https://data.gov.tw/about/doc?chapter=11&doc=4 | dataset metadata 中 license、cost、provider/contact、更新頻率等欄位契約 |
| S09 | `retrieved` | web search/open | https://www.twse.com.tw/zh/about/company/service-contact.html | MOPS 維護、資訊契約／連線與 TWSE 服務窗口 |
| S10 | `retrieved` | web search/open | https://www.twse.com.tw/zh/about/company/service.html | MOPS 用途、內容類型、Data E-Shop 與投資人服務定位 |
| S11 | `retrieved` | web search/open | https://wwwc.twse.com.tw/market_insights/zh/detail/8a8216d6933460a4019343c4dd720060 | MOPS 指導／共同建置單位與互動查詢定位 |
| S12 | `retrieved` | web search/open | https://eshop.twse.com.tw/zh/mops/publicStep | MOPS 主動派送需另行申請及聯絡資訊 |
| S13 | `failed` | web open | https://mops.twse.com.tw/mops/web/index | 官方舊連結轉至 error page；以 S01、S10、S11 回復入口／用途證據 |
| S14 | `retrieved` | web open | https://eshop.twse.com.tw/zh/home/terms | 商店會員、下載、自動化與智慧財產權條款；僅適用 Data E-Shop |

Search-only 結果中含公司參數的 MOPS 查詢頁、PDF／CSV／下載 URL、交易資訊辦法、AI／RSS／隱私政策等候選均為 `not_used`：前兩類屬明確 forbidden scope，後者與 MOPS source-governance 欄位或通道範圍不相符。它們未被開啟，也未被引用為結論。

成功／失敗計數：`retrieved=11`（含 2 個 `retrieved_limited`）、`failed=3`。搜尋導航候選不列入成功／失敗分母。

## 5. Required-field coverage

狀態只表示本次官方證據覆蓋情形，不是法律判斷。`FOUND` 仍可能有 channel scope 限制。

| Required field | Status | 官方證據與短摘要 | 限制 | Confidence |
|---|---|---|---|---|
| source／publisher／owner／contact | `FOUND` | S09–S11：證期局指導、TWSE／櫃買中心等共同合作；TWSE 提供維運與服務窗口 | 未找到單一、完整的 MOPS data-rights owner 聲明 | high（營運）／medium（權利） |
| terms／legal basis | `CONFLICTING` | S03：TWSE 一般網站禁止未經同意的自動下載；S06–S08：指定 open dataset 適用 OGL；S14：商店另有會員條款 | 並非文字直接矛盾，而是適用範圍不同；缺 MOPS-specific terms，故跨通道使用時仍 conflicting／unresolved | high |
| robots result | `NOT_FOUND` | S02 未成功讀取 | robots 不構成法律授權；也不可用讀取失敗推論政策 | high |
| allowed method／path family／media type | `CONFLICTING` | S10–S11 支持人工 web 查詢；S06 指向 OAS 文件並把樣本 dataset 標為檔案資料；S12 支持申請後派送 | 未成功讀取可引用的 API spec 正文，未找到 MOPS path allowlist；不同通道方法不得沿用 | medium |
| authentication constraints | `CONFLICTING` | S01 公開入口可達；S12 需申請；S14 的商店訂購／下載需會員 | 未找到 MOPS interactive 或 TWSE OpenAPI 的正式 auth／no-auth 契約 | medium |
| rate limit／concurrency／request frequency | `NOT_FOUND` | 無成功讀取的官方頁提供數字或政策 | 禁止以測試推測；未做負載／頻率測試 | high |
| required user agent／contact identifier | `NOT_FOUND` | S09、S12 提供一般／申請窗口 | 無頁面要求 connector UA、email 或 contact identifier | high |
| raw retention | `CONFLICTING` | S07 對明確 OGL dataset 授與不限時間利用；S03／S14 對一般網站／商店內容保留權利 | OGL 不可擴張到 MOPS raw HTML、附件或財報；未找到逐 media retention policy | high |
| snippet retention | `CONFLICTING` | 同 raw retention；OGL dataset 可依授權利用與改作 | MOPS 網頁／附件 snippet 保存未明示 | high |
| metadata retention | `CONFLICTING` | S07 的「開放資料／資訊」範圍與 S08 metadata 契約支持指定 dataset metadata 利用 | MOPS retrieval metadata、hash 或 locator retention 未有 source-specific 條款 | medium |
| redaction | `NOT_FOUND` | 無官方頁說明 ingestion-side redaction 義務 | 不以一般隱私政策代替 source artifact policy | high |
| deletion／tombstone／legal hold | `NOT_FOUND` | S07 只說提供機關可停止未來提供；未規定本專案保存副本的刪除、tombstone 或 legal hold | 不推論「不可撤回」等於永不刪除任何第三方權利資料 | high |
| redistribution／derivative／commercial use | `CONFLICTING` | S07 對指定 OGL dataset 允許不限目的重製、散布、改作、再授權，須顯名；S03／S14 對一般網站／商店內容原則上要求事前同意 | 授權只附著於明確 dataset/distribution；MOPS 互動內容與附件仍 unresolved | high |
| review／expiry requirements | `NOT_FOUND` | S03、S14 可隨時變更條款；S06 有 metadata 更新時間；S07 有版本轉換與停止提供機制 | 無 MOPS review date、policy version、expiry 或 mandatory review cadence | high |
| decision evidence locator | `FOUND` | 本 tracker 的 S03、S06–S12、S14 可作 immutable decision artifact 的候選 locator | source/compliance owner 尚未核准、hash 或簽署任何 decision artifact | high |

### 5.1 Channel-specific interpretation

| Field group | `interactive_web` | `official_api_or_open_data` | `manual_file_download` |
|---|---|---|---|
| legal scope | MOPS-specific terms `NOT_FOUND`；TWSE 一般條款僅是風險證據 | OGL 對逐一標示 dataset `FOUND`，其他 API/path `NOT_FOUND` | MOPS 附件條款 `NOT_FOUND`；Data E-Shop 另有獨立條款 |
| method/path/media | 人工 web 查詢存在；無 automation allowlist | OAS landing 與 dataset link 存在；未讀 spec 正文、未呼叫 endpoint | MOPS 存在電子書／年報類型；未驗下載 path/media；商店需申請／會員 |
| auth | 公開入口可達，但正式約束 `NOT_FOUND` | `NOT_FOUND` | 公開 MOPS attachment `NOT_FOUND`；商店會員／申請 `FOUND` |
| rate／UA | `NOT_FOUND` | `NOT_FOUND` | `NOT_FOUND` |
| retention／deletion | 全部 `NOT_FOUND` | 明確 OGL dataset 的利用期間可支持 retention；刪除／legal hold `NOT_FOUND` | MOPS attachment `NOT_FOUND`；商店依契約另審 |
| redistribution | `NOT_FOUND`／一般條款呈限制性 | 明確 OGL dataset `FOUND`，須顯名 | MOPS attachment `NOT_FOUND`；商店一般內容呈限制性 |

## 6. Method／path／media analysis

### 6.1 文件出現 vs. 明示可程式存取

- 成功讀取的政府 dataset 頁 S06 明示 OAS 說明文件 locator，官方 Swagger landing page S05 亦存在。這證明官方文件通道存在，不等於本卡已驗證任一 endpoint 的 auth、rate 或 response media。
- 本卡沒有成功讀取 Swagger spec 正文，因此不把搜尋索引看到的 `/opendata/...`、`/company/...` 等 path 當作已核准 path family。
- S03 明示：TWSE 一般網站的自動化下載，若不是 TWSE 同意的方式或未取得同意，禁止使用 crawler、script 等工具。
- S06 的 OGL 與 file/API metadata 只支持該 dataset/distribution；其 CSV link 未開啟，無 raw bytes 被下載。
- S12 的主動派送是明示的申請式程式／檔案交付途徑；它不是匿名 MOPS web scraping 的替代證明。

### 6.2 Automation／大量下載／重製／散布／商業使用

- 一般 TWSE 網站與 Data E-Shop 條款均呈限制性：未經同意不得以自動化方式下載；一般內容的使用、重製、改作、散布等原則上需權利人同意。
- 明確 OGL dataset 是 scope-limited 例外：可不限目的利用、改作與再授權，並須履行顯名義務；商業用途未被 OGL 排除。
- 無成功證據允許對 MOPS 互動頁面、財報、年報、電子書或其他附件大量下載、建立資料庫或再散布。
- 無證據允許繞過驗證、限制或使用未公開 path；本卡亦未嘗試。

## 7. Cross-source comparison

| Topic | 一致／衝突／缺口 | 比較結果 |
|---|---|---|
| MOPS 身分與用途 | `CONSISTENT` | S10 與 S11 均支持其為投資人查閱公司公開資訊的共同建置平台；S09 提供 TWSE 維運窗口 |
| API／open-data 通道存在 | `CONSISTENT_WITH_SCOPE_LIMIT` | S05 為官方 Swagger landing；S06 明示 OAS URL與個別 dataset 授權。兩者只證明文件／dataset 通道，不證明所有 MOPS 內容均 open data |
| 一般網站 vs. OGL | `SCOPE_DIFFERENCE` | S03 限制一般網站自動下載；S06–S08 對明確上架 dataset 套用 OGL。以 dataset identity／license 切分後不必視為直接矛盾 |
| MOPS web vs. Data E-Shop | `SCOPE_DIFFERENCE` | S10 描述公開查閱；S12、S14 描述申請／會員／下載條款。商店核准不可沿用到 MOPS web，反之亦然 |
| robots | `GAP` | S02 讀取失敗；無第二份官方 robots 證據，不判定 allow/disallow |
| rate／UA／retention／deletion | `GAP` | 所有成功來源均未完整覆蓋；不得補猜 |

## 8. Decision matrix

| Channel | Recommendation | 依據 | 核准前必要條件 |
|---|---|---|---|
| `interactive_web` | `KEEP_BLOCKED` | 缺 MOPS-specific terms、robots、automation path/method、rate、UA、retention、deletion、redistribution 與 review date | source/compliance owner 取得 MOPS 適用條款或書面許可，固定 path/media/rate/UA/retention/deletion 與 review artifact |
| `official_api_or_open_data` | `KEEP_BLOCKED` | 個別 OGL dataset 的 legal/redistribution 證據較完整，但未取得 API spec 正文、auth、rate、UA、deletion/legal-hold 與 review contract；不能批准整個 API catalog | 逐 dataset/distribution 建 registry；固定 OAS/path/media、auth/rate/UA、retention/deletion、attribution 與 expiry；獨立 Review 後由 owner 核准 |
| `manual_file_download` | `KEEP_BLOCKED` | MOPS 下載類型存在，但附件逐 media 條款、retention、deletion、redistribution 不明；Data E-Shop 是另行申請／會員的不同服務 | 明確指定 artifact class 與取得方式；取得適用條款／授權、保存／刪除契約；若走商店則完成另卡授權與契約審查 |

`NOT_APPLICABLE` 不適用：三種通道均有存在性證據，只是治理證據不足。`RECOMMEND_APPROVAL_REVIEW` 亦不適用：依任務卡規則，任一必要欄缺失、範圍不明或限制未解析即須維持 blocked。

## 9. Unresolved fields 與 blockers

1. MOPS-specific 使用條款、免責、著作權／資料授權頁及其適用 operator。
2. `robots.txt` 實際內容；本次工具未成功讀取。
3. 明示可程式存取的完整 path family、HTTP method、request／response media 與版本契約。
4. OpenAPI 與 MOPS web 的 authentication／anonymous-access 契約。
5. rate limit、concurrency、request frequency、retry/backoff。
6. connector 必須使用的 user agent、聯絡識別或 abuse contact。
7. raw／snippet／metadata 的逐 media retention；MOPS HTML、PDF、電子書、XBRL 與 open dataset 不可混用。
8. redaction、刪除 SLA、tombstone propagation、第三方權利撤回與 legal hold。
9. MOPS 互動內容／附件的重製、衍生、再散布與商業使用權。
10. source policy version、owner-approved review date、expiry 與 immutable decision artifact。
11. MOPS 共同建置單位之間，何者能對特定 dataset／attachment 作出授權決定。

Blocker 結果：OQ-SRC-01 對 MOPS 未解；Source Gate 必須 fail closed；不得開始 SLC-02、建立 RawArtifact／Evidence／claim，或宣稱 MOPS approved。

## 10. Owner review packet

若後續另卡取得必要證據，source/compliance owner 應逐 dataset／distribution，而非以「MOPS」整站，建立 immutable decision artifact。最低內容：publisher/rights owner、channel、canonical path family、method/media、auth、rate/concurrency、UA/contact、raw/snippet/metadata retention、redaction/deletion/legal hold、redistribution/derivative/commercial、attribution、policy version、review/expiry、evidence URL/hash、decision actor/time。

本 dossier 不提供法律意見、不自行批准來源、不修改 Source Gate fixture。
