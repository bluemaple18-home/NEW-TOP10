---
card_id: TSKG-MFO-TPEX-01
status: IMPLEMENTED_PENDING_REVIEW
access_date: 2026-07-22
operation_level: bounded_current_day_read
decision: GO_CURRENT_DAY_OPENAPI_ONLY
supersedes_decision: KEEP_BLOCKED
decision_authority: versioned_source_governance
---

# TSKG-MFO-TPEX-01：TPEx 三大法人逐證券來源治理 dossier

## 1. 更正與結論

前一版 `KEEP_BLOCKED` 建立在「未找到對應政府開放資料 dataset」的負面證據上；重新核對後，這項判斷不正確。政府資料開放平臺已有 dataset `11856`「上櫃股票三大法人買賣明細資訊」，資料提供機關為金融監督管理委員會證券期貨局、更新頻率每日、授權為政府資料開放授權條款第 1 版；資料介接由 TPEx 官方 OpenAPI 提供。TPEx 官方 Swagger 同時固定 `GET /tpex_3insti_daily_trading`，實際 API 位址為 `https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading`。

因此來源決策改為 `GO_CURRENT_DAY_OPENAPI_ONLY`：只允許上述 OGL dataset 對應的官方 JSON endpoint，單次 GET、concurrency 1，供本機內部研究與 daily snapshot 使用。互動式歷史網站、CSV 頁、付費 S35、任何 crawler、批次回補與 raw 對外再散布均不在本次核准範圍。

TPEx 網站條款仍禁止未獲同意的網站自動擷取；本決策沒有繞過該限制，而是只使用官方明確列為政府開放資料、並由官方 OpenAPI 提供的機器可讀 operation。

## 2. 官方來源與判定

| ID | Official locator | 已驗證事實 | 判定 |
|---|---|---|---|
| P01 | https://data.nat.gov.tw/dataset/11856 | dataset 名稱「上櫃股票三大法人買賣明細資訊」、資料提供機關金融監督管理委員會證券期貨局、每日更新、OGL 1.0 | target dataset identity、正確顯名與授權 `FOUND` |
| P02 | https://www.tpex.org.tw/openapi/swagger.json | OAS3 固定 operation `/tpex_3insti_daily_trading`，response 為 JSON array、schema 欄位固定 | method/path/media contract `FOUND` |
| P03 | https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading | 2026-07-22 bounded smoke test 回傳 906 筆、單一民國日期 `1150722` | current-day machine source `VERIFIED` |
| P04 | https://data.gov.tw/license | OGL 1.0 允許使用、重製、散布及衍生利用，須顯名並注意來源停止提供風險 | legal basis `FOUND`；本專案另採更保守的 no-raw-public-redistribution |
| P05 | https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html | 網站頁面禁止未同意的 script/crawler/extractor | 歷史網站與互動報表 `BLOCKED` |
| P06 | TPEx paid S35 文件 | 付費三大法人明細另有申請、帳密及散布限制 | paid source `OUT_OF_SCOPE` |

## 3. 可執行政策

版控政策：`config/tskg_source_policy_governed_v1.json`。

| 欄位 | 決策 |
|---|---|
| source id | `tpex-openapi-3insti-daily` |
| method/path/media | 只允許 `GET /openapi/v1/tpex_3insti_daily_trading`、`application/json` |
| authentication | 無；官方 public OpenAPI |
| rate/concurrency | 專案保守上限：每次執行 1 request、concurrency 1；不是宣稱 TPEx 公布 SLA |
| retry/backoff | adapter 不做自動重試；失敗由 scheduler 下一輪處理 |
| update semantics | current-day only；response 只能有一個 trade date，日期不符即 fail closed |
| correction/history | API 未提供版本或歷史日期參數；不以網站爬蟲補歷史 |
| raw retention | 本機 internal cache 最多 30 日；metadata/provenance 可永久保存 |
| redistribution | OGL 需顯名；本專案政策額外禁止 raw snapshot 公開再散布 |
| review/expiry | reviewed `2026-07-22T00:00:00Z`；expires `2027-07-22T00:00:00Z` |

`SourcePolicyRegistry.from_mapping()` 與一般 `from_file()` 仍禁止把 PUBLIC 動態提權成 APPROVED；`from_governed_file()` 同時鎖定 repo path、registry version 與 reviewed canonical checksum。即使呼叫端取得 Python module private token，任意變更 source/path/policy 都會因 checksum 不符而拒絕。

## 4. Adapter contract

`app/tskg/tpex_institutional.py` 實作：

- 先做 governed source preflight，通過後才發出一次 GET。
- 封閉驗證官方 20 欄 schema、單一交易日、stock id uniqueness 與所有 buy-sell-net arithmetic。
- 將數值正規化為整數股數，明確標示 `unit=SHARE`、TPEx endpoint publisher、正確 OGL data-providing organization、dataset id、license 與 response date。
- canonical 排序與 SHA-256 integrity；寫檔採同目錄 atomic replace。
- 不呼叫互動式網站、不接受日期參數去推測歷史 endpoint、不自動重試、不碰付費來源。

2026-07-22 live smoke receipt：906 records；canonical SHA-256 `b913b2b019fd70e50c0f4e709b9c5514279368fd874684c539b4872017fc6005`。真實 payload 僅寫到本機暫存，未提交 Git。

## 5. 未被本決策解除的範圍

- 歷史 TPEx 法人回補仍沒有核准的免費 API 路徑。
- 互動式頁面／CSV crawler 與 paid S35 仍禁止使用。
- raw TPEx payload 不可進 public API、LLM context 或公開 artifact。
- 此來源 GO 只解除「current-day daily snapshot」；不會自動讓 Theme、Graph 或 ranking feature promotion 變成 GO。
