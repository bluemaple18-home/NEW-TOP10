---
card_id: TSKG-01
title: Taiwan Stock Knowledge Graph v1.1 可執行規格
status: INTEGRATED
owner: Codex 主線
assignee: TSKG 規格任務
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 核心資料契約、跨模組架構、來源治理與可驗收性仍有高影響歧義
source_sha: d922e3f05decc4e397eb1132db55f0d601eaf6d3
source_branch: codex/tskg-01-executable-spec
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-01/
---

# TSKG-01：Taiwan Stock Knowledge Graph v1.1 可執行規格

任務：把使用者提供的 TSKG v1.0 Design 轉成可派工、可測試、可追溯的 v1.1 Executable Spec。
範圍：資料實體／關係／證據／時間模型、來源治理、ETL 契約、API 契約、MVP 切片與驗收矩陣。
禁區：不實作 crawler、Neo4j、Postgres、Redis、API；不引入交易策略、模型權重或未公開演算法。
驗證：規格出口契約檢查、需求追溯矩陣、關係方向與 evidence schema 範例、slice dependency/frontier 檢查。
證據：輸出至 `docs/evidence/TSKG-01/`，候選交付必須包含完整 commit SHA 與 `git diff --check` 結果。

## 背景與目標

現有 TSKG v1.0 已定義目標、來源優先序、概念架構、初步 entity／relationship、API 與成功指標，但尚缺少可直接交付工程的核心契約。

本卡只負責完成「做什麼、邊界在哪、如何驗收」與垂直切片，不開始產品實作。規格應支援全部上市、上櫃與 ETF，並允許 Top10 與 LLM 透過公開資訊查詢公司、產品、主題、供應鏈及 ETF 關聯。

## Allowlist

- `docs/specs/TSKG_v1.1.md`
- `docs/evidence/TSKG-01/**`
- 本卡狀態與結果區段：`docs/tasks/2026-07-17_TSKG-01_executable_spec.md`

## Forbidden Scope

- `app/**`、`scripts/**`、`tests/**`、`configs/**` 與任何 runtime code/config。
- 安裝套件、建立外部帳號、連線或寫入 Neo4j／Postgres／Redis。
- 實際爬取 MoneyDJ、MOPS、Yahoo、台灣產業價值鏈平台或其他網站。
- 交易策略、預測、feature engineering、排名分數與權重。
- 修改目前 Top10 生產資料契約或既有 M13／UQ 行為。

## 必須產出

1. `TSKG_v1.1.md`，至少包含：
   - Problem、Goal、Actors、In Scope、Out of Scope。
   - BRS → StRS／User Story → SRS → Acceptance 的追溯鏈。
   - Canonical entity identity 與 alias／dedup 規則。
   - Relationship 定義：方向、inverse、對稱性、可推導性與禁止推導情況。
   - 每一 fact／claim 的 evidence、source、擷取時間、有效期間、confidence、extractor/model version。
   - Neo4j／Postgres 的權威來源、一致性、冪等、重跑與失敗恢復契約，但不寫實作碼。
   - LLM extraction 與 deterministic validation／human review 邊界。
   - API 查詢、分頁、圖展開、錯誤、freshness 與 provenance 回傳契約。
   - Daily diff 的新增、修改、失效、衝突與 change report 語意。
   - 資料來源合規／robots／速率限制／保存與刪除政策的決策點。
   - 可量測成功標準及測試資料集定義。
2. MVP 垂直切片表：每張 slice 的輸入、輸出、依賴、blocking edge、驗收與驗證；標示 current frontier。
3. Open Questions／Assumptions／Dependencies／Risks，所有會阻擋實作或驗收的高影響歧義必須明列，不得假裝已解決。
4. `docs/evidence/TSKG-01/requirements_traceability.md`。
5. `docs/evidence/TSKG-01/verification.md`。

## 核心決策約束

- Customer、Supplier、Partner 等優先建模為 Organization 在特定關係中的角色，不預設為互斥 entity type；若採其他模型，必須寫出理由與查詢影響。
- 雙向語意不可用兩份獨立事實造成漂移；inverse relationship 必須定義為儲存或查詢時推導。
- 任何 `SUPPLIES_TO`、`CUSTOMER_OF`、`COMPETITOR_OF`、`UPSTREAM_OF` 等結論都必須可追溯至公開證據，不得把示意圖直接當事實種子。
- 「補漲股」在 v1 只能輸出具可解釋關聯的候選集合，不得形成交易判定或預測。
- 技術選型（Scrapy、Neo4j、Temporal 等）標示為 architecture decision／constraint，不得混寫成使用者需求；`Temporal or Airflow` 必須轉成待決 ADR，不可任意拍板。

## 驗收條件

- 每條 SRS 均可追溯至至少一條 User Story 或業務需求，並對應 Given／When／Then 或等價測試情境。
- 至少覆蓋 Company／Organization、Security、ETF、Theme、Product、Industry、Evidence／Source 與 Relationship Claim 的 canonical schema。
- 至少用 NVIDIA、Meta、Tesla alias，以及 `3017` 公司查詢示例驗證正規化與 API 契約；示例不得宣稱未經證據支持的真實供應關係。
- 明確定義同一事實多來源、來源衝突、資料失效與 entity merge／split 的處理語意。
- API `<300ms` 只可作為有量測方法的 cache-hit SLO；須定義資料量、查詢形狀、percentile、暖機與測試環境。
- 切片遵循 dependency frontier，第一批可執行 slice 不依賴尚未決定的 scheduler 或完整多來源 crawler。
- `git diff --check` 通過，且實際 changed files 完全落在 allowlist。

## 建議 MVP Frontier

先完成 canonical contract＋一個可公開驗證來源的最小垂直路徑：raw fixture → deterministic parser → normalized claim/evidence → local query response。多來源爬取、LLM PDF extraction、Neo4j 雙寫、每日排程與 Top10 整合應在契約確認後分卡。

## 停損條件

- 若關鍵來源使用條款無法確認，只能記為 blocker，不得實際爬取或猜測授權。
- 同一 blocker 累計失敗三次即停止，不做第四次嘗試。
- 若工作需要超出 allowlist 或開始實作，停止並回主線申請新卡。

## Gate 與交付狀態

- Gate 1：卡片契約、scope、model decision、source SHA 與 evidence path 完整。
- Gate 2：正式 thread ID、側邊欄可見、獨立 worktree cwd/path 與非 queued 狀態可驗證。
- 執行線完成時只可回報 `DELIVERED_CANDIDATE`，不得宣稱已接受、整合或完成。
- 後續 Review／Repair／Integration 由主線另行依正式卡片流程處理。

## Result

- Mainline status：`INTEGRATED`；integration commits through `2b6bf97e4a0fad1052a48b1a239c60850a59c6f6`。
- Accepted successor：`1d464d70eabb3139936999a31917979c5e7c20e9`。
- Independent re-review：`REVIEW_GO / GO_WITH_NOTES`；review artifact commit `2b7dbdc1a230f7fdb8e693d32c1778e1531a3ceb`。
- Resolved findings：F-01～F-05。
- Unresolved non-blocking：F-06 baseline digest capture、F-07 benchmark exact response-size feasibility；不得宣稱兩者已完成。
- Current frontier：SLC-01；未授權或完成任何 runtime、crawler、database、API、benchmark 或外部來源存取。
- Mainline acceptance evidence：`docs/evidence/TSKG-01/acceptance.md`。
