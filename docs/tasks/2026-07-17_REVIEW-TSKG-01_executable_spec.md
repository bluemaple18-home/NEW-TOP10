---
card_id: REVIEW-TSKG-01
title: Review Taiwan Stock Knowledge Graph v1.1 executable spec
status: CARD_DRAFTED
owner: Codex 主線
assignee: 獨立規格 Reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 核心 ontology、evidence、temporal、API 與 ETL 契約需獨立 maker-checker 審查
base_sha: 2855510f740334b2636dfd0c391d93d7e4675706
candidate_sha: fad395589c90254ffbf4f0e7292a36920d019298
reviewed_commit: fad395589c90254ffbf4f0e7292a36920d019298
source_kind: commit
evidence_path: docs/evidence/REVIEW-TSKG-01/
---

# REVIEW-TSKG-01：TSKG v1.1 獨立規格審查

任務：只審查 candidate `fad395589c90254ffbf4f0e7292a36920d019298` 是否滿足 TSKG-01 與原始 v1.0 目標。
範圍：`2855510..fad3955` 的 4 個 docs 檔案；Spec axis 與 Standards axis 分開判定。
禁區：不得修改 candidate、runtime、任務卡以外檔案；不得實作或查外部網站。
驗證：逐項核對 ontology、identity、relationship、evidence/time、conflict、ETL、API、SLO、slice dependency 與 traceability。
證據：輸出 `docs/evidence/REVIEW-TSKG-01/review.md`，結論只能是 `GO` 或 `NO_GO`，findings 需含 severity/path/line/evidence/risk/suggested_fix/validation_gap/confidence。

## Allowlist

- `docs/tasks/2026-07-17_REVIEW-TSKG-01_executable_spec.md` 的 status／Result
- `docs/evidence/REVIEW-TSKG-01/review.md`

## 必查風險

1. `SUPPLIES_TO(A,B)` 與 `CUSTOMER_OF(B,A)` 是否表示同一商業事實卻被允許成兩個 canonical claims；若刻意區分，是否有足夠 qualifiers 與 query semantics 避免重複／矛盾。
2. `RelationshipClaim` 是否具足夠欄位表達 conflict set、resolution decision 與 lineage，而不只是一個 `CONFLICTED` state。
3. API `min_confidence` 是否與「extraction confidence 不等於 truth」契約衝突，尤其 deterministic/human claims 可能沒有 confidence。
4. valid time 的 unknown/open/unbounded 語意是否足以 deterministic round-trip。
5. 31/31 traceability 是否只是 ID coverage，還是真的覆蓋 v1.0 goals、non-goals 與 acceptance。
6. SLC-01 是否真能在未接受 ADR-01／runtime 技術選型時成為 current frontier。

## Reviewer 路由

- correctness：ontology、claim state、time、identity 與 API semantics。
- regression/spec：原始 v1.0 goal/scope/API/Top10 是否被錯改或漏掉。
- security/compliance：來源治理、evidence retention、LLM promotion 邊界。
- performance/test-gap：`<300ms` SLO 與 acceptance datasets 是否可重現。
- maintainability：術語、單一 canonical fact 與 ADR 邊界是否一致。

## Verdict 規則

- P0／P1、核心契約矛盾或無法測試的 acceptance → `NO_GO`。
- 只有 P2/P3 且不影響下一張 SLC-01 實作，可 `GO_WITH_NOTES`，但最終 machine verdict 仍填 `GO` 並列 notes。
- 沒有 findings 時明確寫「未發現阻塞問題」、剩餘風險與驗證缺口。
- 工作結束時只回報 `REVIEW_GO` 或 `REVIEW_NO_GO`、reviewed commit、findings 與 evidence；不得修改 candidate 或宣稱整合。

## Result

待 Reviewer 填寫。
