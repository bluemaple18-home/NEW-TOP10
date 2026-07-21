---
card_id: TSKG-MFO-SRC-01
status: DELIVERED_CANDIDATE
access_date: 2026-07-20
operation_level: read_only
candidate: TWSE listed-security daily institutional investor flow
decision: KEEP_BLOCKED
decision_authority: source_compliance_owner_required
---

# TSKG-MFO-SRC-01：TWSE 三大法人每日買賣資料來源治理

## 1. 結論

本次研究確認兩個官方但不同權利邊界的資料通道：

1. TWSE 官網的「三大法人買賣超日報」提供人工日期／分類查詢與 CSV 下載按鈕，頁面明示資料自民國 101 年 5 月 2 日起提供。
2. TWSE Data E-Shop 的「三大法人買賣超檔」是付費商品，檔名為 `TWT86UC`（不含鉅額）與 `TWTAIUC`（含鉅額），每日 18:00／20:00 產製，起始日為 2004-09-09；內部與外部使用分別有價格及傳輸限制。

未找到能把同一份上市證券逐檔三大法人資料直接納入 TSKG 夜間 ETL 的明確免費 OpenAPI／政府開放資料 distribution。官方 OpenAPI landing page 存在，但本卡未取得列有 `T86` 的可引用 OAS operation；四組 `data.gov.tw/dataset` 精確搜尋只回到使用者「建議開放」頁，而非已上架 dataset。

一般 TWSE 網站條款明示：未依 TWSE 同意方式或未取得同意，不得用自動化裝置、script、crawler 或擷取程式下載資料。Data E-Shop 的使用與訂購條款則要求會員／訂購，並限制內部使用、外部傳輸、衍生商品與再散布。政府 OGL 1.0 只適用於逐一以該條款釋出的資料集，不能由 TWSE 官網或 OpenAPI 入口的存在擴張到 `T86`。

決策：`KEEP_BLOCKED`。本卡不批准 ingestion、不修改 SourcePolicy registry，也不解除 OQ-SRC-01、SLC-02 或 MFO 後續 blocker。

## 2. External-tool gate

```text
external_tool_gate:
tool/service: public web search/open；TWSE、TWSE OpenAPI、Data E-Shop、政府資料開放平臺
operation_level: read_only
connection_status: 公開頁面；無登入、註冊、OAuth、購買或表單提交
schema_checked: 只讀官方 landing／terms／metadata；未下載 OAS JSON，未呼叫資料 endpoint
confirmation_required: false（任務卡已明確授權唯讀研究）
execution_status: 10 retrieved（含 1 retrieved_limited）/ 2 failed / 0 remote writes
evidence: §4 source tracker
remaining_risk: 免費 T86 distribution 的 automation、rate、retention、correction、deletion 與 review contract 未取得；付費通道尚未採購或簽核
```

本卡未開啟 `/fund/T86` response、`/exchangeReport/**`、`/opendata/**`、`swagger.json`、CSV／XLS／TEXT 範例或其他資料檔；未執行日期／公司參數查詢、下載、rate test 或 crawler。

## 3. Candidate identity 與通道分離

| Channel | Canonical identity | 官方證據支持的內容 | 本卡邊界 |
|---|---|---|---|
| `interactive_report` | TWSE「三大法人買賣超日報」 | 日期／分類人工查詢、HTML／CSV 按鈕；自 2012-05-02 起提供；分類含 ETF 與上市產業 | 只證明人工公開查詢存在，不證明 batch/crawler/API 許可 |
| `paid_file_product` | Data E-Shop「三大法人買賣超檔」 | `TWT86UC`／`TWTAIUC`；逐證券法人買進、賣出、淨額；每日；2004-09-09 起；TEXT／Excel；線上或 email 遞送 | 需會員、訂購與契約；內外部用途和再傳輸受限 |
| `official_openapi` | TWSE OpenAPI 1.0 / OAS 2.0 landing | 官方 API 文件入口與 `/v1` base 存在 | 未取得 `T86` operation、target schema、rate、auth 或保存契約；不得把別的 endpoint 授權沿用 |
| `government_open_data` | `data.gov.tw` OGL dataset | OGL 1.0 對明確釋出之 dataset 允許利用、改作、散布及再授權，須顯名 | 本次未找到上市逐檔三大法人 dataset identity；建議頁不是 dataset 或授權 |

### 3.1 Publisher、rights 與 contact

- `interactive_report` 與 `paid_file_product` 的發布者／服務提供者為臺灣證券交易所。
- Data E-Shop 訂購條款宣告其商品的著作權、資料庫權利及衍生權利由 TWSE 所有，僅按契約給予非專屬使用權。
- Data E-Shop 聯絡窗口：`(02) 8101-3494`、`(02) 8101-3393`、`dataeshop@twse.com.tw`。
- TWSE 官網一般聯絡電話為 `(02) 8101-3101`；沒有找到針對免費 `T86` 自動化 ingestion 的 rights／abuse owner 或書面申請流程。

## 4. Source tracker

Access date 均為 `2026-07-20`。只有 `retrieved` 正文承載政策結論；`retrieved_limited` 只證明文件入口與索引可見。搜尋結果內的資料 endpoint 僅作導航排除，未開啟、未引用其資料內容。

| ID | Status | Official URL | 用途／結果 |
|---|---|---|---|
| S01 | `retrieved` | https://wwwc.twse.com.tw/zh/trading/foreign/t86.html | 人工報表名稱、日期／分類、HTML／CSV 控制項、資料起始日與 ETF 分類 |
| S02 | `retrieved` | https://www.twse.com.tw/zh/products/information/information.html | 盤後資訊屬交易時間後由 TWSE 資料系統提供的資料服務 |
| S03 | `retrieved` | https://www.twse.com.tw/zh/terms/use.html | 一般網站自動化下載、智慧財產權、服務變更與 OGL scope exception |
| S04 | `retrieved` | https://eshop.twse.com.tw/zh/product/detail/c4c87ac184e44896a05fcab5a9d544ec | 付費商品 identity、欄位、檔名、格式、時程、起始日、價格、遞送與用途 |
| S05 | `retrieved` | https://eshop.twse.com.tw/zh/home/terms | Data E-Shop 會員、automation 與智慧財產權一般條款 |
| S06 | `retrieved` | https://eshop.twse.com.tw/zh/shopping/finishOrder?show=true&showTIP= | 網路訂購、權利、內外部使用、再傳輸、衍生商品、變更／終止條款 |
| S07 | `retrieved` | https://eshop.twse.com.tw/zh/news/detail/000000008f605848018f60a028090000 | 2024-02-01／02-20 Excel 格式變更；Text 不變 |
| S08 | `retrieved_limited` | https://openapi.twse.com.tw/ | 官方 Swagger landing 可達；搜尋索引呈現 API 1.0、OAS 2.0 與 `/v1`，直接 parser 無正文；未下載 spec |
| S09 | `retrieved` | https://data.gov.tw/license | OGL 1.0 授權、顯名、版本、停止提供與免責；只適用明確依其釋出的 dataset |
| S10 | `retrieved` | https://data.gov.tw/suggests/137032 | 使用者建議開放上市逐檔三大法人資料；沒有 dataset metadata 或機關回應正文，不能作授權證據 |
| S11 | `failed` | https://www.twse.com.tw/robots.txt | web open 回 Internal Error；未取得內容，不推論 allow/disallow |
| S12 | `failed` | https://openapi.twse.com.tw/robots.txt | web open 回 Internal Error；未取得內容，不推論 allow/disallow |

另開啟 `https://data.gov.tw/suggests/44238`，內容同屬使用者建議而非 dataset／provider policy，分類為 `not_used`。四組精確 `data.gov.tw/dataset` 搜尋及兩組 `openapi.twse.com.tw` 的 `T86` 搜尋沒有找到合格 target；此結果只記錄本次 discovery gap，不宣稱全域或永久不存在。

成功／失敗計數：`retrieved=10`（含 1 個 `retrieved_limited`），`failed=2`。`not_used` 與 search-only navigation 不列入分母。

## 5. Required-field coverage

狀態是本次官方證據覆蓋，不是法律意見。`FOUND` 仍受 channel scope 限制。

| Required field | Status | 官方證據與判定 | 限制 |
|---|---|---|---|
| canonical identity／publisher／contact | `FOUND` | S01、S04、S06：人工報表、付費商品與 TWSE／商店窗口均可定位 | 免費 API／OGL target identity 仍未找到 |
| distribution media | `FOUND` | S01：HTML／CSV 控制項；S04：TEXT／Excel、線上／email | 沒有獲准的 TSKG machine distribution |
| terms／legal basis／license | `CONFLICTING` | S03 限制一般網站 automation；S05–S06 限定付費商品用途；S09 對明確 open dataset 較寬 | 是 scope 差異造成的 unresolved，不可混用授權 |
| attribution | `FOUND` | S06 外部使用指定 TWSE／訂單編號聲明；S09 OGL 要求顯名 | 免費 T86 不具 OGL dataset identity，不能選用 OGL attribution |
| commercial／derivative／redistribution | `CONFLICTING` | S06：內部不得外用；外部僅傳給資訊用戶且禁止再傳；衍生商品需事前書面同意。S09 對明確 OGL dataset 允許較廣利用 | target 未被證明屬 OGL；Data E-Shop 需另約 |
| explicit programmatic permission | `NOT_FOUND` | S08 只證明 API 文件入口；S03 對未經同意自動下載呈限制性 | 文件／CSV 按鈕存在不等於 nightly ingestion 許可 |
| path／method／version | `NOT_FOUND` | S01 有人工頁 locator；S08 有 OpenAPI `/v1` 與版本存在性 | 沒有列有 `T86` 的 target operation；禁止以 response URL 反推核准 path |
| authentication | `CONFLICTING` | S01 公開頁可讀；S05–S06 要求商店會員／訂購 | 沒有免費 automation 的正式 auth/no-auth contract |
| robots | `NOT_FOUND` | S11–S12 讀取失敗 | robots 也不等於法律授權；不以失敗推論 |
| rate／concurrency／request frequency | `NOT_FOUND` | 無成功官方正文提供數值或規則 | 未做 rate/load test |
| retry／backoff／required UA／abuse contact | `NOT_FOUND` | 有一般與商店聯絡窗口，無 connector 規格 | 不自行設定即視為官方允許 |
| update frequency／business date | `FOUND` | S04：每日、交易日 18:00／20:00；S01：人工查詢日期；S07：曾有格式變更 | 18:00／20:00 屬付費檔；免費頁更新時點未明示 |
| late correction／revision semantics | `NOT_FOUND` | S07 只證明格式曾變更；S09 只規定知悉錯漏時修正 open data | 沒有 target backfill、revision flag 或更正 SLA |
| raw／snippet／metadata retention | `NOT_FOUND` | S06 授權使用範圍未給保存期限；S09 只對明確 OGL dataset 有不限時間授權 | 沒有 TSKG raw/snippet/metadata 的逐 media 契約 |
| redaction／deletion／tombstone／legal hold | `NOT_FOUND` | 成功來源無 target 規範 | 不以契約終止或 OGL 停止提供條款補猜 |
| policy version／review／expiry | `NOT_FOUND` | S03、S05–S06 可修改條款；S07 證明格式會變 | 無 owner-approved review date、expiry 或 immutable decision hash |
| decision evidence locator／owner | `FOUND` | §4 保存官方 locator；source/compliance owner 是唯一核准者 | 尚未簽核，不是 executable policy |

## 6. Scope 與風險判讀

### 6.1 人工報表不是 ingestion API

S01 證明使用者可在頁面選日期／分類並下載 CSV，但沒有明示允許 crawler、批次查詢或自動建庫。S03 反而要求自動化下載必須是 TWSE 同意的方式或另經同意。因此不得把前端背後可能存在的 response URL 寫進 SourcePolicy。

### 6.2 OpenAPI 入口不是 target operation

S08 證明 TWSE 有官方 OpenAPI catalog，且其他證券交易 API 被列出；本次未找到 `T86` operation，也未取得 target schema、auth、rate 或版本保證。為遵守本卡邊界，沒有下載 `swagger.json` 或呼叫任何 endpoint。結論只能是 target operation `NOT_FOUND`，不能由其他 operation 類推。

### 6.3 OGL 不覆蓋未上架 target

S09 的 OGL 允許明確依該條款釋出的開放資料進行重製、散布、改作與再授權，並要求顯名。S10 是使用者提出的「建議開放」頁，缺 dataset identifier、provider metadata、distribution 與 license；因此不是 `T86` 的 OGL 證據。

### 6.4 Data E-Shop 是可研究但未獲採購授權的替代路徑

S04、S06 對 dataset identity、產製時間、欄位與用途最完整，但它是付費契約：內部版不得外用；外部版只能傳給資訊用戶並要求禁止再傳；另行編製指數或衍生商品需事前書面同意。TSKG 若要採這條路，必須另卡取得採購授權、確認 Top10／LLM／API 是否屬允許用途，並鎖定保存、刪除與下游傳輸契約。

## 7. Decision matrix

| Candidate channel | Recommendation | Gate result | 解除 blocker 的最低條件 |
|---|---|---|---|
| `interactive_report` | `KEEP_BLOCKED` | 缺明示 automation、path allowlist、rate、UA、retention、correction、deletion、redistribution 與 review artifact | TWSE 書面同意或官方 automation policy，逐 path/media 鎖定所有操作與保存欄位 |
| `official_openapi` | `KEEP_BLOCKED` | 未找到 `T86` target operation／dataset identity；其餘操作欄位不完整 | 官方 OAS/metadata 明列 target，補齊 license、auth、rate、UA、retention、revision、deletion 與 review |
| `government_open_data` | `NOT_APPLICABLE` | 本次找不到已上架的上市逐檔三大法人 dataset；建議頁非 dataset | 找到明確 dataset identifier、provider、distribution、license 與 operational contract 後另卡重審 |
| `paid_file_product` | `KEEP_BLOCKED` | dataset identity 清楚，但尚未訂購／簽核且用途、保存與下游傳輸受限 | 採購／法遵 owner 明確授權；確認 internal/external use；補 retention、deletion、correction、delivery SLA 與下游矩陣 |

整體 decision：`KEEP_BLOCKED`。存在性已證明，所以不是整體 `NOT_APPLICABLE`；必要治理欄大量缺失，所以不符合 `RECOMMEND_APPROVAL_REVIEW`。

## 8. Unresolved blockers

1. 免費上市逐證券三大法人資料的 canonical dataset／distribution identity。
2. 明示允許 TSKG nightly programmatic ingestion 的 method／path family。
3. auth/no-auth、rate、concurrency、retry/backoff、UA 與 abuse contact。
4. 免費通道的發布時間、business-date complete marker、late correction 與 backfill 契約。
5. raw／snippet／metadata retention、redaction、deletion、tombstone 與 legal hold。
6. 免費通道的商業、衍生、API／LLM／Top10 再散布邊界。
7. Data E-Shop internal/external 方案與 TSKG 下游用途的相容性及採購核准。
8. owner、policy version、review date、expiry 與 immutable signed decision artifact。
9. 上櫃資料需另選 TPEx 官方來源；本卡只研究 TWSE 上市證券，不可沿用。

## 9. 下一張安全卡

建議不要開始 crawler。下一步應二選一，且各自另卡：

- `TSKG-MFO-SRC-02A`：由 source/compliance owner 向 TWSE 詢問 `T86` 免費自動化介接的書面政策與完整 operational contract。
- `TSKG-MFO-SRC-02B`：若接受付費來源，研究 Data E-Shop 採購方案對 TSKG、Top10、LLM 及 API 下游的契約相容性，不登入、不購買，直到取得明確商務授權。

在其中一條通道完成 owner review 前，Source Gate 必須 fail closed。

## 10. Post-dossier technical access probe

### 10.1 Probe result

2026-07-20，owner 將問題收斂為「公開資料目前是否實際取得得到」，並明確要求做技術確認。執行一次官方 T86 單日唯讀 GET：

- target：`https://www.twse.com.tw/rwd/zh/fund/T86`
- query：`date=20260717`、`selectType=ALLBUT0999`、`response=json`
- response：`stat=OK`
- business date：`20260717`
- title：`115年07月17日 三大法人買賣超日報`
- fields：19
- rows：1,337
- request credentials：未使用登入或 token

回傳欄位包含證券代號、證券名稱、外陸資、投信、自營商自行買賣／避險及三大法人買賣超股數，足以證明目標資料的技術可取得性與逐證券資料形狀。

### 10.2 Revised interpretation

| Question | Status | Meaning |
|---|---|---|
| 目前能否從官方 endpoint 取得資料 | `GO` | 單日 probe 已取得 `stat=OK` 與 1,337 列資料 |
| 能否配合現有盤後固定排程 | `TECHNICALLY_FEASIBLE` | T86 是盤後日資料，可按 business date 每日抓一次；尚未實作 scheduler |
| 是否已證明免登入／免 token 的正式契約 | `PARTIAL` | 本次 request 未帶 credentials 且成功；不等於官方永久 no-auth contract |
| 是否已取得 rate／retention／redistribution 規則 | `NOT_FOUND` | 單次成功不可推論負載、保存或下游再提供權利 |
| production source 是否已核准 | `KEEP_BLOCKED` | 仍需 owner 對 operation policy 與下游用途作明確決策 |

因此，原 dossier 中「技術 path 尚未實測」的部分已由此 probe 補足；真正剩餘 blocker 是治理與 production policy，不是資料拿不到。
