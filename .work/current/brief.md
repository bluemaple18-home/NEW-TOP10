---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-BRIEF
status: GO_LOCAL_DETERMINISTIC
type: mainline
---

# Current Brief

## Main task

`FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01`

Closed-regime source lineage與 exact-regime topic eligibility已修復、經
Repair-1與同一獨立 Reviewer複審，並在目前 task branch完成本機整合。

## Fixed source

- Main base：`33aee4d`
- Stacked parent：`5e6c0385fc8d93a89561583c79981d273c44fde6`
- Full task card：
  `docs/tasks/2026-07-28_FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01_handoff.md`
- Local integration：
  `374792652b8bee8a869052228da78f7a0d4558b4`
- Review GO：
  `0b1373bdea3d02b6a92c07a121f664949e4f48f2`

## Safety boundary

- Fog LaunchAgent保持 unloaded。
- Retry circuit保持 open，不得刪除或旋轉。
- 三次 live probe停損已到；禁止第四次 live probe。
- Main checkout full suite：`587 passed`。
- 尚未 push、deploy或執行 I5 live acceptance。
