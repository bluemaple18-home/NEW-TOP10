---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-BRIEF
status: READY_FOR_DISPATCH
type: handoff
---

# Current Brief

## Main task

`FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01`

Closed-regime source lineage 已修復並驗證；目前 blocker 是 scheduler 仍會選到
沒有 exact-match regime ranking 日期的 topic。下一個獨立 Executor 必須先做
RED，再於 matrix 執行前將該 topic fail closed。

## Fixed source

- Main base：`33aee4d`
- Stacked parent：`5e6c0385fc8d93a89561583c79981d273c44fde6`
- Full task card：
  `docs/tasks/2026-07-28_FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01_handoff.md`

## Safety boundary

- Fog LaunchAgent保持 unloaded。
- Retry circuit保持 open，不得刪除或旋轉。
- 三次 live probe停損已到；禁止第四次 live probe。
- Executor只產生 candidate，不自審、不整合、不做 live acceptance。
