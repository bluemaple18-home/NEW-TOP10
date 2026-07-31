# FOG-CONTINUOUS-TOPIC-SUPPLY-01 Runtime Acceptance

## Identity

- reviewed repair candidate:
  `d166fa1483d2ca2288cda50ea204631cd8b0b972`
- independent re-review commit:
  `b4c12b741b959b3f49bd90d827e53cce072b1f67`
- mainline merge commit:
  `b4db5a93989ff280db9f05f897e7b93c7a580ae5`
- acceptance date: `2026-07-31`
- production ranking、model、weights、promotion：未修改。

## Natural scheduler evidence

沒有重啟或 kickstart LaunchAgent、沒有清 retry circuit、沒有執行人工 live
probe。沿用已載入的 `com.new-top10.fog-research-worker`：

- `StartInterval=900`
- merge前一輪於 `13:14:26 +0800` 啟動，仍產生
  `NO_EXECUTABLE_TOPIC`、0 selected、0 topic runs。
- merge後下一次自然觸發於 `13:46:39 +0800` 啟動，LaunchAgent run count由
  130增為131。
- 新 artifact於 `2026-07-31T05:47:41.146367+00:00` 生成：
  - `inputs.execute=true`
  - `inputs.from_queue=false`
  - `inputs.execute_topic_count=5`
  - selected topics：1
  - topic runs：1
  - outcome：`DEVELOPMENT_CANDIDATE`
  - selected topic：
    `strategy-matrix:artifacts-backtest-shadow_rankings_regime_overlay_extended_tail:risk_guard:development_screen`
  - aggregate `all_topic_runs_ok=true`
  - `development_only=true`
  - `formal_candidate_allowed=false`
  - `promotion_allowed=false`
- quota verifier於 `2026-07-31T05:47:41.871102+00:00` 生成：
  - failed count：0
  - topic runs：1
  - selected topics：1
  - research value：`HAS_FOLLOWUP_SIGNAL`
- worker log：
  - `TOP10_FOG_MAP_HANDOFF_OK`
  - batch finished
  - `no_more_work=0`
- retry state：不存在；circuit沒有開啟或被清除。

## Static and regression evidence

- affected targeted suites：`105 passed`
- mainline full suite：
  `617 passed, 4 warnings, 246 subtests passed`
- shell runtime wiring、shell syntax、`py_compile`、`git diff --check`：PASS
- unresolved P0/P1：none

## Decision

`ACCEPTED_MAINLINE_RUNTIME`

原本的 queue ownership deadlock已由自然排程實證解除：相同
`from_queue=false` worker default不再空轉，能選出 development topic並完成研究。

非阻塞 P2 backlog另記錄於
`docs/tasks/2026-07-31_FOG-TOPIC-SUPPLY-BUDGET-STATUS-01.md`。
