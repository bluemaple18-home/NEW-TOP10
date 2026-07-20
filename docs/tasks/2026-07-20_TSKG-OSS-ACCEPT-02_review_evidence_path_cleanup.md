---
card_id: TSKG-OSS-ACCEPT-02
chain_id: TSKG-OSS
title: Sanitize host paths in acceptance review evidence
status: DELIVERED_CANDIDATE
type: acceptance-cleanup
owner: Codex 主線
assignee: independent-visible-thread
created_on: 2026-07-20
thickness: minimal
risk: low
model: gpt-5.4
reasoning: low
model_reason: 已定位為單一 review evidence 的主機資訊清理，只需保留可重現語意並以中性 placeholder 取代本機值
source_kind: commit
source_sha: 938f583
source_branch: codex/tskg-mfo-src-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-OSS-ACCEPT-02/verification.md
---

# TSKG-OSS-ACCEPT-02：Review evidence 主機資訊清理

## Acceptance finding

`REVIEW-TSKG-OSS-ACCEPT-01` 已正確判定 cleanup candidate 為 GO，但其共享 review evidence 又記入實際 worktree／git metadata 路徑，並逐字保存 host-path 掃描規則，使文件本身重新命中同一 gate。

本卡只清理 review evidence 的本機資訊呈現，不改 GO verdict、reviewed SHA、finding、exit code 或候選內容。

## Must produce

1. 將實際 worktree 路徑改成 `<local-only-worktree>`。
2. 將實際 git metadata 路徑改成 `<repo-gitdir>/worktrees/<worktree-id>`。
3. 將會自我命中的 host-path scan 命令逐字內容改成 `<host-path-scan>`，保留 exit code、掃描範圍與判定。
4. 新增本卡 verification evidence；文件不得記入任何主機專屬路徑、使用者名稱或本機 file URI。
5. 任務卡狀態只可到 `DELIVERED_CANDIDATE`。

## Allowlist

- `docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md`
- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`
- `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md`

## Forbidden scope

- 不修改 cleanup candidate、原 OSS 卡、研究報告、研究 verification、其他 Review／Repair evidence、code、config、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不改 review verdict、reviewed SHA、P0–P3、Spec／Standards axes、exit code 或 remaining risk 的語意。
- 不連外、不 merge、不 push、不建立 ADR。

## Verification

- exact／word diff 證明只有本機資訊呈現被 placeholder 化，以及新增本卡／evidence。
- exact changed files 符合 allowlist。
- 對全部本次 TSKG OSS 共享文件執行 host-path gate，無匹配。
- `git diff --check` 通過。
- candidate 交付完整 SHA、parent、changed files 與 exit codes。

## Stop conditions

- 若需要刪除或改寫 substantive review 結論才能通過，停止並回報。
- 若發現 allowlist 外的第二個新問題，不擴大本卡。
- 同一 blocker 累計失敗三次即停止。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md
source_kind: commit
source_sha: 938f583
provisioning_branch: codex/tskg-mfo-src-01
previous_card_id: TSKG-OSS-ACCEPT-01
previous_thread_id: 019f7e6e-ba1c-74c3-a3dd-c5fc1c9c2b70
previous_review_thread_id: 019f7e71-ba56-7aa0-b256-2d65ed161ab3
source_worktree_clean: clean pre-edit
git_metadata_writable: confirmed preflight
index_lock: clear preflight
unrelated_dirty_paths: [] in source worktree
thread_id: 019f708e-2c20-7262-8102-6144674d54ce
worktree_path: <local-only-worktree>
turn_status: DELIVERED_CANDIDATE
gate_1_card_contract: drafted
gate_2_visible_thread: satisfied
gate_3_candidate_delivery: delivered_candidate
gate_4_independent_review: pending
gate_5_mainline_acceptance: blocked pending cleanup
```
