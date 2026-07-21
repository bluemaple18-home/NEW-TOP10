---
card_id: REVIEW-TSKG-OSS-ACCEPT-02
chain_id: TSKG-OSS
title: Independent review of acceptance evidence path sanitization
status: REVIEW_GO
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
source_sha: 7630b710d88262f691b0b8039b9b2a7d19492ba8
candidate_parent: a6e7b9dd4c34d3cb6aba6203d5e4724e8bb3ddc3
acceptance_source: 938f583eeb361692976c123b12bf5bd134f42848
source_branch: codex/tskg-oss-accept02-review
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/REVIEW-TSKG-OSS-ACCEPT-02/review.md
---

# REVIEW-TSKG-OSS-ACCEPT-02：Review evidence 路徑清理獨立審查

## Review target

本卡已由同一 reviewer 完成 re-review，最終審查 candidate `7630b710d88262f691b0b8039b9b2a7d19492ba8`，parent 為 `a6e7b9dd4c34d3cb6aba6203d5e4724e8bb3ddc3`。原始 NO_GO candidate 為 `e0bfe6712dc1af1e3558e124f10a7d03632471de`，對應 review commit `82a68f9c7fef94cbc17ec10bf49d5b9345e05459`，clarification commit 為 `ca85f678670254908744ab7848952b68fd253bf4`。

## Required review

1. 核對 candidate parent、changed files 與 allowlist。
2. 以 exact／word diff 確認只修 lineage evidence 與 repair 卡狀態，不改 placeholder cleanup 語意。
3. 確認原 review 的 GO、reviewed SHA、finding、Spec／Standards axes、exit codes 與 remaining risk 語意未變。
4. 重跑全部本次 TSKG OSS 共享文件的 host-path gate 與 `git diff --check`。
5. 核對 repair candidate verification 已移除 pending/含糊 fields，改以 immutable lineage + final receipt/re-review evidence 綁定最終 SHA。
6. Reviewer 自己更新的 Review 卡與 review evidence 必須一併納入最後 host-path gate。

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
- 若 re-review 仍是 NO_GO，只列 finding 與修復驗收條件，不自行修 candidate。

## Verdict contract

- `GO`：repair candidate 在 exact allowlist 內完成 non-self-referential lineage repair，且 candidate 與 reviewer 新產物都通過 host-path gate。
- `NO_GO`：任一 P0–P2 correctness、scope、evidence 或 standards finding。

輸出必須包含：verdict、reviewed SHA／parent、P0–P3 findings、Spec axis、Standards axis、commands／exit codes、remaining risks。狀態只可到 `REVIEW_GO` 或 `REVIEW_NO_GO`。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_REVIEW-TSKG-OSS-ACCEPT-02_evidence_path_cleanup.md
source_kind: commit
source_sha: 7630b710d88262f691b0b8039b9b2a7d19492ba8
candidate_parent: a6e7b9dd4c34d3cb6aba6203d5e4724e8bb3ddc3
provisioning_branch: codex/tskg-oss-accept02-review
source_worktree_clean: clean pre-review
git_metadata_writable: confirmed preflight
index_lock: clear preflight
unrelated_dirty_paths: [] in review-base worktree
thread_id: 019f7e7a-241e-7412-86f6-9e69538c7e28
worktree_path: <local-only-worktree>
turn_status: REVIEW_GO
gate_1_card_contract: drafted
gate_2_visible_thread: satisfied
gate_3_candidate_delivery: complete
gate_4_independent_review: REVIEW_GO
gate_5_mainline_acceptance: ready for mainline integration
```

## Review result

`GO`

Repair candidate `7630b710d88262f691b0b8039b9b2a7d19492ba8` resolves the original evidence-integrity issue under the clarified non-self-referential contract. The repaired verification artifact now records immutable input lineage, binds final repair SHA externally through task receipt plus same-reviewer evidence, and preserves the original placeholder cleanup semantics.

## Findings

- `P0`: none
- `P1`: none
- `P2`: none
- `P3`: none

## Spec axis

`GO`

- The repair candidate parent, exact two-file changed set, exact and word diff behavior, host-path gate, and `git diff --check` all satisfy the clarified repair acceptance contract.
- Verification no longer relies on impossible self-reference. Final repair SHA is instead fixed by task final receipt plus same-reviewer re-review evidence.

## Standards axis

`GO`

- Evidence integrity is restored while remaining implementable in Git.
- The repair remains docs-only, host-neutral, and preserves original placeholder cleanup, GO semantics, findings semantics, and exit-code semantics.

## Mainline-ready chain

- acceptance source `938f583eeb361692976c123b12bf5bd134f42848`
- original cleanup card commit `ab4595be037bebf28e201010440dc9bc0aa3f84e`
- original candidate `e0bfe6712dc1af1e3558e124f10a7d03632471de`
- original NO_GO review `82a68f9c7fef94cbc17ec10bf49d5b9345e05459`
- clarification `ca85f678670254908744ab7848952b68fd253bf4`
- repair card commit `a6e7b9dd4c34d3cb6aba6203d5e4724e8bb3ddc3`
- repaired candidate `7630b710d88262f691b0b8039b9b2a7d19492ba8`
- same-reviewer re-review `GO`
