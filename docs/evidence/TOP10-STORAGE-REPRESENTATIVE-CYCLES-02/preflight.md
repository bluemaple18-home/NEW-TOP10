# Checkpoint 0｜Preflight 與隔離設計

## 判定

`PASS_TO_BUILD_VALIDATION_SANDBOX`。此判定只允許建立隔離 sandbox 與執行 guarded manual
validation cycles，不代表任何 production job 已通過，也不授權啟用 launchd。

## Git 與工作區

- Formal thread：`019fc585-f6aa-7a30-9a37-a1291274f98c`
- projectId：`local-49c40f44270697f9bce80f898c3c5a4d`
- dispatch base：`93fb825138774a206a27792f1cbec75e0dd65abb`
- 啟動時 HEAD：`93fb825138774a206a27792f1cbec75e0dd65abb`，符合 required base。
- 啟動時 worktree：獨立 Codex worktree、detached HEAD、`git status --porcelain` 無輸出。
- `.git/index.lock` 與實際 git-dir 的 `index.lock` 均不存在。
- main checkout 保留既存 dirty state，未納入本卡：
  - `scripts/build_weekend_universe_inventory.py`：`c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
  - `tests/test_weekend_universe_inventory_snapshot.py`：`ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：`f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

## CodeGraph 與 source 決策

CodeGraph `status` 與 `context` 都回報本 worktree 尚未初始化。為避免建立不在 allowlist 的
`.codegraph` 狀態，本卡依規則改用限域 `rg` 與 source inspection。

Source 確認：

- policy loader、preflight、runtime sampling、receipt、reclaim、process-group stop 與 restart
  denial 都集中在 `app/storage_safety.py`。
- CLI 位於 `scripts/storage_safety.py`；production wrapper 位於
  `scripts/run_with_storage_guard.sh`。
- 八個 policy job key 與卡片完全一致，且全部 `launch_verified=false`。
- 八個 plist 都先進 production storage wrapper；validation 不改 plist、不呼叫 launchctl
  load／enable／kickstart／restart／reload。
- 八個原始入口依序為：
  - `daily` → `scripts/run_daily_publish.sh`
  - `retrain` → `scripts/daily_retrain.sh monitor --trigger scheduled`
  - `reference` → `scripts/run_reference_update.sh`
  - `fog-research-worker` → `scripts/run_fog_research_worker.sh`
  - `pm-research-harness` → `scripts/run_pm_research_harness_loop.sh`
  - `external-review` → `scripts/run_external_review_host_runner.sh`
  - `external-review-preflight` → `scripts/run_external_review_provider_preflight.sh`
  - `baseline-harness` → `scripts/run_baseline_harness_host_runner.sh`

## 主機容量與程序基線

- filesystem total：`245107195904` bytes。
- free：`60164157440` bytes（`24.546%`）。
- 啟動門檻：`36766079385` bytes（`max(30 GiB, 15%)`）；目前高於門檻。
- runtime 保留線：`24510719590` bytes（`max(20 GiB, 10%)`）。
- worktree 基線：`27930624` bytes（`du -sk=27276`），`1796` files。
- swap 可讀：total `5120.00 MiB`、used `3892.38 MiB`、free `1227.62 MiB`。
- 限域 process scan 沒有現存 TOP10new workload；先前唯一命中是正在執行基線量測的
  shell 本身，命令結束後重掃無命中。

## Launchd 狀態

`launchctl print-disabled gui/<uid>` 對下列八個 label 全部回報 `disabled`，且
`launchctl list` 沒有任何 label 命中：

- `com.new-top10.daily`
- `com.new-top10.retrain`
- `com.new-top10.reference`
- `com.new-top10.fog-research-worker`
- `com.new-top10.pm-research-harness`
- `com.new-top10.external-review`
- `com.new-top10.external-review-preflight`
- `com.new-top10.baseline-harness`

## Validation-only 隔離契約

本卡新增的 `validate-run` 不修改 `launch_verified`，production `run` 路徑仍 fail closed。
validation 路徑只有同時符合以下條件才可略過 `POLICY_NOT_LIVE_VERIFIED`：

1. 執行根目錄沒有 `.git`，因此不能是 main checkout 或 Codex worktree。
2. 根目錄內存在 schema、job allowlist、sandbox root 與 `manual_only=true` 都相符的 marker。
3. source input 先 clone 到本卡專屬 sandbox；child 不取得 main checkout 寫入路徑。
4. sandbox input/output 必須解析在 sandbox root 內且不得為 symlink。
5. TMP、uv、XDG、Matplotlib 與 joblib cache 全部收斂到
   `logs/storage_safety/runtime/<job>/`。
6. 每次 cycle 必須帶 hard runtime；逾時只停止 guard 建立的 process group，留下 persistent
   restart denial，且不自動 retry。
7. receipt 明列 `validation_only=true`、`launch_verified=false`、runtime limit、resolved roots、
   samples、容量／檔數／free space／RSS／swap delta、growth rate、reclaim 與未知寫入。

Affected storage tests 在 sandbox 建立前為 `15 passed`。production readiness 仍是 `NO-GO`。
