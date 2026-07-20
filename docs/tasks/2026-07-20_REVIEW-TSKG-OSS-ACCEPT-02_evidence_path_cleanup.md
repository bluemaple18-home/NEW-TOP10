---
card_id: REVIEW-TSKG-OSS-ACCEPT-02
chain_id: TSKG-OSS
title: Independent review of acceptance evidence path sanitization
status: CARD_DRAFTED
type: review
owner: Codex 主線
assignee: independent-visible-review-thread
created_on: 2026-07-20
thickness: minimal
risk: low
model: gpt-5.4
reasoning: medium
model_reason: 需獨立證明 placeholder 化沒有改變 review 語意，並驗證 reviewer 自己的輸出也符合共享文件路徑規範
source_kind: commit
source_sha: e0bfe6712dc1af1e3558e124f10a7d03632471de
candidate_parent: ab4595be037bebf28e201010440dc9bc0aa3f84e
acceptance_source: 938f583eeb361692976c123b12bf5bd134f42848
source_branch: codex/tskg-oss-accept02-review
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/REVIEW-TSKG-OSS-ACCEPT-02/review.md
---

# REVIEW-TSKG-OSS-ACCEPT-02：Review evidence 路徑清理獨立審查

## Review target

固定審查 candidate `e0bfe6712dc1af1e3558e124f10a7d03632471de`，parent 為 `ab4595be037bebf28e201010440dc9bc0aa3f84e`。

## Required review

1. 核對 candidate parent、changed files 與 allowlist。
2. 以 exact／word diff 確認只將實際 worktree、git metadata 與會自我命中的掃描命令內容改成中性 placeholder。
3. 確認原 review 的 GO、reviewed SHA、finding、Spec／Standards axes、exit codes 與 remaining risk 語意未變。
4. 重跑全部本次 TSKG OSS 共享文件的 host-path gate 與 `git diff --check`。
5. 核對 candidate verification 記錄的是實際結果。
6. Reviewer 自己建立的 Review 卡與 review evidence 必須一併納入最後 host-path gate。

## Evidence writing rule

- 共享文件一律使用 `<local-only-worktree>`、`<repo-gitdir>`、`<worktree-id>` 與 `<host-path-scan>`。
- 不得在 Review 卡或 evidence 寫入實際 cwd、git-dir、使用者名稱、主機名稱、本機絕對路徑、本機 file URI，或 host-path regex 的逐字內容。
- commands table 可寫 `<host-path-scan>` 與其 exit code，不可抄回敏感 pattern。

## Allowlist

- `docs/tasks/2026-07-20_REVIEW-TSKG-OSS-ACCEPT-02_evidence_path_cleanup.md`
- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-02/review.md`

## Forbidden scope

- 不修改 candidate、其他 OSS 文件、code、config、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不連外、不 merge、不 push、不建立 ADR。
- NO_GO 時只列 finding 與修復驗收條件，不自行修 candidate。

## Verdict contract

- `GO`：candidate 是 exact allowlist 內的非語意 placeholder cleanup，且 candidate 與 reviewer 新產物都通過 host-path gate。
- `NO_GO`：任一 P0–P2 correctness、scope、evidence 或 standards finding。

輸出必須包含：verdict、reviewed SHA／parent、P0–P3 findings、Spec axis、Standards axis、commands／exit codes、remaining risks。狀態只可到 `REVIEW_GO` 或 `REVIEW_NO_GO`。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_REVIEW-TSKG-OSS-ACCEPT-02_evidence_path_cleanup.md
source_kind: commit
source_sha: e0bfe6712dc1af1e3558e124f10a7d03632471de
candidate_parent: ab4595be037bebf28e201010440dc9bc0aa3f84e
provisioning_branch: codex/tskg-oss-accept02-review
source_worktree_clean: pending post-card commit
git_metadata_writable: pending preflight
index_lock: clear at card drafting
unrelated_dirty_paths: [] in review-base worktree
thread_id: pending
worktree_path: pending
turn_status: pending
gate_1_card_contract: drafted
gate_2_visible_thread: pending
gate_3_candidate_delivery: complete
gate_4_independent_review: pending
gate_5_mainline_acceptance: blocked pending review
```
