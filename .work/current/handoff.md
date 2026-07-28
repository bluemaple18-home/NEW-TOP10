---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-HANDOFF
status: READY_FOR_DISPATCH
type: handoff
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

## Active state

- Current dispatch source包含 `5e6c038...`。
- Repo tracked changes在本 handoff commit前僅包含交接文件。
- Fog LaunchAgent unloaded。
- Retry circuit open；沒有直接刪除或旋轉。
- Local runtime evidence：
  `artifacts/autonomous_research/run_2026-07-28_115728`

## In progress / remaining work

1. Phase 0建立 zero exact-date topic的 deterministic RED。
2. 修正 eligibility並覆蓋 index／fallback／queue。
3. 跑 targeted、full suite、py_compile、diff check與 allowlist audit。
4. 產生 candidate後停在 `READY_FOR_INDEPENDENT_REVIEW`。
5. 主線另開 Reviewer，GO後才整合並重回 I5。

## Blocked & errors

- Selected topic：
  `strategy-matrix:artifacts-backtest-production_baseline_harness_smoke:long_horizon`
- Error：
  `FileNotFoundError: ranking artifacts 沒有 exact-match regime 日期`
- Outcome：`NO_COMPARISON_EVIDENCE`
- 三次 live probe停損已達上限，不可再試第四次。

## Key decisions & resolved questions

- Source lineage已證明正常，這次不是 source date缺失。
- Matrix exact-regime filter是正確第二道防線，不得放寬。
- 本輪先修已證明的 eligibility缺口；正式 canary mode不併入本卡。
- Combined independent Review必須檢查 `33aee4d..candidate`，不可只看新一個
  commit而漏掉 stacked source-lineage變更。

## Do not touch

Production model、ranking、weights、baseline、promotion、queue policy、manager
history、LaunchAgent、retry circuit與live artifacts。
