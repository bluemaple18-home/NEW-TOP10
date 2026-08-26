# TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01 Verification

## Status

`READY_FOR_REVIEW / CANDIDATE`

`candidate_commit: reported_in_final_receipt`

這是 shared storage guard 的 strict source candidate。未執行 FOG、代表性 workload、cycle、retry、
fresh revalidation、launchd 操作、merge、push、deploy 或 live 排程；前代 sandbox、receipt、log、
marker、contract 與 restart denial 均未讀寫、複製或復用。

## Identity、preflight 與 context

- Formal thread：`019fc789-3422-7711-8b8c-bde172db1ba1`
- Project ID：`local-49c40f44270697f9bce80f898c3c5a4d`
- Activation HEAD：`dad236825731130473e3b1ef543ff5b6605c8700`
- Candidate parent：`dad236825731130473e3b1ef543ff5b6605c8700`
- Activation HEAD 第一親代：`73a1d17dee7a2f42b54d944db57f2d4656377447`
- 獨立 Codex worktree、detached HEAD、初始 clean；task card 的 HEAD tree 與 index blob 均為
  `8c57b85b90449ba177a28fe61b1e9f6be92fe19a`，index lock clean。
- CodeGraph 在此獨立 worktree 回覆 `not initialized`。依卡片契約保存
  `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`，未初始化或寫入 index；fallback 僅限域讀取
  `run_guarded_job()` 與 `tests/test_storage_safety.py` cadence/runtime regression seam。

## Source decision

- `sample_interval_seconds` 保持 completion-to-completion hard maximum，policy、schema、ceiling與
  receipt 解釋均未更動。
- target schedule 固定為 hard maximum 的 `19/20`（95%），正 headroom 為 `1/20`（5%）。既有
  policy 僅接受 `1..300s`，因此 headroom 明確 bounded 為 `0.05..15s`，不是取自真實觀測的
  `0.205s`。
- target 使用 `started_at + n * schedule_interval` 的 monotonic absolute schedule；每輪只增加固定
  interval，不把 sampler duration 累積成 drift。
- cadence hard deadline 另由 `last_safe_observation_at + sample_interval_seconds` 計算；normal return
  與 TimeoutExpired 都以該 deadline 判定。target 已到時直接進 sample path，不向 waiter 傳零或負
  timeout，避免 zero-timeout busy loop。
- hard runtime 早於 sample hard deadline時仍優先；stop後沿用 verified process-group termination、
  persistent denial與 exit `70`。

## RED → GREEN

RED command：

```text
PYTHONDONTWRITEBYTECODE=1 <venv-python> -B -m pytest -q -p no:cacheprovider tests/test_storage_safety.py::StorageSafetyRegressionTest::test_live_sampling_headroom_keeps_normal_overhead_and_lateness_within_hard_maximum
```

舊 source 精確結果：`1 failed`；interval `60s`、sampler overhead `0.2s`、scheduler lateness
`0.005s` 時，actual 為 `70 / LIVE_SAMPLE_CADENCE_EXCEEDED`，completion gaps `[60.005]`、wait
timeouts `[59.8]`。只到第一個 scheduled sample就誤停，符合 `FOG-CADENCE-P1-001`，不是 import、
fixture或環境 assertion failure。

最小 source修復後同一 command：`1 passed`。deterministic public observables為：

- result／receipt：`0 / OK / reasons=[]`，無 restart denial。
- 三個 live completions涵蓋 immediate加兩個 scheduled samples。
- scheduled completion gaps：`[57.005, 57.0]`，皆 `<=60`。
- waiter timeouts：`[56.8, 56.795, 56.795]`，全部為正。

## 真正 hard maximum overrun

`test_live_sampling_hard_maximum_stops_true_completion_overrun` 使用同一 `60s` ceiling與 `0.2s`
sampler overhead，讓 scheduler lateness使 completion gap真正成為 `60.005s`：

- waiter timeout：`56.8s`（正值）；沒有啟動下一輪 sample。
- first result：`70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`。
- restart denial：存在、reason相同、`automatic_clear_allowed=false`；第二次執行回 `75`。
- verified child PID 已 quiescent（`os.kill(pid, 0)` 回 `ProcessLookupError`）。

既有 `test_late_normal_return_after_sample_deadline_fails_closed` 另證明 child exit `0` 不覆蓋 cadence
stop：仍為 `70 / STOPPED`、保留 `child_exit_code=0`、persistent denial與 PGID quiescence。

## Regression checks

- Cadence/runtime/PGID focused selection：`8 passed, 39 deselected in 0.56s`。
  - 包含 monotonic absolute schedule、正常 headroom、真正 overrun、late normal return、hard runtime
    precedence、on-time normal return、sampler overrun與 child during sample。
- Affected suite：
  `tests/test_storage_safety.py tests/test_fog_storage_validation.py` →
  `55 passed, 16 subtests passed in 5.56s`。
- Full suite：`688 passed, 1 failed, 270 subtests passed in 61.10s`。
- 唯一 full-suite failure是既有且不在本次 diff的
  `ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger`：status `FAILED`，唯一 failed
  check為 `evidence_exists`。缺件 ledger IDs精確為
  `research:candidate_ranking`、`research:trail10`、`research:overlap_first`、`research:chip_flow`、
  `research:fundamental_revenue`、`research:industry_map`、`research:concept_membership`、
  `research:market_regime_history`、`research:market_context`、`runtime:industry_theme_context`。
  相依的 ledger builder、verifier與 test相對 activation HEAD均未修改；此 gap亦與前代 verification
  記錄一致，未放寬或宣稱全綠。

## Scope、protected state 與 static checks

Changed-file allowlist精確為：

- `app/storage_safety.py`
- `tests/test_storage_safety.py`
- `docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01.md`
- `docs/evidence/TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01/verification.md`

主 checkout protected hashes維持：

- `scripts/build_weekend_universe_inventory.py`：
  `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
- `tests/test_weekend_universe_inventory_snapshot.py`：
  `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
- `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
  `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

`git diff --check`通過；`[DBG-` scan零命中。最終 candidate commit的第一親代必須保持 activation
HEAD，且 commit後 worktree clean。

## Remaining risk／next step

- Full suite仍有上述既有 ledger evidence gap，因此本卡不是全域 production `GO`。
- 狀態只到 `READY_FOR_REVIEW / CANDIDATE`；主線須建立全新獨立 Reviewer。本 implementation不自審，
  不進入 FOG重驗，live排程持續停用。
