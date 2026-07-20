---
card_id: REPAIR-TSKG-INT-01
chain_id: TSKG-INT
title: Conditionally repair reviewed TSKG integration findings
status: PENDING
type: repair
owner: Codex 主線
assignee: REPAIR-TSKG-INT-01 visible repair thread
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 只有獨立 Review 產生具體 bounded findings 時才執行；範圍由 findings 鎖定，不承擔重新設計或架構決策
source_kind: commit
source_sha: <reviewed-candidate-sha>
mainline_dispatcher: TSKG root thread
previous_card: REVIEW-TSKG-INT-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/REPAIR-TSKG-INT-01/repair.md
---

# REPAIR-TSKG-INT-01：條件式修復 TSKG 整合 findings

## Activation condition

只有 `REVIEW-TSKG-INT-01` 對固定 candidate 回 `REVIEW_NO_GO` 且提供可重現 findings 時啟動。若 Review GO，本卡保持未派工並標記 `NOT_NEEDED`。

## Allowed scope

- 只修改 reviewer 明確列出的 finding paths 與必要 public-behavior tests。
- 新增 `docs/evidence/REPAIR-TSKG-INT-01/repair.md` 與更新本卡 Result/status。
- 每個修復必須可追溯到 finding ID。

## Forbidden scope

- 不擴張 TSKG 功能、不掛 production API、不核准 PUBLIC source。
- 不順手重構、不改模型／排名／ETL／scheduler／部署。
- 不修改 reviewer evidence，不自行宣稱 finding 已關閉。
- Repair 完成後只能交回原 REVIEW thread re-review。

## Verification

- 先重現每個 finding，再補 public-behavior regression test。
- 重跑 reviewer 指定測試、TSKG focused suite、完整 suite 與 `git diff --check`。
- 交付單一 repair candidate SHA、finding-to-test mapping、exact changed files 與 evidence path。

## Stop conditions

- finding 無法重現、需要超出允許範圍、需要改 accepted spec、同一 blocker 第 3 次失敗或 Repair 2 後仍 NO-GO 時停止回主線。

## Result

`PENDING_REVIEW_VERDICT`
