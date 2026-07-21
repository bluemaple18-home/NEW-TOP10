---
card_id: TSKG-MOPS-01-REVIEW
status: REVIEW_GO
reviewed_on: 2026-07-20
verdict: GO
review_kind: independent_source_trace_review
---

# TSKG-MOPS-01 independent review

## 1. Verdict and lineage

- Verdict：`GO`。
- Review card commit：`ce809f0`。
- Reviewed candidate：`d5e9f4660e082b6879490768a56a4385d064c3c5`。
- Candidate parent：`744bf934cd988b75322cb674c218691de6615b97`。
- Candidate 是指定 parent 的 direct child。
- Candidate changed-file allowlist 恰為：
  - `docs/evidence/TSKG-MOPS-01/verification.md`
  - `docs/research/TSKG-MOPS-01_source_dossier.md`
  - `docs/tasks/2026-07-20_TSKG-MOPS-01_source_dossier.md`
- Review 未修改上述 candidate 文件。

`GO` 只表示這三份研究文件可交主線整合，不表示 MOPS、任一 MOPS 資料、
TWSE OpenAPI、政府 open dataset 或 Data E-Shop 已獲 source／compliance／法律核准。
OQ-SRC-01 未解除，SLC-02 仍 blocked；三個 access channel 全部維持
`KEEP_BLOCKED`。

## 2. Findings

未發現 P0–P3 finding。

候選文件中的未解治理欄位是刻意記錄且與 `KEEP_BLOCKED` verdict 一致的
remaining risks，不是 candidate 遺漏或錯誤：MOPS-specific terms、robots、
method/path/media、auth、rate/concurrency、UA、retention、redaction/deletion/
legal hold、redistribution、review/expiry 與 rights-owner decision authority 均未被補猜。

## 3. Spec axis

`GO`

- 固定 candidate、parent 與 exact three-file allowlist 均相符。
- dossier 完整覆蓋任務卡要求的治理欄位；無證據的欄位均標為
  `NOT_FOUND`／`CONFLICTING` 並保留限制。
- 14 個 tracker URL 已逐一重取，實際結果可重現為 11 retrieved
  （9 substantive、2 limited landing）與 3 failed。
- 失敗 URL 只用來記錄 gap／recovery，不承載實質政策或授權結論。
- MOPS interactive、TWSE 一般條款、逐一上架的政府 OGL dataset、TWSE
  OpenAPI landing 與 Data E-Shop／MOPS 主動派送的 scope 有清楚切分。
- 文件沒有把 Swagger／OAS locator 或 landing 存在誤寫成 endpoint、path、auth、
  rate、response media 或 programmatic access permission。
- 文件沒有把 OGL 1.0 擴張到整個 MOPS、任意 MOPS HTML、財報、年報、電子書、
  附件或 Data E-Shop 商品。
- `interactive_web`、`official_api_or_open_data`、`manual_file_download` 均為
  `KEEP_BLOCKED`；沒有 executable `APPROVED` policy、registry、fixture、
  RawArtifact、Evidence、claim 或 ingestion 變更。

## 4. Standards axis

`GO`

- Review 與 candidate 都只使用官方公開 URL 的唯讀 `open`；未呼叫資料 endpoint、
  Swagger spec、CSV／附件下載、登入、註冊、表單、付費或外部寫入。
- 關鍵結論由成功取得正文的官方來源承載；兩個 limited landing 只證明 landing
  可達，不承載正文政策、API 契約或授權結論。
- source tracker、cross-source comparison、required-field matrix、channel matrix 與
  blockers 彼此一致，沒有 search snippet 取代官方正文。
- candidate diff 無本機絕對路徑、secret、非公開 PII 或法律核准式過度宣稱。
  文件中的電話與 email 均為官方頁公開的服務聯絡窗口。
- `git diff --check` 與可重現性／allowlist／host-path scans 通過。

## 5. Source-trace revalidation

Review access date 均為 `2026-07-20`。工具為官方 URL 的唯讀 `web open`；
`retrieved_limited` 計入成功數，但只允許支持 landing 可達。

| ID | Review retrieval | 實際 retrieval 結果 | Conclusion use |
|---|---|---|---|
| S01 | `retrieved_limited` | `https://mops.twse.com.tw/mops/` 回官方「公開資訊觀測站」HTML，parser `0` 行正文 | 只證明新版入口可達 |
| S02 | `failed` | `https://mops.twse.com.tw/robots.txt` 回 non-retryable unsafe，未取得內容 | 只記錄 robots gap，不推論 allow/disallow |
| S03 | `retrieved` | `https://www.twse.com.tw/zh/terms/use.html` 回 TWSE 使用條款正文；含自動下載與 IP 限制 | 只作 TWSE 一般網站風險證據，不當作 MOPS-specific terms |
| S04 | `failed` | `https://www.twse.com.tw/zh/openapi/` 回 non-retryable unsafe | 不作實質證據；以 S05/S06 記錄文件通道存在 |
| S05 | `retrieved_limited` | `https://openapi.twse.com.tw/` 回官方 Swagger UI landing，parser `0` 行正文 | 只證明 landing 存在；不證明 endpoint permission |
| S06 | `retrieved` | `https://data.gov.tw/dataset/28567` 回「公開發行公司基本資料」dataset identity、CSV distribution、OGL、更新頻率與 OAS locator | 只支持該明確 dataset/distribution 的 metadata 與 license |
| S07 | `retrieved` | `https://data.gov.tw/license` 回政府資料開放授權條款第 1 版正文 | 只適用依該條款釋出的 open data；須顯名 |
| S08 | `retrieved` | `https://data.gov.tw/about/doc?chapter=11&doc=4` 回政府資料集 metadata 欄位規範 | 支持逐 dataset 的 license、cost、provider/contact、update 欄位契約 |
| S09 | `retrieved` | `https://www.twse.com.tw/zh/about/company/service-contact.html` 回 TWSE 服務窗口正文 | 支持 MOPS 維護與資訊契約／連線窗口 |
| S10 | `retrieved` | `https://www.twse.com.tw/zh/about/company/service.html` 回 TWSE 服務介紹正文 | 支持 MOPS 的查閱用途、內容類型與 Data E-Shop 分立定位 |
| S11 | `retrieved` | `https://wwwc.twse.com.tw/market_insights/zh/detail/8a8216d6933460a4019343c4dd720060` 回 TWSE MOPS 優化專文 | 支持指導／共同建置單位與互動查詢定位 |
| S12 | `retrieved` | `https://eshop.twse.com.tw/zh/mops/publicStep` 回 MOPS 主動派送申請程序與官方窗口 | 只支持另行申請的派送服務存在 |
| S13 | `failed` | `https://mops.twse.com.tw/mops/web/index` 轉至官方 error page，parser `0` 行正文 | 不作實質證據；以 S01/S10/S11 recovery |
| S14 | `retrieved` | `https://eshop.twse.com.tw/zh/home/terms` 回 Data E-Shop 使用條款正文 | 只適用網路資訊商店會員／訂購／下載服務 |

重驗計數：

| Metric | Candidate | Review | Result |
|---|---:|---:|---|
| substantive retrieved | 9 | 9 | MATCH |
| limited landing | 2 | 2 | MATCH |
| total retrieved | 11 | 11 | MATCH |
| failed／error URL | 3 | 3 | MATCH |
| failed URL used as substantive evidence | 0 | 0 | MATCH |
| non-official conclusion source | 0 | 0 | MATCH |

## 6. Scope-separation revalidation

| Scope | 官方證據能支持什麼 | 不可擴張到什麼 | Review result |
|---|---|---|---|
| MOPS interactive | MOPS 是投資人透過網路查閱公司公開資訊的平台 | crawler、batch、automation、retention 或 redistribution permission | PASS／`KEEP_BLOCKED` |
| TWSE general terms | TWSE 一般網站限制未經同意的自動化下載與內容重製 | MOPS-specific terms 或 open-data license | PASS／只作風險證據 |
| Government OGL dataset | 明確上架且標示 OGL 的 dataset/distribution 可依 OGL 利用 | 全 MOPS、任意附件／財報／HTML、Swagger catalog | PASS／scope-limited |
| TWSE OpenAPI landing | 官方 Swagger landing 與 OAS locator 存在 | 任一 endpoint 的 permission、method/path/media、auth、rate 或 UA 契約 | PASS／`KEEP_BLOCKED` |
| Data E-Shop／active push | 另有會員下載條款與 MOPS 主動派送申請程序 | MOPS interactive 或 open-data API 權限 | PASS／獨立服務 |

## 7. KEEP_BLOCKED and blocker verification

| Channel／blocker | Candidate | Review result |
|---|---|---|
| `interactive_web` | `KEEP_BLOCKED` | PASS |
| `official_api_or_open_data` | `KEEP_BLOCKED` | PASS |
| `manual_file_download` | `KEEP_BLOCKED` | PASS |
| OQ-SRC-01 | 未解除 | PASS |
| SLC-02 | blocked | PASS |
| MOPS source approval | 未核准 | PASS |
| executable policy／registry／fixture／ingestion | 無變更 | PASS |

## 8. Local verification

- `git cat-file -p`：candidate parent 等於
  `744bf934cd988b75322cb674c218691de6615b97`；PASS。
- `git diff --name-status <candidate-parent> <candidate>`：exact three-file
  allowlist；PASS。
- `git diff --check <candidate-parent> <candidate>`：exit `0`，無輸出；PASS。
- candidate 三檔 host-specific absolute-path scan：無 match；PASS。
- secret／credential／private-key scan：無 match；PASS。
- `APPROVED`／OQ-SRC-01／SLC-02／`KEEP_BLOCKED` 語意人工核對：沒有
  approval 或 unblock；PASS。

## 9. Final verdict and remaining risks

`GO`

Spec axis 與 Standards axis 均為 `GO`，未發現阻塞 finding。剩餘風險全部是
dossier 已誠實記錄且以 fail-closed 處理的來源治理缺口；它們阻止 MOPS approval，
但不阻止此份保守研究文件整合。

本 verdict 不核准 MOPS，不解除 OQ-SRC-01／SLC-02，不允許 ingestion、資料
endpoint、附件下載或任何外部寫入。
