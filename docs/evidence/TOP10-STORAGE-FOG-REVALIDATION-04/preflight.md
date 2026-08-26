# TOP10-STORAGE-FOG-REVALIDATION-04｜Fresh preflight

## 判定

`PREFLIGHT_PASS_TO_CYCLE_1`。這只授權在下述同一 fresh sandbox／contract 執行一次
`fog-research-worker` cycle 1；不代表 cycle、fog 或 production PASS，也不授權 launchd。

## Dispatch、trace 與 reviewed source

- Formal thread：`019fc6e8-ba05-7b93-86ff-6187cb4f3b39`。
- projectId：`local-49c40f44270697f9bce80f898c3c5a4d`。
- provisioning HEAD：`1789132101b8e252cbd4cc5881709ee8b4029d6e`；worktree 啟動時 clean、
  detached HEAD，實際 git-dir 無 `index.lock`。
- reviewed source：`001e2dbe7f3a5743a3542c2a36680a3fac8a9fc9`，是 provisioning HEAD
  的直接親代；review thread `019fc6b3-94d8-7373-bdbc-07f82e048d88` final 為
  `REVIEW_GO`、`blocking_findings=0`、`residual_findings=0`。
- Repair 卡四個 anchors `AC-1` 至 `AC-4` 全部存在；reviewed tree 為
  `38168a212febcdf022dda32aed287120beadc3a2`。
- CodeGraph 在本 worktree 未初始化；為避免超出 allowlist 寫入索引，依規則改用限域 source
  inspection。核對入口為 `validate-run` → `load_trusted_validation_entrypoint()` →
  `run_guarded_job()` → fixed fog adapter → `scripts/run_fog_research_worker.sh`。

## 主機與 production fail-closed

- filesystem total：`245107195904` bytes。
- fresh sandbox 完成後 host free：`40498298880` bytes；高於 start threshold
  `max(30 GiB, 15%) = 36766079385.6` bytes。
- runtime reserve：`max(20 GiB, 10%) = 24510719590.4` bytes。即使 meter 再使用完整
  `2147483648` bytes，推估 free 仍為 `38350815232` bytes，高於 reserve。
- swap metric 可讀：total `7168.00 MiB`、used `5683.12 MiB`、free `1484.88 MiB`。
- 沒有 fog runner、`validate-run`、fog-map handoff 或 representative replay 目標程序；沒有
  TOP10 open-deleted file。
- 八個 `com.new-top10.*` labels 全部 `disabled` 且 `NOT_LOADED`；policy 八個 job 的
  `launch_verified` 維持 `false`。

## Main protected state

`<main-checkout>` 既存 dirty path 集合仍為前代三檔：

- `scripts/build_weekend_universe_inventory.py`：
  `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
- `tests/test_weekend_universe_inventory_snapshot.py`：
  `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
- `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
  `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

三檔不在本卡 allowlist；cycle 收尾必須重算且完全相同。

## 前代隔離與 fresh ownership

- `<previous-sandbox>` 仍存在，約 `2506644 KiB`；全程只讀。
- 前代 marker digest：
  `6c0af0aa838fea1e65524cd87f17f9ace19293ee4d84f3ea3dd3b29ec65d058e`。
- 前代 restart denial digest：
  `eea4c1027f1b944b96ffba9c9ee7abcedaacb81fedaf35d10919d17409ea91bb`。
- Fresh sandbox basename：`TOP10-STORAGE-FOG-REVALIDATION-04.6MlpK9`；card id、marker、
  contract、source SHA 與路徑均和前代可區分，沒有複製前代 local logs、runtime、marker 或
  restart denial。

## Bounded copy 與 fresh contract

- Copy 前核准 inputs 約 `2632308 KiB`／`44457` regular files：reviewed tracked source、
  `<main-checkout>/.venv`、`data`、`models`，以及前代卡已核准的 fog real-input artifact roots。
- `.venv` 原有三個 Python symlink 均解參照為 regular files；另從該 symlink 所指的 uv Python
  runtime bounded copy `libpython3.12.dylib`（digest
  `7e9ad60ae022b4dec28c50d5da1115eef632dc945eeaf3cef689e26e4f3ffe1b`）。第一次
  capability probe 在 library 補齊前由 dyld exit `134` fail closed；沒有執行 pytest 或 fog。
  補齊後 Python `3.12.12` 可執行。
- Fresh sandbox 完成後約 `2668864 KiB`／`46272` regular files；`.git=0`、symlink `=0`、
  bind mount `=0`、source-tree `__pycache__`／`.pyc=0`。
- Policy meter baseline：`711514382` bytes／`13885` files；`measure` 因 production
  `launch_verified=false` 正確回 `NO-GO / POLICY_NOT_LIVE_VERIFIED`，不作 validation verdict。
- Fresh marker digest：
  `9fbe2790dd164b6f4d6484c1a4452c92cea5faa79a1ed6b0b2426d0b4b1bb968`。
- Fresh contract digest：
  `d010144130c0cac4f6dca0155d172147977b8b2c6e227105b743874e87f9b0b8`。
- Entrypoint digest：
  `661b9a1b10dc8f932eb7c99afa7502cea34f416c07758ccb8cbe8615494427cd`。
- Runner digest：
  `2780a484e51950b2a6c30089d16111051f5bb3db71fe14e4be74d71923c8ae17`。
- Actual fresh marker 已由 `validate_isolated_root()` 與
  `load_trusted_validation_entrypoint()` 驗證 path、job、schema、contract、entrypoint 與 argv。

## Reviewed regression／confinement probes

相同 reviewed source 在 worktree 與 fresh sandbox 各跑一次：

```text
PYTHONDONTWRITEBYTECODE=1 <venv-python> -B -m pytest -q \
  -p no:cacheprovider tests/test_storage_safety.py tests/test_fog_storage_validation.py
46 passed, 16 subtests passed
```

涵蓋 hostile env、verified runner bytes、`$0`／cwd、128 KiB／exit propagation、固定 bytecode、
exact `/dev/null`、sandbox 外 write denial、registered-unmetered meter invariant、PGID 與 scope。
所有 capability、digest、freshness、write-root 與 capacity gate 均通過後，才授權 cycle 1。
