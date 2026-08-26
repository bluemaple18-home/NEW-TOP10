# TOP10 STORAGE REPRESENTATIVE CYCLES 02｜Repair generation 2 verification

## 收卡狀態

- status: `READY_FOR_RE_REVIEW`
- base commit / prior candidate: `572c789de5902a6f4da2ffaa68f64598bd124470`
- repair-2 source: `644bb57df208419c8209c2fa9dcbf28f072c60b7`
- candidate commit: 此檔屬 candidate commit 本身；40-char SHA 以收卡回覆與
  `git rev-parse HEAD` 為準，避免在 commit 內容中宣稱不可能自我引用的 SHA。
- finding addressed: `TOP10-REV-P1-001`

## Changed-file allowlist

- `app/storage_safety.py`
- `scripts/storage_safety.py`
- `tests/test_storage_safety.py`
- `docs/operations/top10-storage-safety.md`
- `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/repair-2-verification.md`

未修改 task card、production policy、既有 cycle evidence、main checkout、其他專案或 allowlist
外檔案。

## RED

隔離 fixture 使用 raw shell 執行 sandbox sentinel write，再嘗試 scope 外寫入並以 `|| true`
吞掉 Seatbelt error：

```text
uv run python -W error::ResourceWarning -m unittest \
  tests.test_storage_safety.StorageSafetyRegressionTest.test_validation_rejects_swallowed_outside_write_before_spawn
FAIL: result 0 != 70
```

RED 證明 reviewed candidate 的 Seatbelt 確實保護 source hash，但 child exit 0 仍使 guard 回
`OK`；不是 fixture import、環境或無關 assertion 失敗。

## Minimal GREEN

本機沒有可與單一 sandbox instance 無競態綁定的 Seatbelt denial event stream，因此採卡片允許
的 trusted harness／entrypoint contract 路徑：

1. `validate-run` 移除 raw command remainder，改為必填 `--entrypoint-contract`。
2. manual marker 的 `trusted_entrypoints.<job>` 以 sandbox-relative path 與 SHA-256 登記完整
   contract；未登記或 digest／scope／job 不符即 fail closed。
3. contract schema `top10-storage-validation-entrypoint.v1` 固定 `python-isolated`、單一 sandbox
   內 `.py` entrypoint digest 與完整 argv。guard 只組出固定的
   `python -I <entrypoint> <pinned argv>`，沒有 shell、`-c`、eval 或動態 raw-command seam。
4. contract 與 entrypoint 在 spawn 前重驗 digest；verified entrypoint bytes 會 materialize
   到 Seatbelt child 不可寫的短命 execution copy，封住 check／spawn TOCTOU。
5. 不做 command substring／黑名單掃描。raw shell swallowed-denial fixture 現在於 spawn 前以
   `UNTRUSTED_VALIDATION_ENTRYPOINT` STOP，sandbox sentinel 不存在、protected hash 不變，並
   留下 persistent restart denial。

合法 digest-pinned trusted fixture 已證明可讀 source、只寫 sandbox 並回 `OK`。另有 regression
覆蓋：未登記 entrypoint、marker contract digest 不符、load 後 contract 被替換、Python `-c`
動態 command、Seatbelt capability 缺失與 probe failure。

## Invocation 相容性變更

以下舊式人工驗證呼叫不再相容，且刻意不提供 fallback：

- `validate-run ... -- /bin/sh -c ...`
- `validate-run ... -- <任意 executable/argv>`
- `python -c`、eval 或由呼叫端動態拼接 command

若未來要重跑人工驗證，必須先將 reviewed harness 實體化為 sandbox 內 `.py`，建立 pin
entrypoint digest 與完整 argv 的 contract，再由 manual marker 登記 contract path/digest。
安全優先，不為相容性恢復 raw-command bypass。

## 最終驗證

Affected storage suite：

```text
uv run pytest -q tests/test_storage_safety.py
35 passed, 16 subtests passed in 4.32s
```

P1-002／P1-003 與 isolation 指定回歸：

```text
uv run pytest -q \
  tests/test_storage_safety.py::StorageSafetyRegressionTest::test_live_metric_gap_cannot_be_hidden_by_valid_final_sample \
  tests/test_storage_safety.py::StorageSafetyRegressionTest::test_quick_child_without_live_sample_fails_closed \
  tests/test_storage_safety.py::StorageSafetyRegressionTest::test_leader_exit_does_not_leave_background_descendant \
  tests/test_storage_safety.py::StorageSafetyRegressionTest::test_process_group_stop_is_isolated_from_unrelated_process \
  tests/test_storage_safety.py::StorageSafetyRegressionTest::test_validation_hard_runtime_stops_only_target_and_denies_restart
5 passed in 0.76s
```

語法與 hygiene：

```text
uv run python -m py_compile app/storage_safety.py scripts/storage_safety.py tests/test_storage_safety.py
PASS

rg -n '\[DBG-' app/storage_safety.py scripts/storage_safety.py tests/test_storage_safety.py
0 matches

git diff --check
PASS
```

Full suite：

```text
uv run pytest -q
1 failed, 668 passed, 4 warnings, 270 subtests passed in 62.93s
```

唯一失敗仍為前一代已記錄的 allowlist 外 environment/artifact gap：
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
其 verifier 缺少 checkout 未提供的 research ledger evidence；ledger 模組與 evidence 未被本 repair
修改。依卡片禁止擴張非 P1 scope，因此不在本 candidate 修復。

## Residual risks 與邊界

- manual marker 與其 digest-pinned contract 是明確 trust anchor；guard 證明執行的是 reviewed
  bytes／argv，不嘗試以內容掃描判斷 harness 語意。若審核者刻意信任會吞錯的 harness，必須
  以新 contract digest 重新核准，這屬 trust review 而非 raw-command bypass。
- macOS Seatbelt capability／probe 仍為必要條件；缺失時 fail closed。
- 未處理任何 P2 residual，未修改 `launch_verified=false`；八個 live launchd job 仍 disabled。
- 未執行代表性 workload、production reclaim／stop-loss drill、browser、provider 或 launchd
  動作；未 merge、push、deploy 或發布外部訊息。
