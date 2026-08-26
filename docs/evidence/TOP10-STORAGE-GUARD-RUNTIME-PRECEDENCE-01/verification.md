# TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01 Verification

## Status

`READY_FOR_REVIEW / CANDIDATE`

`candidate_commit: reported_in_final_receipt`

## Identity、preflight 與 context

- Formal thread：`019fc7c2-dd03-73e1-8059-4fbae7be1298`
- Project ID：`local-49c40f44270697f9bce80f898c3c5a4d`
- Activation HEAD：`6902618ddf4fabfd9002fbe758de077f9f2be44a`
- Required parent：`d4597c3950e4635f32c03519ff8715c580176160`
- 獨立 detached worktree、初始 clean、card 實體存在、index lock absent。
- CodeGraph 未在此 worktree 初始化；保存
  `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`，未建立 index，fallback 限於指定
  cadence/runtime loop 與 `tests/test_storage_safety.py`。

## Deterministic RED

Command：

```text
PYTHONDONTWRITEBYTECODE=1 <uv-venv-python> -B -m pytest -q -p no:cacheprovider tests/test_storage_safety.py::StorageSafetyRegressionTest::test_runtime_between_target_and_predicted_completion_preempts_sample
```

未修改 source 的 activation parent 精確得到 `1 failed`，且 failure 是目標症狀：

- hard maximum `10s`、absolute schedule interval `9.5s`、runtime deadline `19.2s`、sampler
  durations `[9.6, 9.6]`。
- 第一筆 completion `9.6s` 後，O(1) reconcile target 為 `19.0s`、sample hard deadline
  `19.6s`、依最近 duration 預估 completion `28.6s`。
- Observed completions `[9.6, 28.6]`、waits `[9.4]`、clock `28.6s`、
  `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`；persistent denial 存在，第二次 `75`。
- 第二筆 sampler 自然完成；測試沒有人工終止 sample 或 child 來製造結果。

## Source decision 與 GREEN

- `next_sample_action()` 保留 O(1) arithmetic target reconcile，並顯式回傳三種薄決策：
  - `runtime_deadline <= next_sample_target` → `WAIT_RUNTIME`。
  - `next_sample_target < runtime_deadline < predicted_completion` → `WAIT_RUNTIME`。
  - `predicted_completion <= runtime_deadline` → 再依既有 sample hard deadline 決定
    `SAMPLE` 或 `SCHEDULE_OVERRUN`。
- `WAIT_RUNTIME` 直接把下一 wake deadline 指向 runtime；傳給 waiter 的 timeout 嚴格大於 `0`，不啟動
  已知會跨 runtime 的 sample。
- `completed_sample_deadline_reason()` 依 actual cadence deadline 與 runtime 的絕對先後排序：runtime
  不晚於 cadence deadline 時保留 `HARD_RUNTIME_EXCEEDED`；actual cadence violation 先發生時保留
  `LIVE_SAMPLE_CADENCE_EXCEEDED`。
- hard maximum、`19/20` target、absolute monotonic schedule、policy/schema 均未變；沒有 epsilon、
  tolerance、ceiling 或 magic seconds。

同一 RED command 的 GREEN 結果為 `1 passed`：

- target `19.0s`、runtime `19.2s`、predicted completion `28.6s`、sample hard deadline `19.6s`。
- Actual completions `[9.6]`；第二筆 sample 未啟動；waits `[9.6]` 且嚴格為正；clock 精確抵達
  `19.2s`。
- `70 / STOPPED / HARD_RUNTIME_EXCEEDED`；verified PGID quiescent、persistent denial、
  `automatic_clear_allowed=false`、第二次 `75`。

## Deterministic deadline matrices

### Runtime 相對 target 與 predicted completion

hard `10s`、target `9.5s`、observed duration `1.0s`、predicted completion `10.5s`：

| Case | Runtime | Actual completions | Waits | Result |
|---|---:|---|---|---|
| just before target | `9.4` | `[1.0]` | `[8.4]` | `70 / HARD_RUNTIME_EXCEEDED` |
| equal target | `9.5` | `[1.0]` | `[8.5]` | `70 / HARD_RUNTIME_EXCEEDED` |
| just after target / before predicted | `9.6` | `[1.0]` | `[8.6]` | `70 / HARD_RUNTIME_EXCEEDED` |
| equal predicted completion | `10.5` | `[1.0, 10.5]` | `[8.5]` | `70 / HARD_RUNTIME_EXCEEDED` |
| just after predicted completion | `10.6` | `[1.0, 10.5]` | `[8.5, 0.1]` | `70 / HARD_RUNTIME_EXCEEDED` |

所有 waits 嚴格為正；前三個排列不啟動第二筆 sample，後兩個排列允許第二筆 sample。

### Runtime 相對 sample hard deadline

第一筆 completion `9.6s`、next target `19.0s`、predicted completion `28.6s`、sample hard deadline
`19.6s`：

| Case | Runtime | Actual completions | Waits | Result |
|---|---:|---|---|---|
| just before hard deadline | `19.5` | `[9.6]` | `[9.9]` | `70 / HARD_RUNTIME_EXCEEDED` |
| equal hard deadline | `19.6` | `[9.6]` | `[10.0]` | `70 / HARD_RUNTIME_EXCEEDED` |
| just after hard deadline | `19.7` | `[9.6]` | `[10.1]` | `70 / LIVE_SAMPLE_CADENCE_EXCEEDED` |

最後一列於 runtime 到達時 actual completion gap 已為 `10.1s > 10s`，因此 cadence violation 已先發生；
前兩列沒有把未發生的 actual overrun 誤報為 cadence。

### Sampler completion 的 actual ordering

- sampler actual completion `10.1s`、cadence deadline `10.0s`：runtime `9.9s`／`10.0s` 分別得到
  `HARD_RUNTIME_EXCEEDED`；runtime `10.05s` 得到 `LIVE_SAMPLE_CADENCE_EXCEEDED`。三者均只有一筆
  completion `[10.1]`，沒有 waiter。
- 另一個 actual overrun：immediate completion `0.2s`、scheduled completion `10.3s`、wait `[9.3]`、
  runtime `11.0s`；actual gap `10.1s` 在 runtime 前完成，結果保持
  `LIVE_SAMPLE_CADENCE_EXCEEDED`。

每個 fail-closed matrix case 都驗證 persistent denial、`automatic_clear_allowed=false`、第二次 `75`
與 target PGID quiescent。

## Regression checks

- Focused cadence/runtime/PGID selection：`20 passed, 34 deselected, 11 subtests passed`。
- 前代 stale-target case：首筆 `9.6s` completion 後仍以
  `70 / STOPPED / LIVE_SAMPLE_SCHEDULE_OVERRUN` bounded fail closed，不依賴 iteration cap。
- First-write 跨 target：completions `[9.49, 9.51]`、reconciled target `19.0s`、最後實質 wait
  `9.49s > 0`、`0 / OK`。
- Healthy `60s`、`0.2s` overhead、`0.005s` lateness、true `60.005s` completion overrun、absolute
  schedule、late/on-time normal return、sampler overrun、child during sample、process-group 與 denial
  regressions均包含於 focused／affected suite。
- Affected suite：`tests/test_storage_safety.py tests/test_fog_storage_validation.py` →
  `62 passed, 27 subtests passed in 6.37s`。
- Full suite：`695 passed, 1 failed, 281 subtests passed in 61.09s`。
- 唯一 full-suite failure 是既有 `ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger`；
  verifier 僅 `evidence_exists` check 失敗，缺件 IDs：`research:candidate_ranking`、
  `research:trail10`、`research:overlap_first`、`research:chip_flow`、
  `research:fundamental_revenue`、`research:industry_map`、`research:concept_membership`、
  `research:market_regime_history`、`research:market_context`、
  `runtime:industry_theme_context`。本卡未修改或放寬該契約，未宣稱 full green。

## Scope、policy 與 protected state

- Changed-file allowlist：
  - `app/storage_safety.py`
  - `tests/test_storage_safety.py`
  - `docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01.md`
  - `docs/evidence/TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01/verification.md`
- 八份 policy 的 `launch_verified` 全為 `false`。
- 主 checkout protected hashes維持：
  - `scripts/build_weekend_universe_inventory.py`：
    `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
  - `tests/test_weekend_universe_inventory_snapshot.py`：
    `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
    `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`
- `git diff --check` 通過；source/test 的 `[DBG-`、`epsilon`、`tolerance` scan 零命中。
- 所有 pytest 使用 `PYTHONDONTWRITEBYTECODE=1`、`-B`、`-p no:cacheprovider`。
- 未執行 FOG／workload／cycle／retry／reclaim／stop-loss；未讀寫、清除、複製或復用任何前代
  sandbox／receipt／log／marker／contract／denial；未操作 browser／provider／launchd控制面，未
  merge／push／deploy／live／自審。

## Remaining risk／next step

- Full suite 保留上述既有 research-ledger evidence gap，因此本卡不是 production `GO`。
- 狀態只到 `READY_FOR_REVIEW / CANDIDATE`；主線須建立全新獨立 Reviewer，implementation 不進 FOG。
