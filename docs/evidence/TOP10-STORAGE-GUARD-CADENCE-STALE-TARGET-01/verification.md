# TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01 Verification

## Status

`READY_FOR_REVIEW / CANDIDATE`

`candidate_commit: reported_in_final_receipt`

## Identity、preflight 與 context

- Formal thread：`019fc7a6-8a96-7e70-b7f7-66771c624933`
- Project ID：`local-49c40f44270697f9bce80f898c3c5a4d`
- Activation HEAD：`7b43531dbae8d7231a3f333023cbcdab1d61ecd0`
- Required parent：`8b01eb7f9479c8a4d0e104f4a56edd574ee5d150`
- 獨立 detached worktree、初始 clean、card 實體存在、index lock absent。
- CodeGraph 未在此 worktree 初始化；依卡保存
  `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`，未建立 index，fallback 僅讀指定 cadence loop 與
  `tests/test_storage_safety.py`。

## 可證偽假說

1. 若根因是機會性 sample 跨過 absolute target 後，既有程式每輪只做一次
   `next_sample_target += schedule_interval`，則 `9.6s` sampler 在 `9.5s` target 上會讓 target lag
   每輪增長，且 waiter 永遠不會收到正 timeout；有 iteration cap 的 fake-clock test 應穩定重現。
2. 若以 O(1) arithmetic 把過期 target reconcile 到下一個 future absolute target，並用剛完成 sample 的
   實測 duration 判定該 target 是否仍能在 completion hard deadline 前安全完成，則此案例會在固定步數內
   以 `LIVE_SAMPLE_SCHEDULE_OVERRUN` fail closed，而不會冒稱 cadence overrun。
3. 若既有 completion-gap 判定本身正確，則真正 `60.005s > 60s` 的案例仍會優先得到
   `LIVE_SAMPLE_CADENCE_EXCEEDED`，不應被新的 schedule reason 覆蓋。

## RED → GREEN

RED command：

```text
PYTHONDONTWRITEBYTECODE=1 <uv-venv-python> -B -m pytest -q -p no:cacheprovider tests/test_storage_safety.py::StorageSafetyRegressionTest::test_stale_sample_target_fails_closed_without_unbounded_no_wait_sampling
```

Activation source 精確結果：`1 failed`，且是目標症狀而非 import／fixture failure：

- `10s` completion hard maximum、derived target interval `9.5s`、每次 sampler duration `9.6s`。
- live completions：`[9.6, 19.2, 28.799999999999997, 38.4, 48.0]`。
- completion gaps：`[9.6, 9.599999999999998, 9.600000000000001, 9.600000000000001]`，全數
  `<=10s`。
- target lag：`[0.1, 0.2, 0.3, 0.4, 0.5]`（浮點近似），逐輪增長。
- waiter timeouts：`[]`；child 在五筆 completion 後仍存活，harness 第六次 sample 入口的 iteration cap
  才使 guard 以 `70 / GUARD_INTERNAL_ERROR_StaleTargetIterationCap` 收斂。
- 這證明 activation source 的 stale target 會形成無界 no-wait sampling；GREEN 不得依賴 iteration cap。

## Source decision

- `sample_interval_seconds`、`19/20` target 與 policy/schema 完全不變；沒有 epsilon、tolerance 或 ceiling
  調整。
- `sample_live_child()` 同時量測 completion gap 與本次 sampler duration。真正 gap 超過 hard maximum時，
  既有 `LIVE_SAMPLE_CADENCE_EXCEEDED` 判定仍先執行。
- immediate、first-write 與 scheduled sample 完成後，若 absolute target 已過期，以
  `floor((now-target)/interval)+1` 一次算出需跳過的 intervals；沒有 while loop或逐輪 catch-up。
- Reconciled target 必須嚴格在未來，且以本次 sampler duration 推估的下一 completion 不得跨過
  `last_safe_observation_at + sample_interval_seconds`。若無法安全排程，使用穩定 reason
  `LIVE_SAMPLE_SCHEDULE_OVERRUN` fail closed。
- 若 hard runtime deadline早於 sample hard deadline，保留既有 runtime precedence；下一輪由
  `HARD_RUNTIME_EXCEEDED` 收斂，不讓 schedule reason搶先。

GREEN 使用同一 RED command：`1 passed`。

- 首筆 live completion：`[9.6]`；沒有第二筆 no-wait sample，iteration cap 未觸發。
- guard result／receipt：`70 / STOPPED / LIVE_SAMPLE_SCHEDULE_OVERRUN`；此時 actual completion gap並未
  超過 `10s`，因此沒有冒稱 `LIVE_SAMPLE_CADENCE_EXCEEDED`。
- waiter timeouts：`[]`；這是首筆 sample 已證明下一 absolute target 無法在 hard deadline內安全完成，
  因而直接 fail closed，不是 busy loop。
- persistent denial存在、`automatic_clear_allowed=false`、第二次執行 `75`，target PID 已 quiescent。

First-write regression：

- immediate completion `9.49s`，first-write sample duration `0.02s`，completion `9.51s`，剛跨過
  `9.5s` target。
- O(1) reconcile後 target為 `19.0s`；只產生兩筆 live completion，沒有第三筆 back-to-back sample。
- 下一個實質 waiter timeout為 `9.49s > 0`；結果 `0 / OK`、reasons `[]`，無 denial。

## Regression checks

- Focused cadence/runtime/PGID selection：`12 passed, 37 deselected in 1.02s`。
  - 包含 stale target、first-write crossing、absolute schedule、healthy headroom、true overrun、late／on-time
    normal return、runtime precedence、sampler overrun與 child during sample。
- Healthy `60s` regression保持 `0 / OK`：sampler `0.2s`、lateness `0.005s`，scheduled completion gaps
  `[57.005, 57.0]`，waits `[56.8, 56.795, 56.795]`，全部為正且無 denial。
- True overrun保持：completion gap `60.005s` →
  `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`；verified PGID quiescent、persistent denial、第二次
  `75`。
- Affected suite：`tests/test_storage_safety.py tests/test_fog_storage_validation.py` →
  `57 passed, 16 subtests passed in 5.80s`。
- Full suite：`690 passed, 1 failed, 270 subtests passed in 60.71s`。
- 唯一 full-suite failure是既有且未由本卡修改的
  `ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger`：status `FAILED`，前代 verification
  已記錄同一 `evidence_exists` gap。缺件 IDs為 `research:candidate_ranking`、`research:trail10`、
  `research:overlap_first`、`research:chip_flow`、`research:fundamental_revenue`、
  `research:industry_map`、`research:concept_membership`、`research:market_regime_history`、
  `research:market_context`、`runtime:industry_theme_context`。本卡沒有放寬或宣稱 full green。

## Scope、protected state 與 static checks

- Changed-file allowlist：
  - `app/storage_safety.py`
  - `tests/test_storage_safety.py`
  - `docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01.md`
  - `docs/evidence/TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01/verification.md`
- 八份 policy 的 `launch_verified` 全為 `false`；未呼叫 launchd／browser／provider／connector控制面。
- 主 checkout protected hashes維持：
  - `scripts/build_weekend_universe_inventory.py`：
    `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
  - `tests/test_weekend_universe_inventory_snapshot.py`：
    `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
    `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`
- `git diff --check`通過；source／test 的 `[DBG-` scan零命中。
- 未執行 FOG、代表性 workload、cycle、retry、reclaim／stop-loss drill；未讀寫、清除、複製或復用
  前代 sandbox／receipt／log／marker／contract／denial；未 merge、push、deploy或自審。

## Remaining risk／next step

- Full suite仍有上述既有 research ledger evidence gap，因此本卡不是全域 production `GO`。
- 狀態只到 `READY_FOR_REVIEW / CANDIDATE`；主線須建立全新獨立 Reviewer。Implementation不進 FOG，
  live排程持續停用。
