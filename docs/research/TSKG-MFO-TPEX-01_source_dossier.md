---
card_id: TSKG-MFO-TPEX-01
status: DELIVERED_CANDIDATE
access_date: 2026-07-22
operation_level: read_only
decision: KEEP_BLOCKED
decision_authority: source_compliance_owner_required
---

# TSKG-MFO-TPEX-01：TPEx 三大法人逐證券來源治理 dossier

## 1. 結論

TPEx 官方 OpenAPI catalog 明列 `GET /tpex_3insti_daily_trading`，中文名稱為「上櫃股票三大法人買賣明細資訊」，因此已確認存在 machine-readable source identity，涵蓋上櫃逐證券三大法人明細。TPEx 也提供「三大法人買賣金額彙總表」公開查詢頁及 CSV 控制項，但該頁是互動式報表，不能單獨證明批次自動化使用權。

本次未取得官方明示的 nightly automation permission、允許 path/method 的正式契約、rate/concurrency、required UA、retry/backoff、raw/metadata retention、revision/deletion 或 TSKG/API/LLM redistribution 條件。TPEx 網站條款反而明定，未依 TPEx 同意方式或未經 TPEx 同意，不得以自動化裝置、script、crawler 或擷取程式下載資料。政府 OGL 只適用於明確依 OGL 釋出的 dataset；本次沒有找到帶 TPEx 逐證券三大法人 identity 的 data.gov.tw dataset。

另有 TPEx「收市後交易資料」付費方案：S35 `STKBIG3DDTLN.TXT` 是「三大法人與陸資買賣日、週、月明細資訊(新版)」，需申請、帳號／密碼與月費；條款禁止未授權重製、傳輸或散布。未購買、註冊或接受條款。

Source gate：`KEEP_BLOCKED`。本卡不修改 source policy、不建立 live connector、不執行資料 endpoint、下載、rate/load test 或 adapter implementation。後續若要解鎖，須由 source/compliance owner 取得逐 operation 的書面同意並補齊完整 operational contract。

## 2. 官方 source tracker（access date 2026-07-22）

| ID | Official locator | Dataset identity / evidence | 判定 |
|---|---|---|---|
| P01 | https://www.tpex.org.tw/openapi/ | TPEx OpenAPI 1.0.0 / OAS3 landing；catalog 列 `GET /tpex_3insti_daily_trading` 與 schema `tpex_3insti_daily_trading`，名稱為上櫃股票三大法人買賣明細資訊 | machine-readable identity FOUND；未取 response 或 OAS operation 細節 |
| P02 | https://www.tpex.org.tw/openapi/swagger.json | 官方 OAS locator，為 P01 所指向的 machine-readable specification | target spec locator FOUND；未下載，故 path parameters/media/rate 未證實 |
| P03 | https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/summary/day.html | TPEx「三大法人買賣金額彙總表」；日／週／月／年頁面，頁面有資料日期與下載 CSV 控制項；自民國 96 年 1 月起提供 | public interactive report FOUND；不是 automation permission |
| P04 | https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/detail/day.html | TPEx official foreign/institutional detail page，提供日／週／月／年、日期、分類及 CSV 控制項；英文頁確認上櫃法人明細語意 | public interactive detail FOUND；自動化仍受 P06 條款限制 |
| P05 | https://www.tpex.org.tw/storage/regular_system/收市後交易資料使用收費辦法(V1.31版).pdf?t=202312221705 | 官方付費資料辦法；S35=`STKBIG3DDTLN.TXT` 為三大法人與陸資買賣日／週／月明細資訊(新版) | paid machine/file alternative；需申請／付費 |
| P06 | https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html | TPEx website terms：未依 TPEx 同意方式或經 TPEx 同意，禁止以自動化裝置、指令碼、自動程式、蜘蛛、爬蟲或擷取程式下載軟體或資料；未明確 OGL data 不得逕自重製／散布 | explicit automation permission NOT FOUND；blocking |
| P07 | https://data.gov.tw/license | OGL v1.0；需由資料提供機關以明確 dataset/version 釋出，並依條款顯名；機關可停止提供 | general license only；不能擴張覆蓋 TPEx web/API |
| P08 | https://www.tpex.org.tw/en-us/service/data/overview.html | TPEx data products／after-hours data 說明：訂閱、有效帳號密碼、下載檔案及資料商品契約 | paid access contract exists；未採購 |

## 3. Required-field contract

| 欄位 | 狀態 | 證據與限制 |
|---|---|---|
| publisher / owner | `FOUND` | 發布者與 owner 為財團法人中華民國證券櫃檯買賣中心（Taipei Exchange / TPEx）；網站總機 `(02)2369-9555`；未找到特定 API abuse/contact owner |
| dataset identity | `FOUND` | P01/P02 的 operation `tpex_3insti_daily_trading`、schema 同名；P05 的 paid file identity S35 |
| machine-readable media | `FOUND` | P01 OAS3 API；P05 TXT file；公開頁 P03/P04 有 CSV export 控制項 |
| license / terms / legal basis | `CONFLICTING` | P06 website terms restrictive；P07 OGL 僅對明確 OGL dataset；P05 是付費訂購條款，不能混用 |
| automation permission | `NOT_FOUND` | P01 catalog 的存在不是法律／契約授權；P06 要求 TPEx 同意，未取得同意 artifact |
| allowed method / path / version | `PARTIAL` | operation name與OAS locator可定位；未取得 operation request/response contract，不把推測 URL 寫入 adapter allowlist |
| authentication | `NOT_FOUND`（API）；`FOUND`（paid） | 免費 API 無正式 no-auth contract；P08 paid system 需有效帳號密碼 |
| rate / concurrency / retry / UA | `NOT_FOUND` | 官方來源未提供數值或 connector policy；未做 rate/load test |
| update / business date | `PARTIAL` | 報表有日期查詢；P05 為日／週／月檔；免費 API 的 complete marker、發布 SLA 未找到 |
| late correction / revision | `NOT_FOUND` | 未找到 target-specific revision flag、backfill、correction SLA 或 immutable version contract |
| retention / redaction / deletion | `NOT_FOUND` | 未找到免費 API/raw/snippet/metadata 保存、刪除、tombstone 或 legal-hold規則；OGL 的停止提供不等於 TSKG 保存契約 |
| redistribution / derivative | `BLOCKED` | P06 未經書面同意不得重製／散布；P05 未授權不得重製、傳輸、散布，授權傳輸亦有下游限制 |
| review / expiry / decision owner | `NOT_FOUND` | 未有 source-compliance owner 的 signed approval、policy version、review date、expiry |

## 4. Decision matrix

| Candidate | Decision | 最低解鎖條件 |
|---|---|---|
| `tpex_3insti_daily_trading` official OpenAPI | `KEEP_BLOCKED` | TPEx 書面確認 automated use；固定 operation/path/method/version、auth、rate/concurrency、UA、retention、revision/deletion、redistribution、owner/review |
| TPEx interactive detail/CSV | `KEEP_BLOCKED` | TPEx 明示允許的 automation method/path 與完整使用契約；CSV 按鈕不構成 crawler permission |
| TPEx paid S35 `STKBIG3DDTLN.TXT` | `KEEP_BLOCKED` | 不購買前不得使用；取得採購／法遵核准並確認內部 ETL、保存與下游用途，且取得帳號與契約 |
| Government OGL dataset | `NOT_APPLICABLE` | 本次未找到對應 TPEx 逐證券三大法人 dataset identity；若後續出現，另行驗證 dataset/version/provider/distribution |

## 5. Prohibited actions and next step

本卡未接受條款、未註冊、未購買、未呼叫資料 API、未下載資料檔、未做負載／速率測試，也未建立 `app/tskg/tpex_*.py` 或 live fetch script。下一步只能由 source/compliance owner 取得書面 permission 或另卡評估付費方案；在此之前所有 TPEx ingestion 與下游 redistribution 維持 blocked。
