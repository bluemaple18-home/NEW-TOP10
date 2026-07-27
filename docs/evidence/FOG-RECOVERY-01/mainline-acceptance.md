---
id: FOG-RECOVERY-01-MAINLINE-ACCEPTANCE
status: BLOCKED_REPAIR_LIMIT
chain_id: FOG-RECOVERY-01
accepted_by: mainline
---

# Mainline Acceptance

## Root question

如何讓 research progress／fog map 與 weekend inventory 在同一份完成語意下產生一致 processed count，讓 controlled-grid linkage 與 circuit recovery 可安全通過？

## Current state

- Candidate `58ff3467426b4ec01386a6ad14cd38c8950b601b`：加入 bounded snapshot rebuild 與 explicit circuit recovery gate。
- Review `2e6ef666a691aeaa99eabcb2c6978b85722a60b1`：initial NO-GO。
- Repair-1 `9ce4d80a22a01c79a25368d30cfb77859d0f83ec`：關閉 whitespace finding。
- Re-review `b381e769a0beb644cdc897ab88555f03c4697c89`：GO。
- Repair-2 `7b25e901084121234a41e87a8ec6a00f4905f34e`：先刷新 progress／fog map，再建 inventory。
- Final re-review `f7f26ad1cebcb74d84ec3a6e119bddd65e101020`：GO。

## Mainline verification

- Full suite：`474 passed, 4 warnings, 246 subtests passed`。
- Targeted order＋snapshot tests：`5 passed`。
- Circuit shell regressions：OK。
- Python compile、shell syntax、fixed-range `git diff --check`：OK。

## Live acceptance blocker

`run_controlled_grid_drain_host_runner.py --date 2026-07-27` 的實際步驟：

1. `build_research_progress_before_inventory`：OK
2. `build_fog_map_before_inventory`：OK
3. `verify_fog_map_before_inventory`：OK
4. `build_inventory_and_bounded_frontier_queue`：FAILED

兩次 bounded inventory build 都得到：

```text
current_processed_count=33360
current_remaining_count=2833392
map_expanded_processed=33358
map_expanded_pending=2833394
```

這證明持久差異來自兩條計算路徑的 processed semantics，而非 stale refresh order。現有 fail-closed 行為正確阻止假 OK。

## Blocker

- `BLOCKED_REPAIR_LIMIT`
- Repair generation 已達 2；不得建立 Repair-3。
- retry circuit 保持 open；沒有刪除或輪替 live state。
- production ranking、model、weights、promotion 均未變更。

## Candidate fork

需要新授權後另開 root question：比較 `research_map_contract.apply_run_history()/completed_v2_expansion_count()` 與 `weekend_training_common.current_status_from_*()`，找出兩個多算／少算的 combo IDs，統一定義並建立雙向 recompute gate。不得以容忍差值或改 verifier 解決。
