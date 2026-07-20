---
card_id: REVIEW-TSKG-OSS-ACCEPT-01
chain_id: TSKG-OSS
title: Independent review of shared-card host-path cleanup
status: CARD_DRAFTED
type: review
owner: Codex 主線
assignee: independent-visible-review-thread
created_on: 2026-07-20
thickness: minimal
risk: low
model: gpt-5.4
reasoning: medium
model_reason: 只需獨立核對單一非語意替換、allowlist 與 host-path gate，但仍需固定 SHA 與可重現證據
source_kind: commit
source_sha: 6dc908a52b79a5db85648343eb6696ab69baa733
candidate_parent: f723b64ebc13733bbcefc93feb460558246f018a
acceptance_source: 64e5bb22ae0847d18e2b50f3662cd55e16724725
source_branch: codex/tskg-oss-accept-review
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md
---

# REVIEW-TSKG-OSS-ACCEPT-01：共享卡片 host path 清理獨立審查

## Review target

固定審查 candidate `6dc908a52b79a5db85648343eb6696ab69baa733`，parent 為 `f723b64ebc13733bbcefc93feb460558246f018a`。

本 review 只判定 acceptance-cleanup 是否為一處非語意、合規、可整合的修正；不得修改 candidate。

## Required review

1. 核對 candidate parent、changed files 與卡片 allowlist。
2. 以 exact diff／word diff 確認原 OSS-02 卡只替換 `worktree_path` 值，沒有研究語意、來源、版本、排序或 verdict 改動。
3. 核對新值不含主機名稱、使用者名稱或本機絕對路徑。
4. 對本次 TSKG OSS 共享文件重跑 host-specific path scan。
5. 核對 verification evidence 記的是實際命令與 exit code，不只是預期文字。
6. 重跑 `git diff --check`，確認 worktree clean、無 index lock。

## Allowlist

- `docs/tasks/2026-07-20_REVIEW-TSKG-OSS-ACCEPT-01_host_path_cleanup.md`
- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`

## Forbidden scope

- 不修改 cleanup candidate、OSS 研究／verification、原 Review／Repair evidence、code、config、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不連外、不 merge、不 push、不建立 ADR。
- NO_GO 時只列具體 finding 與 repair acceptance；不得自行修復。

## Verdict contract

- `GO`：candidate 是 exact allowlist 內的非語意 host-path cleanup，所有 gate 可重現通過。
- `NO_GO`：出現任一 P0–P2 correctness、scope、evidence 或 standards finding。

輸出必須包含：verdict、reviewed SHA／parent、P0–P3 findings、Spec axis、Standards axis、commands／exit codes、remaining risks。狀態只可到 `REVIEW_GO` 或 `REVIEW_NO_GO`。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_REVIEW-TSKG-OSS-ACCEPT-01_host_path_cleanup.md
source_kind: commit
source_sha: 6dc908a52b79a5db85648343eb6696ab69baa733
candidate_parent: f723b64ebc13733bbcefc93feb460558246f018a
provisioning_branch: codex/tskg-oss-accept-review
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
