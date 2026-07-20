---
card_id: REVIEW-TSKG-OSS-ACCEPT-02
chain_id: TSKG-OSS
title: Independent review of acceptance evidence path sanitization
status: REVIEW_NO_GO
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
source_worktree_clean: clean pre-review
git_metadata_writable: confirmed preflight
index_lock: clear preflight
unrelated_dirty_paths: [] in review-base worktree
thread_id: 019f708e-2c20-7262-8102-6144674d54ce
worktree_path: <local-only-worktree>
turn_status: REVIEW_NO_GO
gate_1_card_contract: drafted
gate_2_visible_thread: satisfied
gate_3_candidate_delivery: complete
gate_4_independent_review: REVIEW_NO_GO
gate_5_mainline_acceptance: blocked by candidate verification mismatch
```

## Review result

`NO_GO`

Candidate `e0bfe6712dc1af1e3558e124f10a7d03632471de` preserves the intended placeholder cleanup in its edited review evidence and stays within the candidate card allowlist, but its own verification artifact does not record the actual delivered candidate SHA/parent. Because the review contract explicitly requires candidate verification to reflect actual results, this is an evidence-integrity miss and blocks acceptance.

## Findings

- `P1` candidate verification metadata does not match the delivered candidate: `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md:5`, `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md:6`, `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md:7`, `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md:23`, `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md:24`
  The artifact still says `source_candidate: 938f583`, `candidate_head: pending single candidate commit`, and `candidate_parent: 938f583`, while the reviewed candidate is `e0bfe6712dc1af1e3558e124f10a7d03632471de` with parent `ab4595be037bebf28e201010440dc9bc0aa3f84e`. The preflight table also records the pre-edit ancestry instead of the delivered candidate ancestry. This fails the card requirement that candidate verification capture actual SHA/parent/verification results.

## Spec axis

`NO_GO`

- Candidate parent, changed files, exact diff, word diff, host-path gate, and `git diff --check` all satisfy the cleanup scope.
- The candidate does not satisfy Required review item 5 because its verification evidence does not record the actual delivered candidate lineage.

## Standards axis

`NO_GO`

- Evidence integrity is part of the acceptance contract for this docs-only cleanup.
- Placeholder sanitization is correct, but a verification artifact that leaves final candidate identity pending is not a trustworthy acceptance record.

## Required acceptance fix

- Update `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md` so the delivered candidate SHA and parent match `e0bfe6712dc1af1e3558e124f10a7d03632471de` and `ab4595be037bebf28e201010440dc9bc0aa3f84e`.
- Replace the pre-edit ancestry rows with the actual delivered-candidate lineage or clearly separate pre-edit checks from final delivered-candidate checks.
- Re-run the same allowlist diff, broader host-path gate, and `git diff --check`, then record the observed exit codes.
