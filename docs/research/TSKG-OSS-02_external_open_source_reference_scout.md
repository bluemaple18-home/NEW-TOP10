---
card_id: TSKG-OSS-02
status: DELIVERED_CANDIDATE
access_date: 2026-07-20
operation_level: read_only
candidate_count: 7
decision: REFERENCE_SCOUT_ONLY
---

# TSKG-OSS-02：外部開源參考盤點

## 1. 結論

本輪唯讀盤點共留下 `7` 個可引用候選，沒有找到「專做 T86 且仍持續維護」的單一專用 crawler/parser/wrapper repo；最接近可直接借鏡的，是把 `T86` 包進較大資料層的專案，或是直接記錄 `T86` 路徑漂移的 issue。

最值得後續 synthesis 卡優先閱讀的前三項：

1. `twjackysu/TWSEMCPServer`
   - 目前看到最直接、最明確把 `/rwd/zh/fund/T86` 寫進工具分層與歷史查詢模組的開源實作。
2. `FinMind/FinMind`
   - 活躍度最高，直接涵蓋三大法人與資料增補流程；但 code license 與 data-use note 有邊界風險，不能直接混為一談。
3. `mlouielu/twstock`
   - 不直接做 `T86`，但對 request limit、proxy、code update 與 TWSE/TPEX 資料抓取邊界有成熟可借鏡做法。

## 2. 候選總表

| # | Candidate | Canonical link | Directness | 最近維護跡象（查閱日：2026-07-20） | License | 可參考部分 | 主要風險 |
|---|---|---|---|---|---|---|---|
| 1 | FinMind | https://github.com/FinMind/FinMind | `DIRECT` | GitHub latest release `2.0.5` 於 `2026-07-18`；PyPI `2.0.5` 也於 `2026-07-18` 發布 | Repo: `Apache-2.0`；PyPI/README 另有「資料僅教育、非商業用途」說明 | `DataLoader` / `feature.add_kline_institutional_investors` 類型的欄位補強與資料增補流程 | code 與 data use 邊界不完全一致；有 request/token 限制 |
| 2 | twstock | https://github.com/mlouielu/twstock | `ADJACENT` | GitHub latest release `v1.5.1` 於 `2026-04-23`；PyPI `1.5.1` 於 `2026-04-23` 發布 | `MIT` | request limit、proxy provider、TWSE/TPEX code update、realtime wrapper | 不含 `T86`；較偏通用台股抓取工具 |
| 3 | twstocks-crawler | https://pypi.org/project/twstocks-crawler/ | `NOT_RELEVANT` | PyPI 最新 `0.0.7` 於 `2022-06-27` 發布，之後未見新版本 | PyPI 標示 `MIT` | 只證明有一個薄封裝 package 名稱存在 | 幾乎沒有專案描述；原始碼首頁未在本輪成功取回；與 `T86` 無直接證據 |
| 4 | tsec | https://github.com/Asoul/tsec | `ADJACENT` | GitHub latest release `1.0.1` 於 `2016-03-27`；repo README 自述最後更新 `2017/02/15` | `LICENSE 未見` | 批次日資料 crawler、post-process、TWSE/TPEX 歷史資料檔案化流程 | 維護停滯；授權不明；不能直接複用 code |
| 5 | tsrtc | https://github.com/Asoul/tsrtc | `ADJACENT` | GitHub latest release `1.0.2` 於 `2017-02-15`；README 自述最後更新 `2017/02/15` | `LICENSE 未見` | 即時 TWSE API 分析、欄位拆解、資料完整率與清洗腳本思路 | 維護停滯；授權不明；屬即時盤，不是 `T86` |
| 6 | TWSEMCPServer | https://github.com/twjackysu/TWSEMCPServer | `DIRECT` | GitHub repo 首頁 sidebar 顯示 latest release `v1.8.0` 於 `2026-07-19`；repo 176 commits、3 open issues | `MIT` | `history/institutional (T86)`、`/exchangeReport` vs `/rwd/zh/...` 路徑分層、歷史查詢模組化 | 是 MCP server，不是單純 parser；需抽象出資料層而不是整套架構照搬；release 頁主列表仍殘留 `v1.7.0 Latest` 呈現，需以 evidence 記錄 cross-page 不一致 |
| 7 | python-and-Taiwan-stock-market issue #76 | https://github.com/arleigh418/python-and-Taiwan-stock-market/issues/76 | `DIRECT` | issue opened `2025-05-22`，2025-07 仍有追問 | Repo license 本輪未核；issue 本身無獨立 license | `T86` 路徑漂移與教學碼失效風險的直接現場證據 | 只是 discussion，不是可直接引用的 crawler 實作 |

## 3. 候選細節

### 3.1 FinMind

- Canonical:
  - Repo: https://github.com/FinMind/FinMind
  - Package: https://pypi.org/project/finmind/
- 為何列入：
  - repo 與 PyPI 都明確列出「三大法人買賣」與 `add_kline_institutional_investors` 類型功能，屬直接相關候選。
- 可參考部分：
  - 將原始股價表再補入法人欄位的 augmentation 介面。
  - 把多資料集包成統一 loader / feature layer 的 API 設計。
- 維護跡象：
  - GitHub repo page 顯示 latest release `2.0.5` 於 `2026-07-18`。
  - PyPI page 顯示 `finmind 2.0.5` 於 `2026-07-18` 發布。
- License / boundary：
  - GitHub repo page標示 `Apache-2.0 license`。
  - 但 PyPI 與 repo README 也明寫「本專案提供的所有內容均用於教育、非商業用途」。
  - 推論：至少 code license 與資料內容使用說明存在雙層邊界，後續若只借鏡欄位與流程還可讀；若想直接依賴資料服務，必須額外核定。
- 風險：
  - API request limit 明寫 `300 / hour`，登入帶 token 才可提高到 `600/hr`。
  - 若未來要借鏡，不可把其資料服務使用條款誤當純 Apache-2.0。

### 3.2 twstock

- Canonical:
  - Repo: https://github.com/mlouielu/twstock
  - Package: https://pypi.org/project/twstock/
- 為何列入：
  - 雖不直接處理 `T86`，但它是台股抓取 wrapper 中維護仍相對新、且 request 邊界寫得很清楚的代表。
- 可參考部分：
  - `TWSE` / `TPEX` 來源整合。
  - 首次使用更新 code list 的流程。
  - proxy provider 抽象與 realtime wrapper。
- 維護跡象：
  - GitHub repo page 顯示 latest release `v1.5.1` 於 `2026-04-23`。
  - PyPI page 顯示 `twstock 1.5.1` 於 `2026-04-23` 發布。
- License / boundary：
  - GitHub repo 與 PyPI 都標示 `MIT`。
- 風險：
  - README / PyPI 明寫 `TWSE` request limit 為「每 5 秒 3 個 request，超過可能被 ban」。
  - 與 `T86` 沒有直接 parser/normalizer 關聯，只能借 request 控制與資料層抽象。

### 3.3 twstocks-crawler

- Canonical:
  - Package: https://pypi.org/project/twstocks-crawler/
- 為何列入：
  - seed 明確點名；本輪確實成功讀到 package metadata，因此保留，但排序很後面。
- 可參考部分：
  - 幾乎沒有；僅能證明曾有一個名為 `twstocks-crawler` 的 package 發布。
- 維護跡象：
  - PyPI page 顯示最新版本 `0.0.7` 於 `2022-06-27` 發布。
- License / boundary：
  - PyPI metadata 與 classifier 都標示 `MIT License`。
- 風險：
  - package description 幾乎是空的。
  - PyPI project links 指向的 homepage 在本輪未成功解析成可讀 repo 正文。
  - 沒有任何成功讀到的原始碼頁面能證明它跟 `T86`、三大法人或欄位正規化直接相關。

### 3.4 Asoul/tsec

- Canonical:
  - Repo: https://github.com/Asoul/tsec
  - Related issue: https://github.com/Asoul/tsec/issues/6
- 為何列入：
  - 舊但直接，明確是 TWSE/TPEX 歷史資料 crawler，能作為 batch update flow 的舊世代參考。
- 可參考部分：
  - `crawl.py` / `post_process.py` 的批次抓取與後處理分離。
  - CSV 檔名與逐日資料落盤設計。
- 維護跡象：
  - repo page 顯示 latest release `1.0.1` 於 `2016-03-27`。
  - README 自述最後更新時間 `2017/02/15`。
  - Issue #6 記錄 `TWSE` 改版後 crawler 需重寫，2017-06 有回覆修復。
- License / boundary：
  - 本輪成功讀到的 repo page 檔案列表與 repo navigation 未見 `LICENSE`。
  - 這裡的「授權不明」是依成功讀到的 repo page 所作保守判定，不代表絕對不存在其他授權聲明。
- 風險：
  - 維護停滯。
  - path / cookie 行為容易被站方改版打斷。
  - 無明確授權時，只建議讀概念，不建議挪用 code。

### 3.5 Asoul/tsrtc

- Canonical:
  - Repo: https://github.com/Asoul/tsrtc
- 為何列入：
  - 雖非 `T86`，但它直接分析 `mis.twse.com.tw` 即時欄位，是 request 控制與欄位拆解的歷史參考。
- 可參考部分：
  - `getStockInfo` query pattern 說明。
  - 即時欄位 mapping、資料完整率與重複清洗思路。
- 維護跡象：
  - repo page 顯示 latest release `1.0.2` 於 `2017-02-15`。
  - README 自述最後更新時間 `2017/02/15`。
- License / boundary：
  - 本輪成功讀到的 repo page 未見 `LICENSE`。
- 風險：
  - 即時盤欄位與 `T86` 日報結構不同。
  - README 自承「分析所得，可能有誤」。
  - 仍屬舊路徑與舊 API 分析。

### 3.6 twjackysu/TWSEMCPServer

- Canonical:
  - Repo: https://github.com/twjackysu/TWSEMCPServer
  - File: https://github.com/twjackysu/TWSEMCPServer/blob/main/CLAUDE.md
- 為何列入：
  - 這是本輪最直接、最可操作的 `T86 wrapper` 候選。
  - `CLAUDE.md` 明確寫出 `TWSE Web API` 中含「三大法人買賣超日報、個股明細（/rwd/zh/fund/T86）」與 `history/institutional (T86)` 模組。
- 可參考部分：
  - `tools/history` 的分層方式。
  - 將 `exchangeReport` 與 `rwd/zh/...` 端點分開處理的架構思路。
  - 歷史查詢與本地過濾責任切分。
- 維護跡象：
  - 2026-07-20 查閱 canonical repo 首頁 sidebar，顯示 `Releases 9`，其中 latest release 為 `v1.8.0`、日期 `2026-07-19`。
  - 同日查閱 `https://github.com/twjackysu/TWSEMCPServer/releases`，主列表仍把 `v1.7.0` 標成 `Latest`，日期 `2026-07-18`；本報告將此視為 GitHub cross-page 呈現不一致，已記錄於 verification evidence。
  - repo page 顯示 `176 commits`、`3 issues`。
- License / boundary：
  - repo page 與 `LICENSE` 導覽都顯示 `MIT license`。
- 風險：
  - 專案本體是 MCP server，抽用時要抓資料層，不要把 MCP / prompt / tool wiring 一起照搬。
  - 其 README/CLAUDE 對 endpoint 行為的敘述仍需要之後在我們自己的 source gate 下再次對官方來源核定。

### 3.7 python-and-Taiwan-stock-market issue #76

- Canonical:
  - Issue: https://github.com/arleigh418/python-and-Taiwan-stock-market/issues/76
- 為何列入：
  - 它不是實作 repo 候選，而是最直接的 `T86` 路徑漂移 / 教學碼失效證據。
- 可參考部分：
  - issue 內保留了舊寫法 `https://www.twse.com.tw/fund/T86?...date=...&selectType=...`。
  - 後續留言指出使用者在 2025-07 看見的 XHR 變成 `https://www.twse.com.tw/rwd/zh/fund/T86?response=json&_=...`。
- 維護跡象：
  - issue opened `2025-05-22`，之後到 `2025-07-11` 仍有新追問。
- License / boundary：
  - 這是 discussion 證據，不是可直接複製的授權實作。
- 風險：
  - 只能用來提醒「硬編 path 很脆弱」，不能拿來當穩定 parser 契約。

## 4. 沒找到的東西

- 沒有找到一個仍在積極維護、且專門只做 `T86` crawler/parser/wrapper 的單一知名 repo。
- `twstocks-crawler` 在本輪只成功讀到 PyPI package metadata，沒有成功補到可讀的原始 repo 正文。
- 因此若後續要做 synthesis，不應假設「社群已有成熟 T86 專用套件可直接採納」。

## 5. Source tracker

Access date 均為 `2026-07-20`。

| ID | Status | URL | 用途 |
|---|---|---|---|
| S01 | `retrieved` | https://github.com/FinMind/FinMind | FinMind repo、release、license、README 內容 |
| S02 | `retrieved` | https://pypi.org/project/finmind/ | FinMind PyPI release、metadata、request note |
| S03 | `retrieved` | https://github.com/mlouielu/twstock | twstock repo、release、license、README 內容 |
| S04 | `retrieved` | https://pypi.org/project/twstock/ | twstock PyPI release、MIT、request limit |
| S05 | `retrieved` | https://pypi.org/project/twstocks-crawler/ | package 存在性、release、MIT、description 缺失 |
| S06 | `retrieved` | https://github.com/Asoul/tsec | 歷史 crawler、release、license 未見、README 最後更新 |
| S07 | `retrieved` | https://github.com/Asoul/tsec/issues/6 | 站方改版導致 crawler 要重寫的直接證據 |
| S08 | `retrieved` | https://github.com/Asoul/tsrtc | 即時 API 分析、release、license 未見、README 最後更新 |
| S09 | `retrieved` | https://github.com/twjackysu/TWSEMCPServer | repo、MIT、repo sidebar latest release `v1.8.0 / 2026-07-19`、commit 數量 |
| S10 | `retrieved` | https://github.com/twjackysu/TWSEMCPServer/blob/main/CLAUDE.md | `/rwd/zh/fund/T86` 與 `history/institutional (T86)` 明文證據 |
| S11 | `retrieved` | https://github.com/arleigh418/python-and-Taiwan-stock-market/issues/76 | `T86` 路徑漂移 / 教學碼脆弱性證據 |
| S12 | `failed` | PyPI `twstocks-crawler` project link homepage click-through | 本輪未成功解析成可讀 repo 正文，因此未用來支持任何結論 |

## 6. 建議給下一張 synthesis 卡

1. 優先讀 `TWSEMCPServer` 的 `history/institutional` 分層，抽的是 endpoint 分群與 schema 正規化責任，不是 MCP 介面本身。
2. 再讀 `FinMind`，只借資料增補與欄位整合手法；其資料服務與使用條款需獨立看待。
3. 用 `twstock` 補 request discipline、proxy 與 code update 的實務做法。
4. 把 `issue #76` 當成風險案例，提醒後續實作不要把 `T86` 路徑與 query 參數硬寫死成唯一契約。
