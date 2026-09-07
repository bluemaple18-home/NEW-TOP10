# Fog natural acceptance evidence bounded repair

任務：`REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01`

結論：本地修補與程式驗收為 `CANDIDATE_GREEN`；live Fog 仍為 `NATURAL_ACCEPTANCE_PENDING`。Owner 後續已授權 commit／deploy，但 deploy preflight 發現既有 runtime restart-denied marker，因此 fail closed；本輪沒有 activation、kickstart、marker 清除、舊 receipt 回填或 push。

## 修補結果

- Fog worker 於成功結束後，依 exact `invocation_id` 發布 atomic、immutable terminal evidence，包含 `artifact_run_date`、`run_id`、terminal result、canonical event path 與 hash。
- evidence writer/reader 以既有 Fog time authority 驗證 `artifact_run_date`，並使用 anchored dirfd、`O_NOFOLLOW/O_DIRECTORY`、same-fd `fstat/read/publish` 防止 symlink 與 path-swap。
- Storage Guard 只在 child exit 且 final process group quiescent 後讀取 exact invocation evidence；不讀 `latest`。
- natural provenance 由 source Fog plist `StartInterval`、相鄰 archived receipt、`scheduled_at` 與 invocation timestamp binding 驗證；PPID=1 只形成 candidate。
- acceptance gate 同時要求 artifact、cadence、child exit=0、final quiescence、denial marker absent、Fog worker lock absent 與 research queue lock absent。
- 舊的 pending/0 receipt 可作 cadence anchor但不計入 accepted counter；第一個新合格週期為 1，第二個連續合格週期才為 `ACCEPTED`。

## RED／GREEN

Mainline probe：

- Round 1 RED：`stale_date_verified True 2026-09-06`；Repair 1 GREEN：`stale_date_rejected ValueError`。
- Round 1 RED：`old_anchor False 0 PREVIOUS_RECEIPT_NOT_QUALIFIED`；Repair 1 GREEN：`old_anchor True 1 None`。

需求情境已由 tests 覆蓋：缺 exact evidence 維持 pending、artifact 正確但 cadence 未驗證維持 pending、雙 gate 通過才累加、連續兩輪才 accepted，以及 latest-only／錯 identity/date/hash／symlink/path-swap／marker／locks 的 fail-closed 行為。

## 驗證

- Mainline targeted suite：`139 passed, 38 subtests passed in 19.00s`。
- 唯一既有時序測試曾在第一次沙箱外 full run 多取一次 live sample；隔離重跑通過，第二次完整 targeted suite 亦全綠，且該測試本卡無差異。
- 8 個 Fog shell regressions：lock contention、lock identity、partial lock、verified cleanup failure、retry circuit、resource budget、runtime time wiring、signal teardown，全部 exit 0。
- `bash -n scripts/run_with_storage_guard.sh`：通過。
- `bash -n scripts/run_fog_research_worker.sh`：通過。
- 變更 Python 檔 compile：通過。
- `git diff --check`：通過。
- 兩名原 Reviewer 對 Repair 1 fixed manifest 的獨立重審：`GO / GO`，無新 P0/P1。

## 邊界與後續

- 這是 local-only code candidate，不是 live acceptance 證明。
- 既有 `fog-research-worker-20260907T070804Z-4310` 不得回填為 accepted。
- Owner 已授權本地 commit 與 production deploy；push 仍未授權。
- production runtime `/Users/mattkuo/TOP10-runtime-automation-26c8834` 存在 `logs/storage_safety/restart_denied/fog-research-worker.json`。其 root invocation 為 `fog-research-worker-20260907T090500Z-80610`，理由為 `REGISTERED_WRITE_OUTSIDE_METER`，列出的變更來自 17:40 external-review-preflight artifacts；Fog child exit `143`，final process group 已 quiescent。
- activation transaction 會處理／清除舊 marker；這與本卡「不得清 marker」衝突，因此 Mainline 沒有執行 deploy。此 blocker 必須先以獨立 bounded root-cause card 處理 cross-job write attribution／隔離，再由 Owner 明確核准 marker clear。
- 部署後只能由原有自然排程產生兩個新的連續合格週期；不得以 manual kickstart 製造驗收。
- 現有允許輸入無法區分「恰好落在 cadence window 的 manual kickstart」與 natural fire；本卡沒有新增第二 ledger 或虛構 provenance authority。
