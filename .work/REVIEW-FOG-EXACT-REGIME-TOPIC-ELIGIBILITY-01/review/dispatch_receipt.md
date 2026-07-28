---
id: REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-DISPATCH
version: 2
status: RUNNING
---

# Dispatch receipt

## Card contract

- Card：`docs/tasks/2026-07-28_REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01.md`
- Physical card commit：
  `bca6e75c9c576fe6e3e128381fa4b626e0312518`
- Ownership：independent Reviewer
- Thickness／risk：`strict`／`high`
- Model／reasoning：`gpt-5.6-sol`／`xhigh`
- Model reason：正式 thread繼承使用者設定；stacked production scheduler
  contract不降級。
- Review boundary：
  `33aee4d..684d3adf3916100a7eb9bb57c6164f3b67a58064`
- Exact output allowlist：review card receipt、
  `docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review.md`、
  `.work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/**`

## Provisioning source

- Source kind：commit
- Source SHA：`684d3adf3916100a7eb9bb57c6164f3b67a58064`
- Source worktree：`/Users/mattkuo/TOP10new`
- Source branch：
  `codex/fog-exact-regime-topic-eligibility-handoff-20260728`
- Source clean：yes
- Git metadata writable：yes
- Index lock：absent
- Unrelated dirty paths：`[]`

## Formal thread

- Client receipt：
  `client-new-thread:aab4c03a-367b-4d18-94ed-0cb954a55f8d`
- Thread ID：`019fa76b-e568-7653-ade0-a399a3a1aa4a`
- Host：`local`
- Title：`REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01`
- Sidebar/list visible：yes
- Rollout：
  `/Users/mattkuo/.codex/sessions/2026/07/28/rollout-2026-07-28T14-31-34-019fa76b-e568-7653-ade0-a399a3a1aa4a.jsonl`
- Reviewer worktree：
  `/Users/mattkuo/.codex/worktrees/dc9c/TOP10new`
- Reviewer cwd equals worktree：yes
- Reviewer cwd differs from main cwd：yes
- Reviewer HEAD：
  `684d3adf3916100a7eb9bb57c6164f3b67a58064`
- Reviewer branch：detached fixed commit
- Reviewer worktree clean：yes
- Reviewer Git metadata：
  `/Users/mattkuo/TOP10new/.git/worktrees/TOP10new`
- Reviewer index lock：absent
- Turn status：in progress
- Preflight commentary：HEAD精確、worktree clean、cwd隔離；
  capability preflight完成，CodeGraph為 degraded fallback `rg`。

## Workflow and gates

- Workflow：
  `DELIVERED_CANDIDATE → READY_FOR_REVIEW → THREAD_CREATED → RUNNING`
- Gate 1 card contract：PASS
- Gate 2 visible thread：PASS
- Gate 3 candidate delivery：PASS
- Gate 4 independent review：PENDING
- Gate 5 mainline acceptance：NOT_STARTED

## Limits

- Reviewer不得修改 candidate code、自行 Repair、merge、push、deploy或操作
  live Fog runtime。
- 只有 P0／P1可 `REVIEW_NO_GO`；P2／P3只記 residual risk。
- Review結果回主線後，才決定 `REVIEW_GO` acceptance或唯一 Repair transition。
