---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-HANDOFF
status: GO_LOCAL_DETERMINISTIC
type: mainline
---

# Handoff: FOG exact-regime topic eligibility

## Goal

在 matrix執行前排除沒有 exact-match regime ranking 日期的 topic，保留
closed-regime fail-closed契約與合法 no-work receipt。

## Constraints & preferences

- strict task，Executor使用 `gpt-5.6-sol high`。
- 新對話必須使用獨立乾淨 worktree／branch。
- 先 RED，再 production edit。
- Executor不自審、不整合、不執行 live acceptance。

## Completed actions

- I1–I4 time/data authority已整合並 acceptance。
- Processed-semantics repair已整合。
- Installed plist已更新為 reviewed版本，但 worker保持 unloaded。
- Source lineage candidate `be9bb74`已建立。
- Evidence tip `5e6c038...`已驗證 targeted 69與 full 576 tests。
- 三次 bounded live probe證明下一個 blocker是 exact-regime topic eligibility。
- Exact-regime candidate、Repair-1與同一 Reviewer targeted re-review已完成。
- Review verdict：`REVIEW_GO`。
- Local integration：`374792652b8bee8a869052228da78f7a0d4558b4`。
- Main checkout full suite：`587 passed`。

## Active state

- Current task branch已在
  `374792652b8bee8a869052228da78f7a0d4558b4`完成本機整合。
- Worktree clean；branch尚未 push。
- Fog LaunchAgent unloaded。
- Retry circuit open；沒有直接刪除或旋轉。
- Local runtime evidence：
  `artifacts/autonomous_research/run_2026-07-28_115728`

## In progress / remaining work

1. 等待是否 push／開 PR的明確授權。
2. I5 bounded dry與scheduler acceptance若要恢復，另行仲裁三次停損、
   LaunchAgent與 circuit recovery邊界。

## Repair-1 candidate

- SHA：`51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Parent：`e50022a9db130832d9855846d12168a79d454cef`
- Hostile probe：`16/16`
- Targeted：`88 passed`
- Repair worktree full suite唯一失敗為既有 isolated-worktree ledger missing
  ignored artifacts；主 checkout full suite已`587 passed`。
- Re-review：`REVIEW_GO`
- Local integration：`374792652b8bee8a869052228da78f7a0d4558b4`
- Main checkout acceptance：`587 passed`

## Blocked & errors

- Selected topic：
  `strategy-matrix:artifacts-backtest-production_baseline_harness_smoke:long_horizon`
- Error：
  `FileNotFoundError: ranking artifacts 沒有 exact-match regime 日期`
- Outcome：`NO_COMPARISON_EVIDENCE`
- 三次 live probe停損已達上限，不可再試第四次。
- Original P1已由 Repair-1關閉。
- 目前沒有 deterministic code blocker。

## Key decisions & resolved questions

- Source lineage已證明正常，這次不是 source date缺失。
- Matrix exact-regime filter是正確第二道防線，不得放寬。
- 本輪先修已證明的 eligibility缺口；正式 canary mode不併入本卡。
- Combined independent Review必須檢查 `33aee4d..candidate`，不可只看新一個
  commit而漏掉 stacked source-lineage變更。
- Repair-1只關閉`FOG-EXACT-REGIME-REVIEW-P1-001`，不得修改 protected matrix；
  修完由原 Reviewer identity做 targeted re-review。

## Do not touch

Production model、ranking、weights、baseline、promotion、queue policy、manager
history、LaunchAgent、retry circuit與live artifacts。
