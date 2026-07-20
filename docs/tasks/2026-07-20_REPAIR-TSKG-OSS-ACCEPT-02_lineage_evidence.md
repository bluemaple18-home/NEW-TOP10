---
card_id: REPAIR-TSKG-OSS-ACCEPT-02
chain_id: TSKG-OSS
title: Correct non-self-referential candidate lineage evidence
status: CARD_DRAFTED
type: repair
owner: Codex 主線
assignee: independent-visible-repair-thread
created_on: 2026-07-20
thickness: minimal
risk: low
model: gpt-5.4
reasoning: low
model_reason: 單一 P1 evidence metadata 修復，接受條件已由原 reviewer 明確化，不涉及研究內容或架構判斷
source_kind: commit
source_sha: e0bfe6712dc1af1e3558e124f10a7d03632471de
source_parent: ab4595be037bebf28e201010440dc9bc0aa3f84e
review_commit: 82a68f9c7fef94cbc17ec10bf49d5b9345e05459
review_clarification_commit: ca85f678670254908744ab7848952b68fd253bf4
reviewer_thread_id: 019f7e7a-241e-7412-86f6-9e69538c7e28
source_branch: codex/tskg-oss-accept02-repair
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-OSS-ACCEPT-02/verification.md
---

# REPAIR-TSKG-OSS-ACCEPT-02：Candidate lineage evidence 修復

## Repair target

只修原 reviewer 的單一 P1：`docs/evidence/TSKG-OSS-ACCEPT-02/verification.md` 把 delivery candidate 留為 pending，且沒有清楚區分 acceptance source、card commit、original candidate 與 repair candidate 的 immutable lineage。

Reviewer 已在 clarification commit 確認：不得要求 Git commit 在自身內容回寫自己的最終 SHA。最終 Repair SHA 應由 task final receipt 與同一 reviewer 的 re-review evidence 固定。

## Must produce

1. 移除含糊的 `source_candidate`、`candidate_head: pending` 與舊 `candidate_parent` 欄位。
2. 在 verification frontmatter 明確記錄：
   - acceptance source SHA `938f583eeb361692976c123b12bf5bd134f42848`；
   - original cleanup card commit `ab4595be037bebf28e201010440dc9bc0aa3f84e`；
   - original delivered candidate `e0bfe6712dc1af1e3558e124f10a7d03632471de` 與 parent；
   - 本 Repair 卡 commit 與 expected repair-candidate parent；
   - repair candidate 最終 SHA 由 final receipt＋re-review evidence 綁定，不在自身 commit 內自我引用。
3. 將 preflight 表格的舊 HEAD／parent 敘述改成語意明確的 original delivery 與 repair preflight lineage。
4. 保留 placeholder cleanup、GO verdict、所有既有 SHA 判定、findings、exit-code 語意與 host-path gate 結論。
5. Repair 卡狀態只可到 `REPAIR_READY`。

## Allowlist

- `docs/tasks/2026-07-20_REPAIR-TSKG-OSS-ACCEPT-02_lineage_evidence.md`
- `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md`

## Forbidden scope

- 不修改原 review evidence、其他任務卡、OSS 研究／verification、code、config、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不改 placeholder cleanup、GO verdict、reviewed SHA、findings、exit code 或研究語意。
- 不把 Repair candidate 自身 SHA 寫進同一個 candidate commit。
- 不連外、不 merge、不 push、不建立 ADR。

## Verification

- exact／word diff 證明只修 lineage metadata、preflight 描述與本 Repair 卡狀態。
- changed files 完全符合兩檔 allowlist。
- verification 不再含 pending candidate 或含糊 lineage 欄位。
- 全部本次 TSKG OSS 共享文件通過 host-path gate。
- `git diff --check` 通過。
- final 回報完整 repair candidate SHA／parent；送回原 reviewer thread re-review。

## Stop conditions

- 若修復需要自我引用 candidate SHA，停止並回報契約衝突。
- 若需要改 substantive review／research 內容，停止並回報 scope expansion。
- 同一 blocker 累計失敗三次即停止。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_REPAIR-TSKG-OSS-ACCEPT-02_lineage_evidence.md
source_kind: commit
source_sha: e0bfe6712dc1af1e3558e124f10a7d03632471de
source_parent: ab4595be037bebf28e201010440dc9bc0aa3f84e
review_commit: 82a68f9c7fef94cbc17ec10bf49d5b9345e05459
review_clarification_commit: ca85f678670254908744ab7848952b68fd253bf4
provisioning_branch: codex/tskg-oss-accept02-repair
source_worktree_clean: pending post-card commit
git_metadata_writable: pending preflight
index_lock: clear at card drafting
unrelated_dirty_paths: [] in repair-base worktree
thread_id: pending
worktree_path: pending
turn_status: pending
gate_1_card_contract: drafted
gate_2_visible_thread: pending
gate_3_candidate_delivery: pending
gate_4_same_reviewer_re_review: pending
gate_5_mainline_acceptance: blocked pending repair
```
