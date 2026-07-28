---
id: FOG-PROCESSED-SEMANTICS-AUTHORITY-01-VERIFICATION
status: VERIFIED_CANDIDATE
---

# Verification

## Root cause

`research_map_contract.completed_v2_expansion_count()` 只接受合法、non-default、
completed 且具 artifact 的 v2 expansion record；weekend inventory 原本卻只要
exact combo record存在就算 processed，形成第二套較寬鬆語意。

Live symmetric difference中的兩筆都是 default-coordinate v2 rows：

- `artifacts-backtest-liquidity_quality_candidate_universe_shadow_rankings_2026-06--514eedec:long_horizon|horizon_3|stop_none|take_profit_0.15|group_exposure_none|regime_gate_ALL|risk_guard_NONE|entry_filter_TOPIC_DEFAULT`
- `artifacts-backtest-liquidity_quality_candidate_universe_shadow_rankings_2026-06--514eedec:long_horizon|horizon_3|stop_none|take_profit_0.25|group_exposure_none|regime_gate_ALL|risk_guard_NONE|entry_filter_TOPIC_DEFAULT`

這兩筆不可由 expansion path重複計數；default coordinate只走既有
base-scenario folding。

## Red → green

- RED：新增 regression 初次執行 exit `1`，default-coordinate 得到
  `LOW_INFORMATION`，預期 `PENDING`。
- GREEN：inventory 重用 `is_completed_v2_expansion_record()` 後，測試檔
  `4 passed`。
- Mutation coverage：合法 non-default completed仍 processed；
  default-coordinate、incomplete、missing artifact皆 pending。

## Live frozen recompute

修前：

```text
current_processed_count=33360
map_expanded_processed=33358
current_remaining_count=2833392
map_expanded_pending=2833394
```

修後唯讀重算：

```json
{"current_processed_count": 33358, "current_remaining_count": 2833394, "map_expanded_pending": 2833394, "map_expanded_processed": 33358}
```

## Gates

- Targeted Python：`17 passed`
- Retry circuit shell regression：PASS
- Full suite：`569 passed, 4 warnings, 246 subtests passed`
- Production state：circuit仍 open；未旋轉 retry state、未寫 queue、未修改
  model／ranking／weights／baseline／promotion。
