# TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01 Verification

## Status

`READY_FOR_REVIEW / CANDIDATE`

`candidate_commit: reported_in_final_receipt`

## Identity、preflight 與 context

- Formal thread：`019fc7e4-51b7-71f3-b3b1-95396dcc05a5`
- Project ID：`local-49c40f44270697f9bce80f898c3c5a4d`
- Activation HEAD：`cb9a6aedc348c494d984fa168d9c3fb7e089da80`
- Required parent：`65b00fc7870aff5f8337c2cf235465c9166568ad`
- 獨立 detached worktree、初始 clean、card 實體存在、index lock absent。
- CodeGraph 未在此 worktree 初始化；保存
  `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`，未建立 index，fallback 限於指定
  first-write／scheduled／runtime loop 與 `tests/test_storage_safety.py`。

## Root cause 與 ownership boundary

- Waiter 內 first-write event set 後，同一 loop iteration 直接進 scheduled branch，既有程式沒有在
  scheduled sampler 前 claim event；scheduled completion 後，下一輪把 stale event 當成另一筆
  first-write observation，形成 back-to-back double sample。
- 修復以 lock-protected `claim_pending_first_write()` 將 ownership boundary 固定在 observation start：
  start 前 pending event 由當次 observation 原子 clear／consume，start 後才發生的 event 保持 pending。
- Scheduled observation 若未承接 first-write，pending event 不得立即走 direct sample；它先經下一個
  absolute target 的 strictly-positive waiter，再由下一 scheduled observation consume。
- `WAIT_RUNTIME` 判定仍優先；first-write 不會繞過 runtime preemption。Hard maximum、`19/20` target、
  O(1) reconcile、policy/schema均未改，沒有 epsilon、tolerance、ceiling提高或 magic seconds。

## Reviewer exact deterministic RED

Command：

```text
PYTHONDONTWRITEBYTECODE=1 <uv-venv-python> -B -m pytest -q -p no:cacheprovider tests/test_storage_safety.py::StorageSafetyRegressionTest::test_scheduled_observation_consumes_first_write_pending_from_waiter
```

未修改 source 的 activation parent 精確得到 `1 failed`，且 failure 是目標症狀：

- hard maximum `10s`、absolute target `9.5s`；child 於首次 waiter 輸出 `65536` bytes。
- sampler durations `[0.1, 0.1, 10.1]`；completions `[0.1, 9.6, 19.7]`、waits `[9.4]`。
- `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`；persistent denial 建立、target PGID 已由 guard
  quiesce。第三筆 `10.1s` sampler 自然返回，測試未人工終止第三筆 sample。

## Minimal GREEN

同一 command 在修復後為 `1 passed`：

- Scheduled observation start 前原子 claim waiter 內 pending event；sampler只呼叫兩次。
- Completions `[0.1, 9.6]`、waits `[9.4, 9.4]`，所有 wait 嚴格大於 `0`。
- 下一個 absolute target wait 約 `9.4s`；child 正常 `0 / OK`、無 persistent denial、target PGID
  quiescent。

## First-write 四窗口 matrix

Focused matrix command 得到 `2 passed, 4 subtests passed`；事件時間、completion與wait均由 fake
monotonic clock 鎖定：

| Window | Event time | Completions | Waits | Ownership/result |
|---|---:|---|---|---|
| waiter 內 | `0.1` | `[0.1, 9.6]` | `[9.4, 9.4]` | 當次 scheduled consume；`0 / OK` |
| scheduled sampler 開始前 | `9.5` | `[0.1, 9.6]` | `[9.4, 9.4]` | 當次 scheduled consume；`0 / OK` |
| scheduled sampler 期間 | `9.5` | `[0.1, 9.6, 19.1]` | `[9.4, 9.4, 9.4]` | 保持 pending；正等待後由下一 scheduled consume |
| scheduled sampler 完成後 | `9.6` | `[0.1, 9.6, 19.1]` | `[9.4, 9.4, 9.4]` | 不事後冒領；正等待後由下一 scheduled consume |

四列皆 sample count 符合唯一 owner、所有 waits 嚴格為正、`0 / OK`、無 denial、PGID quiescent。

## Runtime、cadence 與 process-group regressions

- Pending first-write 的 `WAIT_RUNTIME` exact case：hard `10s`、target `19.0s`、runtime `19.2s`；只完成
  `[9.6]`，waits `[9.6]`，first-write 未啟動 sample，於 `19.2s` 得到
  `70 / STOPPED / HARD_RUNTIME_EXCEEDED`、persistent denial、
  `automatic_clear_allowed=false`、第二次 `75`、target PGID quiescent。
- Focused first-write／runtime equality／cadence／stale-target／sampler／late-on-time return／PGID selection：
  `21 passed, 36 deselected, 15 subtests passed in 2.24s`。
- 前代 runtime `19.2s` exact、target／predicted completion 五排列、sample hard deadline 三排列、actual
  cadence ordering、stale-target schedule-overrun、first-write跨target正wait、healthy `60s`、true
  `60.005s` cadence、absolute schedule、sampler overrun、child during sample、process-group 與 denial
  regressions均包含於 focused／affected suite。
- Affected suite：`tests/test_storage_safety.py tests/test_fog_storage_validation.py` →
  `65 passed, 31 subtests passed in 7.47s`。

## Full suite known gap

- Full suite：`698 passed, 1 failed, 285 subtests passed in 62.68s`。
- 唯一 failure：`ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger`；實際 verifier report
  只有 `evidence_exists` check 失敗。
- 缺件 IDs：`research:candidate_ranking`、`research:trail10`、`research:overlap_first`、
  `research:chip_flow`、`research:fundamental_revenue`、`research:industry_map`、
  `research:concept_membership`、`research:market_regime_history`、`research:market_context`、
  `runtime:industry_theme_context`。
- 此 gap 與前代 evidence 一致；本卡未修改或放寬 research-ledger 契約，因此不宣稱 full green。

## Scope、policy 與 protected state

- Changed-file allowlist：
  - `app/storage_safety.py`
  - `tests/test_storage_safety.py`
  - `docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01.md`
  - `docs/evidence/TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01/verification.md`
- 八份 policy 的 `launch_verified` 全為 `false`。
- 主 checkout protected hashes維持：
  - `scripts/build_weekend_universe_inventory.py`：
    `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
  - `tests/test_weekend_universe_inventory_snapshot.py`：
    `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
    `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`
- `git diff --check` 通過；source/test 的 `[DBG-`、`epsilon`、`tolerance` scan零命中；未產生
  cache／bytecode。
- 未執行 FOG／workload／cycle／retry／reclaim／stop-loss；未讀寫、清除、複製或復用任何前代
  sandbox／receipt／log／marker／contract／denial；未操作 browser／provider／launchd控制面，未
  merge／push／deploy／live／自審。

## Remaining risk／next step

- Full suite 保留上述既有 research-ledger evidence gap，因此本卡不是 production `GO`。
- 狀態只到 `READY_FOR_REVIEW / CANDIDATE`；主線須建立全新獨立 Reviewer，implementation 不進 FOG。
