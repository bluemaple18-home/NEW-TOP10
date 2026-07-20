---
card_id: TSKG-OSS-ACCEPT-01
chain_id: TSKG-OSS
title: Remove host-specific worktree path from shared OSS card
status: CARD_DRAFTED
type: acceptance-cleanup
owner: Codex 主線
assignee: independent-visible-thread
created_on: 2026-07-20
thickness: minimal
risk: low
model: gpt-5.4
reasoning: low
model_reason: 單一已定位的共享文件路徑合規修正，只需精確替換與機械驗證，不需要架構推理
source_kind: commit
source_sha: 64e5bb2
source_branch: codex/tskg-mfo-src-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-OSS-ACCEPT-01/verification.md
---

# TSKG-OSS-ACCEPT-01：共享卡片 host path 清理

## Acceptance finding

主線 Gate 5 在整合研究與 re-review GO 後，發現：

- `docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md` 的 receipt 仍保存某台電腦的 worktree 絕對路徑。
- 即使標示 local-only，共享任務卡仍不得保存主機專屬絕對路徑或本機 file URI。

本卡只做一處非語意、可重現的合規清理，不改研究結論、來源、版本、排序或審查 verdict。

## Must produce

1. 將該 `worktree_path` 值改為不含主機資訊的描述，例如 `<local-only-worktree verified in preflight>`。
2. 新增本卡 verification evidence，記錄 source SHA、exact diff、allowlist、host-path scan 與 `git diff --check`。
3. 任務卡狀態只可到 `DELIVERED_CANDIDATE`。

## Allowlist

- `docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-01_host_path_cleanup.md`
- `docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md`
- `docs/evidence/TSKG-OSS-ACCEPT-01/verification.md`

## Forbidden scope

- 不修改研究報告、原研究 verification、Review／Repair evidence、code、config、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不改任何研究結論、URL、release metadata、License、directness、候選排序或 GO verdict。
- 不連外、不 push、不 merge、不建立 ADR。

## Verification

- `git diff --word-diff=porcelain` 證明只有指定 path 值與本卡/evidence 新增。
- exact changed files 符合 allowlist。
- 對本次 TSKG OSS 共享文件執行 host-specific path scan，結果無匹配。
- `git diff --check` 通過。
- 交付完整 candidate SHA、parent、changed files 與 exit codes。

## Stop conditions

- 若掃描找到第二個 host-specific path，停止並回報，不擴大本卡自行修復。
- 若需要修改研究語意或 Review 結論才能通過，停止並交回主線。
- 同一 blocker 累計失敗三次即停止。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-01_host_path_cleanup.md
source_kind: commit
source_sha: 64e5bb2
provisioning_branch: codex/tskg-mfo-src-01
previous_repair_thread_id: 019f7e66-00fd-7583-86bf-2f56944ea70b
previous_reviewer_thread_id: 019f7e60-0da2-71d1-b9cb-76f794312ee6
source_worktree_clean: pending post-card commit
git_metadata_writable: pending preflight
index_lock: clear at card drafting
unrelated_dirty_paths: [] in source worktree
thread_id: pending
worktree_path: pending
turn_status: pending
gate_1_card_contract: drafted
gate_2_visible_thread: pending
gate_3_candidate_delivery: pending
gate_4_independent_review: pending
gate_5_mainline_acceptance: blocked pending cleanup
```
