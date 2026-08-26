---
id: TOP10-STORAGE-DAILY-VALIDATION-HARNESS
chain_id: TOP10-STORAGE-DAILY-VALIDATION
status: candidate
created_at: 2026-08-27
owner: Storage validation Worker
base_commit: 208dd1d
---

# TOP10-STORAGE-DAILY-VALIDATION-HARNESS｜Daily sandbox 代表性驗證入口

## Root question

如何在不發送 Clawd／Discord／ops、不中斷 production、launchd 全程 disabled、policy
`daily.launch_verified=false` 的前提下，建立 digest-pinned sandbox-only 的 daily storage
validation seam，讓兩個 serial real-data daily cycle 可由 `scripts/storage_safety.py validate-run`
收完整 receipt？

## 邊界

- 不修改 launchd control plane，不 load、enable、kickstart、reload 或 restart。
- 不修改 production notification default，不把 `daily.launch_verified` 改成 `true`。
- 不放寬 `validate-run` 的 no-`.git`、symlink、source immutability、digest、Seatbelt、
  unknown-write 或 PGID guards。
- 不建立第二套 daily pipeline；validation entrypoint 必須重用 canonical daily orchestrator。
- 所有 output、cache、tmp 只能進 fresh sandbox；source input 唯讀且 receipt 必須可驗 hash／identity。
- 外部發送必須由 code contract hard-disable，不可只靠 env 約定。
- 本卡不執行實際兩週期、不 external send、不 reclaim live、不 push。

## 驗收

1. RED：現況沒有 daily trusted validation entrypoint，因此 focused test 必須先失敗。
2. GREEN：新增最小 daily validation entrypoint，可在 sandbox 內重用
   `app.automation.daily_orchestrator.run_daily` 與 `run_daily_final_artifacts`，輸出 cycle receipt。
3. Receipt 包含 source root identity、來源檔 SHA-256、orchestrator call sequence、external send
   disabled contract、sandbox output roots、cycle id 與 run date。
4. `scripts/storage_safety.py validate-run` 保持既有 digest-pinned trusted entrypoint contract，
   且不恢復 raw command seam。
5. 驗證：focused tests、storage policy JSON schema/self-test、`git diff --check` 通過。
6. 交付單一 candidate commit；若 git 權限阻擋，回報主線代 commit。

## Blocked receipt

`BLOCKED / REPRESENTATIVE_SEAM_REQUIRES_PROJECT_ROOT_PARAMETERIZATION`

目前可安全建立的 digest-pinned entrypoint 只能做到 sandbox wrapper；若不改 production
daily actions 的 root contract，`scripts.run_automation` 仍以 module-level `PROJECT_ROOT`
綁定 checkout。替代方案有兩個都不符合本卡：

- 在 validation harness 內重作 `DailyAutomationActions`：會變成第二套 daily pipeline，且只會
  產 placeholder storage output，不能代表 canonical ETL／ranking／report implementation。
- 把 source checkout 大量複製到 sandbox 再跑 `python -m scripts.run_automation daily`：會把
  source input bytes 混入 sandbox output growth，破壞 source-input-readonly 與 capacity receipt
  語意，也不能證明所有 writes/cache/tmp 只來自 daily cycle。

要完成 GREEN，需要先把 production `AutomationRunner`／command runner 的 source root、output
root、runtime cache root 變成受測 contract，讓 canonical daily implementation 可在 source
唯讀、output sandbox 的狀態下實際執行。這超過本 slice 的「不重構大量 PROJECT_ROOT globals」
限制，因此停止，不宣稱 representative。

## Candidate receipt

`CANDIDATE / DAILY_ROOT_PARAMETERIZATION_MINIMAL`

本 slice 已補上最小 roots contract，讓 daily validation entrypoint 可用 canonical
`scripts.run_automation.AutomationRunner` 執行 `run_daily` 與 `run_daily_final_artifacts`：

- `source_root`：讀 source code、config、reference data、model input。
- `output_root`：寫 `data/`、`artifacts/`、`logs/`。
- `runtime_root`：寫 validation cache/tmp。

Production defaults 維持未傳 roots 時的 checkout 行為；`python -m app.agent_b_ranking`
不帶參數時仍使用原本 `data/clean`、`models`、`artifacts`、`config/signals.yaml`。

### Changed-file allowlist

- `scripts/run_automation.py`
- `app/agent_b_ranking.py`
- `scripts/storage_validation/daily.py`
- `tests/test_daily_storage_validation.py`
- `docs/tasks/2026-08-27_TOP10-STORAGE-DAILY-VALIDATION-HARNESS.md`

### Validation-mode contract

- `validation_mode=True` 時只保留 ETL、validate、ranking、daily report、Clawd-ready
  payload；candidate persistence、weekly snapshot、TSKG、market context、decision quality、
  shadow monitors、postcheck 均由 code-level config override 關閉。
- Clawd payload builder 仍只產 publish-ready artifact；LLM rewrite 在 runner code path 直接
  `SKIPPED`，不依賴外部 env 約定。
- Receipt 包含 source identity pre/post hash、orchestrator step sequence、commands、sandbox
  output roots、external send disabled contract、ranking/report/payload artifact SHA。

### Verification

- `RED`：新增前 `tests/test_daily_storage_validation.py` 兩測皆失敗，原因為缺
  `scripts/storage_validation/daily.py`。
- `GREEN`：`.venv/bin/python -m pytest tests/test_daily_storage_validation.py -q`
  → `2 passed`。
- Affected suite：
  `.venv/bin/python -m pytest tests/test_daily_storage_validation.py tests/test_daily_automation_orchestrator.py tests/test_automation_status_contract.py tests/test_clawd_publish_payload_boundary.py -q`
  → `12 passed, 3 subtests passed`。
- Storage safety suite：
  `.venv/bin/python -m pytest tests/test_storage_safety.py -q`
  → `57 passed, 31 subtests passed`。
- Compile:
  `.venv/bin/python -m py_compile scripts/run_automation.py scripts/storage_validation/daily.py app/agent_b_ranking.py`
  → passed。
- Whitespace:
  `git diff --check` → passed。

### Boundary not executed

本卡未執行兩個 serial real-data daily cycles、未 load/enable/kickstart launchd、未外送、
未 live reclaim、未 push。正式代表性容量驗證仍須由後續 fresh sandbox 透過
`scripts/storage_safety.py validate-run` 執行兩個 real cycles 後，才能更新
`daily.launch_verified` 判定。

## 2026-08-27 Operator acceptance attempt

`NO-GO / REPRESENTATIVE_SNAPSHOT_MISSING`

本輪在 source checkout
`/private/tmp/top10-daily-storage-validation-20260827`
（HEAD `f6f514fd7b2f31c434e2aef1492bb89b269955be`）執行 strict acceptance。起始
Rule24 host free/swap gate 通過，且 read-only launchd evidence 顯示八個
`com.new-top10.*` job 均 disabled、`com.new-top10.daily` not loaded。

但 source root 內沒有可交給 `ValidationSnapshotProvider` 的 real-data snapshot：
`data/clean/features.parquet` 不存在，`data/reference/tradable_universe.csv` 不存在，
`data/clean`、`data/raw`、`data/reference` 只有 `.gitkeep` 或非行情 fixture。依任務邊界，
不得改用 bounded fixture、不得觸發 provider network、不得從其他 checkout 借資料。

已建立 fresh no-`.git` sandbox：
`/private/tmp/top10-daily-validation-sandbox-20260827-no-go-1`。第一次使用 `/tmp/...`
contract path 時被 lexical symlink guard 拒絕，修正為 `/private/tmp/...` 後，cycle-1
以 digest-pinned contract 進入 `validate-run`，並 fail closed：

- guard receipt: `docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/cycle-1-guard-receipt.json`
- child log: `docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/cycle-1-child.log`
- child error: `validation snapshot input 必須是存在且非 symlink 的一般檔案`
- guard status: `CHILD_FAILED`
- samples: `preflight` / `live` / `final`
- peak RSS: `3997696` bytes
- swap delta: `0` bytes
- unknown writes: `[]`
- registered-unmetered writes: `[]`

依 acceptance 指示，cycle-1 非 OK 後停止，未執行 cycle-2。sandbox-only reclaim drill
已執行；在 allowlist `logs/*.log` 中加入 stale probes 後，`reclaim --execute` 回收
`105` bytes / `3` files，removed paths 全部位於 sandbox logs。source checkout 在
validation 與 reclaim 後均維持 clean，核心 source/config/model SHA 前後一致。

本輪不提出 `daily.launch_verified=true` candidate；policy 只能維持 fail closed，並記錄
`REPRESENTATIVE_SNAPSHOT_MISSING` 作為新的 verification basis。完整 machine summary 見
`docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/no-go-summary.json`。

## 2026-08-27 Corrected main-source acceptance attempt

`PASS / DAILY_LAUNCH_VERIFIED_POLICY_CANDIDATE`

主線更正 source selection：validation worktree 缺少 Git-ignored real data，但 main checkout
`/Users/mattkuo/TOP10new` 存在可用 real-data snapshot。本輪以 main checkout 作 read-only
`source_root`，fresh no-`.git` sandbox 作 `output_root` / `runtime_root`，未 load、enable、
kickstart launchd，未執行 publish wrapper，未 external send，未 push。

Preflight evidence：

- main HEAD：`f6f514fd7b2f31c434e2aef1492bb89b269955be`
- main 既存 modified files hash 已保護，前後不變：
  - `scripts/build_weekend_universe_inventory.py`
  - `tests/test_weekend_universe_inventory_snapshot.py`
- `data/clean/features.parquet` 是 regular file、非 symlink，SHA-256
  `6dfeed9a54ff5513c516e4aa1e0a6258bd7a8e1f7c61036459d72da96b64d7c9`
- `ValidationSnapshotProvider` gates PASS：`532255` rows、`1967` stocks、
  `282` trade dates、`2025-06-06..2026-07-31`、latest coverage `98.98%`、
  markets `TPEX/TWSE`
- `data/reference/tradable_universe.csv` 是 regular file、非 symlink，`1967` rows/stocks
- launchd read-only evidence：八個 `com.new-top10.*` jobs disabled，`com.new-top10.daily`
  not loaded

Execution evidence：

- sandbox：`/private/tmp/top10-daily-validation-sandbox-20260827-main-source-2`
- cycle-1 guard receipt：
  `docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/main-source-pass/cycle-1-guard-receipt.json`
- cycle-1 child receipt：
  `docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/main-source-pass/cycle-1-child-receipt.json`
- cycle-2 guard receipt：
  `docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/main-source-pass/cycle-2-guard-receipt.json`
- cycle-2 child receipt：
  `docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/main-source-pass/cycle-2-child-receipt.json`
- both cycles：guard `OK`、child exit `0`、source identity unchanged、
  unknown writes `[]`、registered-unmetered writes `[]`
- worst observed cycle delta：`344530180` bytes
- observed two-cycle peak project bytes：`473750353`
- peak RSS：`1575763968` bytes
- max swap delta：`333185024` bytes
- sandbox-only reclaim drill：回收 `72` bytes / `2` files，removed paths 全部在 sandbox
  `logs/*.log`
- projection：14d worst peak `4823422520` bytes < daily cap `6442450944` bytes；
  projected host headroom `9374072499` bytes above runtime reserve

Policy update：只將 `daily.launch_verified=true`，verification basis 指向本輪 PASS evidence；
其他七個 job 維持 `launch_verified=false`。完整 machine summary 見
`docs/evidence/TOP10-STORAGE-DAILY-VALIDATION-20260827/main-source-pass/pass-summary.json`。
