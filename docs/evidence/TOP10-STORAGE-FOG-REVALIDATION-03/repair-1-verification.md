# REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1｜Verification

## 執行邊界

- 只執行 unit／integration／static checks；未執行 fog、cycle、代表性 workload、reclaim drill
  或 stop-loss drill。
- 未清除既有 validation sandbox 或 restart denial；未觸碰 production data、artifacts、models
  或 launchd live 狀態。
- 三個 root cause 依序採 `RED → minimal fix → GREEN`，上一項 GREEN 後才建立下一項 RED。

## Root cause 1｜Hostile environment 與 runner swap

可證偽假說：若 digest bypass 來自 caller environment 透傳，以及 Bash 在 digest 後重新解析
runner path，則 hostile `BASH_ENV` 在 Bash startup 階段替換 runner 時會留下 injected output；改成
固定 child environment 並執行已驗證 bytes 的無路徑唯讀 FD 後，injection 不會執行，原 pinned
runner 仍會完成。

RED command：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  -p no:cacheprovider \
  tests/test_fog_storage_validation.py::FogStorageValidationEntrypointTest::test_hostile_shell_environment_cannot_swap_verified_runner
```

RED result：

```text
FAILED ... test_hostile_shell_environment_cannot_swap_verified_runner
AssertionError: True is not false
1 failed in 0.05s
```

失敗點為 `shell-startup-injected.txt` 實際存在；不是 import、fixture 或環境缺件錯誤。

Minimal fix：

- child environment 改為純固定值／sandbox runtime paths，不再複製 caller environment；固定
  `PATH=/usr/bin:/bin:/usr/sbin:/sbin`、`LANG=C`、`LC_ALL=C`。
- 以 directory FD＋`O_NOFOLLOW` 讀取固定 runner，對讀得 bytes 驗證 SHA-256。
- 將已驗證 bytes 寫入短命 materialization、以唯讀 FD 開啟後 unlink；不再重新信任 runner
  path。

GREEN result：

```text
1 passed in 0.05s
```

Test 同時證明 `BASH_ENV`／`ENV`／shell function import 與其他 hostile shell／loader／Python
environment 不會出現在 child；injected startup 與 swapped runner output 均不存在。

主線隨後補查真實 runner prologue：

```text
cd "$(dirname "$0")/.."
```

第一次 materialization 方案以 `/bin/bash /dev/fd/<fd>` 執行，observable RED 為：

```text
/dev/fd/3: line 4: artifacts/fog-entrypoint-env.txt: No such file or directory
1 failed in 0.06s
```

原因是 `$0=/dev/fd/<fd>`，prologue 會離開 sandbox。`/bin/bash -s --
scripts/run_fog_research_worker.sh` 也不可用；macOS Bash 會得到 `$0=/bin/bash`、名稱落在 `$1`。

Final minimal fix 將 unlink 後的唯讀 materialization FD `dup2` 到 stdin，再以
`os.execve("/bin/bash", ["scripts/run_fog_research_worker.sh", "-s"], environment)` 啟動。
因此 Bash 從固定 bytes stdin 讀 script，同時由 `argv[0]` 保留既有相對 runner 名稱；不使用
`bash -c`、pipe writer 或額外 descendant，也沒有 pipe buffer 上限。

Observable GREEN：

```text
3 passed in 0.11s
```

涵蓋 hostile environment／runner swap、真實 `$0` 對 sandbox cwd 語意、Bash 非 POSIX mode、
128 KiB runner（超過常見 pipe buffer）與 exit `37` 原樣傳遞。

## Root cause 2｜Exact `/dev/null` Seatbelt compatibility

可證偽假說：若 cycle blocker 只來自 profile 未授權 `/dev/null` write，則同一受限 child 先寫
`/dev/null`、再寫 sandbox、最後嘗試寫 protected outside path 時，修復前會在第一步 exit `1`；
新增 exact literal capability 後，前兩步成功且 outside write 仍被拒絕。

RED command：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  -p no:cacheprovider \
  tests/test_storage_safety.py::StorageSafetyRegressionTest::test_validation_confinement_allows_only_exact_dev_null_and_sandbox_write
```

RED result：

```text
AssertionError: 1 != 0
1 failed in 0.13s
```

Minimal fix：Seatbelt profile 只新增 `(literal "/dev/null")` 的 `file-read* file-write*`；既有
sandbox root 仍是唯一一般 write subpath。spawn 前 confinement probe 也明確要求 `/dev/null`
redirect 成功、sandbox write 成功與 scope 外 write 失敗。

GREEN result：

```text
1 passed in 0.22s
```

同一 integration test 證明 exact `/dev/null` 與 sandbox 內檔案可寫，protected outside 普通檔案
內容仍維持原值。

## Root cause 3｜Registered-but-unmetered writes

可證偽假說：若 gap 來自 `unknown_changed_paths()` 將整個 registered root 視為免檢，而
`take_sample()` 又只量測 meter roots，則 child 在 `artifacts` 下 meter 外新增 nested file 並修改
既有檔案時，guard 仍會錯誤回 `0`；新增獨立 registered-but-unmetered delta 後應 reason-coded
STOP。

第一個 RED：

```text
tests/test_storage_safety.py::StorageSafetyRegressionTest::test_guard_stops_registered_new_and_modified_files_outside_meter
AssertionError: 0 != 70
1 failed in 0.29s
```

Minimal fix：每次 runtime/final snapshot 同時計算「registered prefix 內、所有 meter prefix 外」的
新增、修改或刪除，觸發 `REGISTERED_WRITE_OUTSIDE_METER`；receipt 另存
`registered_unmetered_changed_paths`，不與真正的 `UNREGISTERED_WRITE_PATH` 混用。

第一個 GREEN：

```text
1 passed in 0.28s
```

第二個 RED 鎖定已知 call chain output：

```text
AssertionError: 'artifacts/host_runner' not found in (...)
1 failed, 8 subtests passed in 0.05s
```

Policy minimal fix 只把 `artifacts/host_runner` 加進 fog meter；`max_bytes=2147483648` 與
`max_file_count=30000` 完全不變。GREEN：

```text
1 passed, 8 subtests passed in 0.03s
```

Root cause 3 targeted regressions：

```text
3 passed, 8 subtests passed in 0.30s
```

涵蓋 meter 外新增、既有檔修改、nested path、known `artifacts/host_runner` 與重疊 meter paths
不重複計量。

## Final contract

- `fog_research_worker.py` 不再從 caller 複製任何 environment；只建立固定 `PATH`／locale／時區、
  固定 TOP10 contract 值與 sandbox-local HOME/tmp/cache/XDG paths。
- 固定 runner 以 directory FD＋`O_NOFOLLOW` 讀取；SHA-256 驗證的是實際保存並執行的 bytes。
  materialization 由唯讀 FD 持有且已 unlink，child 無 path 可替換或改寫。
- Bash invocation 為固定 executable、fixed `argv[0]` 與 `-s`；沒有 raw command remainder、
  `bash -c`、eval、pipe writer 或 dynamic command。
- Seatbelt 一般 write scope 仍只有 sandbox subpath；額外 capability 只指向 exact `/dev/null`。
- 每個 registered-root file change 要嘛符合 meter prefix，要嘛出現在 receipt 並觸發
  `REGISTERED_WRITE_OUTSIDE_METER`。Fog known output `artifacts/host_runner` 已納入 meter，ceiling
  未調高。

## Tests 與 static checks

Affected suites：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  -p no:cacheprovider tests/test_storage_safety.py tests/test_fog_storage_validation.py
45 passed, 16 subtests passed in 4.51s
```

Full suite：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q -p no:cacheprovider
1 failed, 678 passed, 4 warnings, 270 subtests passed in 64.72s
```

唯一 failure：
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
它與 reviewed candidate 已記錄的 ledger evidence gap 相同；本 Repair 未修改該 component、fixture
或 evidence。

下列 checks 通過：

- `python -m py_compile`：`app/storage_safety.py`、trusted adapter 與兩個 affected test modules。
- `python -m json.tool docs/operations/top10-storage-policy.json`。
- 全部八個 job `launch_verified == false`；fog bytes/files ceilings 保持原值。
- `git diff --check`。
- affected files 無 `[DBG-...]` marker。

## Protected state 與 production fail-closed

Main checkout dirty path 集合仍為原三檔，SHA-256 與 implementation preflight 完全相同：

```text
c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538  scripts/build_weekend_universe_inventory.py
ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9  tests/test_weekend_universe_inventory_snapshot.py
f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea  docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md
```

八個 launchd labels 收尾全部 `disabled` 且 `NOT_LOADED`。本 Repair 未執行 fog、任何 cycle／
代表性 workload、reclaim／stop-loss drill；未清除 sandbox 或 restart denial，未修改 production
data、artifacts、models，也未 merge／push／deploy。

## Changed files

- `app/storage_safety.py`
- `scripts/storage_validation/fog_research_worker.py`
- `docs/operations/top10-storage-policy.json`
- `tests/test_storage_safety.py`
- `tests/test_fog_storage_validation.py`
- `docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1.md`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/repair-1-verification.md`

## Residual risks

- 這是 strict contract Repair，不是 workload revalidation；修復後的 runner／Seatbelt／meter 組合
  尚未執行 fog。只有原 Reviewer targeted re-review 為 `REVIEW_GO` 後，主線才能另開 fresh
  revalidation 卡。
- Runner 從唯讀 materialization stdin 執行；已確認目前真實 runner 只以 `$0` 決定 cwd，沒有
  `BASH_SOURCE` 或 stdin read，並以 observable tests 鎖住 Bash mode、cwd 與 exit propagation。

## Generation 2｜Fixed Python bytecode policy

Reviewer 對 Generation 1 candidate `a04805f587aef48296b1a0046e5946c6b8c77f26` 的 tempfile
probe 發現新 P1：strict environment 清除了原固定 `PYTHONDONTWRITEBYTECODE=1`，runner 匯入
sandbox-local module 後會在 registered roots 外建立 `scripts/__pycache__/*.pyc`。前代 runner
integrity、meter 與 exact `/dev/null` findings 均維持 resolved，本代不重構那些邊界。

可證偽假說：若唯一 root cause 是 fixed environment 漏掉 bytecode 禁寫，則 hostile caller 即使
提供相反的 `PYTHONDONTWRITEBYTECODE=0` 與 `PYTHONPYCACHEPREFIX`，trusted runner 的 local import
仍會在 source tree 寫 `.pyc`；恢復固定 `PYTHONDONTWRITEBYTECODE=1` 後，source tree 與 caller
指定 prefix 都不會出現 cache，且其他 hostile `PYTHON*` 仍不會進 child。

RED command：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  -p no:cacheprovider \
  tests/test_fog_storage_validation.py::FogStorageValidationEntrypointTest::test_fixed_bytecode_policy_blocks_source_tree_pyc_from_local_import
```

RED result：

```text
AssertionError: ['scripts/__pycache__/probe_module.cpython-312.pyc'] != []
1 failed in 0.70s
```

這是實際 local-module import 產生 `.pyc` 的 observable failure，不是 import／fixture 或環境缺件。

Minimal fix：只在 `FIXED_ENVIRONMENT` 恢復
`PYTHONDONTWRITEBYTECODE=1`。不透傳 caller `PYTHON*`、不設定 caller
`PYTHONPYCACHEPREFIX`、不擴張 registered/meter roots，也不提高 ceiling。Hostile-environment
assertion 改為只允許這一個精確固定安全值。

Targeted GREEN：

```text
2 passed in 0.21s
```

同時涵蓋實際 local import 不產生 source-tree pycache，以及既有 hostile shell／Python
environment 仍被固定 allowlist 封住。

Generation 2 affected suites：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  -p no:cacheprovider tests/test_storage_safety.py tests/test_fog_storage_validation.py
46 passed, 16 subtests passed in 4.94s
```

Generation 2 full suite：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q -p no:cacheprovider
1 failed, 679 passed, 4 warnings, 270 subtests passed in 62.72s
```

唯一 failure 仍是既有
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
ledger evidence gap；本代未修改其 source、fixture 或 evidence。

Generation 2 static／state checks：

- Affected Python `py_compile`、policy JSON validation、八個 job `launch_verified=false` 與
  `git diff --check` 通過；affected files 無 `[DBG-...]`。
- Main checkout dirty path 集合與三個 protected SHA-256 均和前代／preflight 完全相同。
- 八個 launchd labels 全部 `disabled`、`NOT_LOADED`。
- 未執行 fog／cycle／workload，未清 sandbox／restart denial，未 merge／push／deploy。

Generation 2 changed files：

- `scripts/storage_validation/fog_research_worker.py`
- `tests/test_fog_storage_validation.py`
- `docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1.md`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/repair-1-verification.md`
