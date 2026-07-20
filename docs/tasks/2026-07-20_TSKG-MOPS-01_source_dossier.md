---
card_id: TSKG-MOPS-01
chain_id: TSKG-SRC
title: MOPS read-only source governance dossier
status: INTEGRATED
type: research
owner: Codex 主線
assignee: TSKG-MOPS-01 research thread
thickness: standard
risk: high
model: gpt-5.5
reasoning: high
model_reason: 來源條款、robots、介面、保存與再散布需多份官方證據交叉驗證；結論影響後續外部存取，但本卡保持唯讀且不做法律核准
source_kind: commit
source_sha: 744bf934cd988b75322cb674c218691de6615b97
source_branch: codex/tskg-mops-01
mainline_dispatcher: TSKG root thread
previous_card: TSKG-SRC-01
previous_implementation_thread: 019f75d7-093b-7ef2-a556-2b20673c5b40
previous_review_thread: 019f75e7-4703-72f0-bdf5-67e8401acbd9
previous_repair_thread: 019f75f3-f8ab-7d50-b0e5-083a57190726
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
operation_level: read_only
evidence_path: docs/evidence/TSKG-MOPS-01/
deliverable_path: docs/research/TSKG-MOPS-01_source_dossier.md
---

# TSKG-MOPS-01：MOPS 唯讀來源治理研究

任務：以官方公開頁面建立公開資訊觀測站（MOPS）的 source-governance dossier，填補 OQ-SRC-01 的可驗證證據；不執行 ingestion、不下載公司資料、不代表法律或 source-owner 核准。

## Root question

MOPS 是否提供足以讓 source/compliance owner 決定 `APPROVED/BLOCKED/EXPIRED` 的官方證據，明確覆蓋 terms/legal basis、robots、allowed method/path/media、authentication、rate/concurrency、user agent/contact、raw/snippet/metadata retention、redaction/deletion、redistribution、review date 與 decision evidence？

## Dependencies and frontier

- `TSKG-SRC-01` 已整合，Source Gate 對任何 `PUBLIC+APPROVED` 維持 fail closed。
- 本卡只產出研究 dossier 與建議，不修改 registry，不解除 OQ-SRC-01。
- SLC-02 只有在本卡完成、獨立 Review 通過，且使用者／source owner 另行明確核准 immutable decision artifact 後才能開始。

## External-tool gate

- 服務：MOPS、臺灣證券交易所及其官方政策／開放資料文件。
- 操作：`read_only`。
- 可用工具：目前已暴露的 web search/open；不安裝 CLI、不登入、不要求 OAuth。
- 只讀政策、使用說明、robots、API／open-data 文件與聯絡資訊頁；禁止呼叫公司資料查詢、下載財報/PDF/HTML raw artifact 或批次 endpoint。
- 不送出表單、不註冊、不登入、不改任何遠端狀態。
- 每個外部結果記錄 access date、工具、URL、成功／失敗、用途；不得引用未成功開啟的頁面。

## Source selection and authority

研究優先序：

1. `mops.twse.com.tw` 官方 robots、首頁、免責／使用條款、操作說明、資料介面文件。
2. `twse.com.tw` 官方網站使用條款、資料使用／授權、open API／open data 文件與聯絡資訊。
3. 若官方頁面指向政府資料開放授權，才讀該官方政府授權頁；不得以第三方文章取代。

搜尋結果只作導航；結論只能依成功讀取的官方頁面。關鍵結論至少兩份官方證據交叉驗證；若只能找到一份或彼此矛盾，標記 `UNVERIFIED/CONFLICTING`，不得補猜。

## Required dossier fields

對每一欄輸出 `FOUND / NOT_FOUND / CONFLICTING / NOT_APPLICABLE`、官方 URL、access date、短摘要、限制與 confidence：

- source/publisher/owner/contact
- terms／legal basis
- robots result（明示 robots 不等於法律授權）
- allowed method、path family、media type
- authentication constraints
- rate limit／concurrency／request frequency
- required user agent／contact identifier
- raw retention、snippet retention、metadata retention
- redaction、deletion/tombstone、legal hold
- redistribution／derivative use／commercial use
- review/expiry requirements
- decision evidence locator

另須列出：

- MOPS 互動式查詢、官方 open API／open data、人工下載等 access channel 是否存在，彼此條款能否互相沿用。
- 哪些 endpoint/path 只在文件出現、哪些實際被官方明示可程式存取；沒有明示就保持 blocked。
- 是否存在禁止自動化、大量下載、重製、再散布、商業使用或繞過限制的文字；只可短摘要，不大量引用。
- robots、terms、open-data license、API docs 的適用範圍是否一致或衝突。

## Decision matrix

Dossier 最後必須給逐通道建議，而不是把整個 MOPS 混成單一結論：

- `interactive_web`
- `official_api_or_open_data`
- `manual_file_download`

每個通道只能建議：

- `RECOMMEND_APPROVAL_REVIEW`：官方證據完整到足以交人核准，但本卡不核准。
- `KEEP_BLOCKED`：任一必要欄缺失、範圍不明、條款衝突或限制未解析。
- `NOT_APPLICABLE`：官方明確不存在該通道。

不得輸出 executable `APPROVED` policy，不得修改 Source Gate fixture。

## Allowed files

- `docs/tasks/2026-07-20_TSKG-MOPS-01_source_dossier.md`
- `docs/research/TSKG-MOPS-01_source_dossier.md`
- `docs/evidence/TSKG-MOPS-01/verification.md`

## Forbidden scope

- 不修改 code、config、fixture、tests、requirements、lockfile、Source Gate registry 或 production API。
- 不下載或保存 MOPS 公司資料、申報內容、PDF、HTML、CSV、JSON raw bytes或 snippet corpus。
- 不呼叫資料查詢 endpoint、不建立 crawler/playwright/http client、不做負載或 rate-limit 測試。
- 不提供法律意見、不把「公開可見」「robots allow」或「官方網站」等同使用授權。
- 不宣稱 MOPS 已核准、不解除 SLC-02、不建立 RawArtifact/Evidence/claim。

## Verification and evidence

- 建立 source tracker：每個 URL 必須標 `retrieved/failed/not_used`；final dossier 只能引用 `retrieved`。
- 對關鍵結論做 cross-source comparison，明列一致、衝突與缺口。
- 所有引用使用短摘要；單一來源不得長篇逐字重製。
- 驗證 deliverable 逐欄完整、所有 cited URLs 已成功讀取、failed URLs 有 recovery 或 gap、日期為 `2026-07-20`。
- 執行 host-specific path scan、changed-file exact allowlist、`git diff --check`、post-commit clean。
- 純研究文件卡，無 runtime 邏輯，TDD 不適用；以 source-trace gate 與 independent Review 驗收。

## Stop conditions

- 官方來源要求登入、驗證碼、帳密、付費、表單或非公開權限時停止，不繞過。
- 需要實際呼叫資料 endpoint、下載 raw content、推測條款或決定法律基礎時停止回主線。
- 同一 blocker 累計失敗三次即停，不做第四次嘗試。

## Delivery contract

- 只回 `DELIVERED_CANDIDATE`，包含完整 SHA/parent、changed files、成功／失敗來源數、決策矩陣、unresolved fields、evidence 與 blockers。
- 必須建立 candidate commit，交獨立 Review；研究線不得自稱 accepted、integrated、source approved 或 SLC-02 unlocked。

## Result

`INTEGRATED`

- Dossier：`docs/research/TSKG-MOPS-01_source_dossier.md`
- Verification：`docs/evidence/TSKG-MOPS-01/verification.md`
- Independent Review：`docs/evidence/TSKG-MOPS-01/review.md`（`GO`）
- Acceptance：`docs/evidence/TSKG-MOPS-01/acceptance.md`
- 逐通道建議：`interactive_web=KEEP_BLOCKED`、`official_api_or_open_data=KEEP_BLOCKED`、`manual_file_download=KEEP_BLOCKED`
- 本結果不是 source-owner／法律核准，不修改 Source Gate，不解除 OQ-SRC-01 或 SLC-02。
