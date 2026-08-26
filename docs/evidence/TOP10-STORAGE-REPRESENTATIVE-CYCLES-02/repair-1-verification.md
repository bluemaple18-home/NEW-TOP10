# TOP10 STORAGE REPRESENTATIVE CYCLES 02｜Repair generation 1 verification

## 收卡狀態

- status: `READY_FOR_RE_REVIEW`
- reviewed candidate / base commit: `4cd5458367284b8904c424ec9955275c7bfe9a34`
- repair source: `2330972ce9f2e2a8f4abe53141514bf91f4549ec`
- candidate commit: 此檔屬 candidate commit 本身，40-char SHA 以收卡回覆與 `git rev-parse HEAD` 為準，避免在 commit 內容中宣稱不可能自我引用的 SHA。
- findings addressed: `TOP10-REV-P1-001`、`TOP10-REV-P1-002`、`TOP10-REV-P1-003`

## Changed-file allowlist

- `app/storage_safety.py`
- `scripts/storage_safety.py`
- `tests/test_storage_safety.py`
- `docs/operations/top10-storage-safety.md`
- `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/repair-1-verification.md`

未修改 task card、production policy、代表性 cycle receipts、main checkout、其他專案或任何
allowlist 外檔案。

## RED → minimal GREEN

### TOP10-REV-P1-001

RED：

```text
uv run python -W error::ResourceWarning -m unittest \
  tests.test_storage_safety.StorageSafetyRegressionTest.test_validation_child_cannot_write_outside_sandbox
FAIL: result 0 != 70
```

GREEN：validation-only child 在 spawn 前執行真實 macOS `sandbox-exec` probe；只允許本次
sandbox write，source 與其他 scope 只能讀。source input 必須存在、是目錄、lexical path
沒有 symlink component，且不得落在可寫 sandbox 內。capability／probe 缺失一律在真實 child
spawn 前 fail closed。source root 另保留最多 50,000 檔的 bounded 前後 snapshot；偵測到
mutation 會留下 `PROTECTED_ROOT_MUTATED` 與 persistent restart denial。

isolated tests 證明：scope 外寫入被 OS 拒絕且原內容不變；合法 source read + sandbox write
成功；missing capability、probe failure、missing／non-directory／lexical symlink source 與
scope 外 output 全部拒絕。

### TOP10-REV-P1-002

RED：

```text
uv run python -W error::ResourceWarning -m unittest \
  tests.test_storage_safety.StorageSafetyRegressionTest.test_live_metric_gap_cannot_be_hidden_by_valid_final_sample
FAIL: result 0 != 70
```

GREEN：receipt sample 明確標示 `preflight`、`live`、`final`。任何 `live` RSS 或必要 swap
空值立即以 `RSS_METRIC_UNAVAILABLE`／`SWAP_METRIC_UNAVAILABLE` 停損；成功至少需要一筆
child 取樣前後均存活且資源量測完整的 live sample。快速 child 沒有 live evidence 時以
`MISSING_VALID_LIVE_RESOURCE_SAMPLE` fail closed；preflight／final 空值不誤判，也不能補證據。

### TOP10-REV-P1-003

RED：

```text
uv run python -W error::ResourceWarning -m unittest \
  tests.test_storage_safety.StorageSafetyRegressionTest.test_leader_exit_does_not_leave_background_descendant
FAIL: result 0 != 70
```

GREEN：可信 bootstrap leader 先等待 parent 鎖定 PGID、session ID 與 leader start token，才
exec 真實 child。正常結束與停損都驗證 group quiescent；leader-first exit 若仍有 descendant，
以 `PROCESS_GROUP_DESCENDANT_SURVIVED_LEADER` 停止已驗證 group並留下 restart denial。
identity mismatch 會 fail closed、不送 signal；isolated unrelated process 在 timeout／metric stop
測試中保持存活。

## 最終驗證

Affected storage suite：

```text
uv run pytest -q tests/test_storage_safety.py
31 passed, 16 subtests passed in 3.57s
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
1 failed, 664 passed, 4 warnings, 270 subtests passed in 122.27s
```

唯一失敗為 allowlist 外既有測試：
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
精確重跑仍失敗；verifier 的唯一 failed check 是 `evidence_exists`，目前 checkout 缺少多個
`artifacts/model_experiments/*`、`artifacts/market_context_*.json`、`data/reference/*.csv` 與
`data/clean/features.parquet` evidence。這些檔案與 ledger 模組未被本 repair 修改；依卡片禁止
擴張 P2／非 P1 scope，因此記為 full-suite environment/artifact gap，不在本 candidate 修復。

## Residual risks 與邊界

- OS confinement 實作目前以 macOS Seatbelt 為可信 provider；非 macOS 或缺
  `/usr/bin/sandbox-exec` 時刻意 fail closed，沒有降級路徑。
- protected snapshot 是有界偵測層，使用 size／mtime 且超過 50,000 檔即 fail closed；真正的
  spawn 前寫入邊界仍由 Seatbelt enforcement 提供，snapshot 不冒充 confinement。
- 未處理 Review 的 P2 residual；本輪沒有不可分割的 P2 改動。
- `launch_verified=false` 保持不變；八個 live launchd job 仍 disabled。
- 未執行八 job 代表性 workload、production reclaim／stop-loss drill、browser、provider 或
  launchd 動作；未 merge、push、deploy 或發布外部訊息。
