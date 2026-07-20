---
card_id: TSKG-MOPS-01-REVIEW
chain_id: TSKG-SRC
title: MOPS source-governance dossier independent review
status: REVIEW_GO
type: review
owner: Codex 主線
assignee: independent review thread
created_on: 2026-07-20
model: gpt-5.5
reasoning: high
source_kind: commit
source_sha: d5e9f4660e082b6879490768a56a4385d064c3c5
source_parent: 744bf934cd988b75322cb674c218691de6615b97
---

# TSKG-MOPS-01 independent Review

## 目標

獨立審查 MOPS 唯讀來源治理 dossier 的證據可追溯性、授權邊界與 fail-closed 結論。只做 Review，不修改候選文件、不核准來源、不啟動 ingestion。

## 固定範圍

- Candidate：`d5e9f4660e082b6879490768a56a4385d064c3c5`
- Review 對象：
  - `docs/tasks/2026-07-20_TSKG-MOPS-01_source_dossier.md`
  - `docs/research/TSKG-MOPS-01_source_dossier.md`
  - `docs/evidence/TSKG-MOPS-01/verification.md`
- 可唯讀開啟 dossier 列出的 14 個官方 URL 以核對取證；不得呼叫資料 endpoint、下載附件、登入、送表單或寫入外部服務。

## 必查項目

1. Candidate SHA、parent 與 exact three-file allowlist 正確。
2. 11 retrieved（含 2 limited）／3 failed 的 tracker 計數可重現；失敗 URL 未被當作實質證據。
3. 每個被引用的 URL 確為官方來源且曾成功讀取；正文結論不依賴 search snippet 或 limited landing。
4. MOPS interactive、TWSE 一般條款、政府 OGL dataset、TWSE OpenAPI landing、Data E-Shop 的適用範圍被清楚分離。
5. 不把 endpoint 文件存在誤寫成 programmatic access permission，不把 OGL 擴張到全站、附件或財報。
6. terms、robots、method/path/media、auth、rate/concurrency、UA、retention、redaction/deletion/legal hold、redistribution、review/expiry、rights owner 等必要欄位均有證據或明確 gap。
7. 三通道 matrix 保守且一致：全為 `KEEP_BLOCKED`；OQ-SRC-01 與 SLC-02 未解除，無 `APPROVED` policy、registry、fixture 或 ingestion 變更。
8. shared docs 無本機絕對路徑、secret、PII 或法律核准式過度宣稱；驗證命令與 allowlist 可重現。

## 交付契約

在 `docs/evidence/TSKG-MOPS-01/review.md` 產出：

- Spec axis 與 Standards axis 分開判定。
- Findings 依 P0–P3 排序，含 `path:line`、觸發條件、風險與最小修法。
- Source-trace 重驗表與實際成功／失敗數。
- 最終 verdict 僅能是 `GO` 或 `NO_GO`。
- `GO` 只表示研究文件可整合，不表示核准 MOPS 或解除 Source Gate。
- 若 `NO_GO`，列出 repair allowlist；不得自行修改候選。

## Result

`GO`

- Reviewed candidate：`d5e9f4660e082b6879490768a56a4385d064c3c5`。
- Candidate parent：`744bf934cd988b75322cb674c218691de6615b97`。
- Spec axis：`GO`；Standards axis：`GO`。
- Findings：未發現 P0–P3 finding。
- Source trace：`11 retrieved`（其中 `9 substantive`、`2 limited landing`）／`3 failed`，與 candidate tracker 一致。
- Verdict 邊界：本 `GO` 只表示研究文件可整合；不核准 MOPS，不解除 OQ-SRC-01 或 SLC-02，三個 access channel 全部維持 `KEEP_BLOCKED`。
- Evidence：`docs/evidence/TSKG-MOPS-01/review.md`。
- Review commit：完整 SHA 由 reviewer 最終回報，避免 commit 自參照。
