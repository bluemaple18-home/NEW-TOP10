---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1-DISPATCH
status: RUNNING
type: visible_thread_receipt
---

# Repair-1 dispatch receipt

- Client receipt：
  `client-new-thread:f1c4ce0f-ed12-4e2d-98fa-611db4551c96`
- Formal task：
  `019fa778-8623-70b1-840d-a542a9a2e46d`
- Worktree：`<codex-worktree>/39c6/TOP10new`
- Source kind：commit
- Source SHA：
  `e50022a9db130832d9855846d12168a79d454cef`
- Source clean：是
- Worktree registered：是
- Main checkout隔離：是
- Git metadata：linked worktree git dir可解析
- `index.lock`：不存在
- Actual model：`gpt-5.6-sol`
- Actual reasoning：`xhigh`
- Workflow：`REVIEW_NO_GO → REPAIR_RUNNING → READY_FOR_REVIEW`
- Original Reviewer：
  `019fa76b-e568-7653-ade0-a399a3a1aa4a`

## Gates

- Gate 1：實體 Repair卡與固定 P1 finding成立。
- Gate 2：正式 task、worktree、source SHA、clean與model receipt成立。
- Gate 3：等待單一 Repair candidate commit與completed turn。
- Gate 4：由原 Reviewer identity做 targeted re-review。
- Gate 5：主線另行 acceptance；本 task不得整合。
