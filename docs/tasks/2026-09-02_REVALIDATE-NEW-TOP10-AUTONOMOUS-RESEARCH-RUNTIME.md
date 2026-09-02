---
id: REVALIDATE-NEW-TOP10-AUTONOMOUS-RESEARCH-RUNTIME
status: BLOCKED_REPRESENTATIVE_WORKLOAD_EMPTY_3 / LEDGER_MIGRATION_CONTRACT_STALE / LIVE_ACTIVATION_NOT_AUTHORIZED
type: runtime-revalidation
risk: high
baseline: d73001ca870974625530f33f0766e7abf5231124
---

# Autonomous Research Runtime Revalidation

👉 [假設與目標確認] 目標：證明自主研究 worker 在新版 memory-pressure stop-loss 下可安全完成兩個代表性週期；不碰正式排名、模型、推播、外部服務或 launchd 啟用；以兩週期 receipt、容量回收、停損與受影響測試全數通過判定。

## Runtime facts

- `com.new-top10.fog-research-worker` 與 `com.new-top10.pm-research-harness` 的 plist 已存在，但目前都未載入。
- PM harness 現行 shell 通過 `bash -n`；舊 log 的 unmatched quote 是歷史故障，不是目前 blocker。
- PM harness 是 disabled standby，queue owner 固定 `fog_worker`；恢復自主研究只應先處理 fog worker，不應同時啟用兩個 writer。
- `fog-research-worker.launch_verified=false`，production guard 會以 `POLICY_NOT_LIVE_VERIFIED` fail closed。
- 前次代表性 fog cycle 因全機 swap 單獨超限停止；`2999daa` 已將 stop-loss 改為 memory pressure 可讀時不以 swap growth 單獨停機，但尚未做 fog 兩週期重驗。

## Falsifiable hypotheses

1. 若目前停機主因是 intentional storage fail-closed，而非 runner code regression，則 targeted runtime suites 應通過、production measure 只剩 `POLICY_NOT_LIVE_VERIFIED`。
2. 若 `2999daa` 已修復前次 fog 誤殺，fresh representative cycle 在 memory pressure 低於 3 時，即使 swap growth 超過舊 ceiling也不應單獨 STOP。
3. 若 workload 本身仍造成連續 critical pressure、RSS／容量超限、sample cadence 失約或未登記寫入，cycle 必須 NO-GO，且不得執行第二週期或啟用 launchd。
4. 若 BLAS／OpenMP oversubscription 是可移除的資源風險，固定單執行緒並交由 launchd `Background`／低優先 I/O 執行後，代表性週期應能維持在 2 GiB 程序樹 RSS ceiling 內。

## Validation plan

1. Static/runtime seam：shell、plist、queue-owner 與 targeted suites → `bash -n`、`plutil -lint`、pytest 全綠。
2. Capacity preflight：host free、memory pressure、swap、project bytes/files → start threshold 與 projected reserve PASS。
3. Fresh no-`.git` sandbox：同一 pinned contract 串行兩個 representative fog cycles → 兩份 receipt `OK`、有效 live samples、零 unknown/unmetered writes、process group quiescent。
4. Reclaim／stop-loss：驗證 allowlist 回收與只停止目標 group → PASS 才能提出 `launch_verified=true` candidate。
5. Live activation：不屬本卡；即使 candidate PASS，仍需 Owner 明確授權 load／enable／kickstart。

## Current evidence

- 原 targeted suites：`77 passed, 31 subtests passed`。
- resource candidate suites：`71 passed, 31 subtests passed`；fog shell `bash -n`、plist lint、time wiring 與 `git diff --check` 全數 PASS。
- shell：fog、PM harness 均 `bash -n` PASS；兩份 plist 已安裝且 `plutil` PASS。
- host free：約 `53.1 GB`；project meter 約 `1.33 GB / 21,470 files`。
- memory pressure=`2`；swap 約 `5.75 GiB used`。
- production measure：fog 與 PM 均精確 `NO-GO / POLICY_NOT_LIVE_VERIFIED`。
- external sandbox target：`/Volumes/VibeCode`，可用約 `135 GiB`；`/Volumes/VibeSSD` 僅約 `32 GiB`，不採用。
- 啟動前連續兩次 memory pressure=`2`，swap 約 `5.5 GiB used`；為避免影響其他專案，本輪未建立 full sandbox、未啟動 representative workload。
- 前次新版代表性 cycle 的程序樹 peak RSS 為 `1,085,718,528 bytes`（約 1.01 GiB）；當時 STOP 原因是全機 swap growth `2,964,848,640 bytes`，不是程序 RSS 超限。
- candidate optimization：fog worker 預設將 OMP／OpenBLAS／MKL／NumExpr／vecLib 限為單執行緒；launchd 宣告 `ProcessType=Background` 與 `LowPriorityIO=true`；fog 程序樹 ceiling 由 4 GiB 收緊至 2 GiB，仍保留約 1.98 倍於最新代表性 peak 的 headroom。
- next condition：由 tmp artifact lifecycle seam 在 `/Volumes/VibeCode` 建立唯一 sandbox；第一週期非完整 PASS 即不跑第二週期。
- R1 external receipt：cycle 1 `OK` 但僅 `4.42s / 67,403,776 bytes RSS`，queue 已耗盡而非代表性 workload；cycle 2 因 `MISSING_VALID_LIVE_RESOURCE_SAMPLE` STOP。兩輪 memory pressure 均為 `2`、swap delta `0`，但整體 verdict 必須維持 `NO-GO / REPRESENTATIVE_WORKLOAD_EMPTY`。
- R1 另揭露共用 lifecycle 的 evidence staging 位於 sandbox volume，無法跨 volume 原子 rename 回 repo；candidate harness 已改為在目的 volume 建 staging 後原子發布，仍由 lifecycle 負責 sandbox ownership、budget 與 cleanup。
- R2 修正方向：validation-only fresh sandbox 固定 `TOP10_RESEARCH_ALLOW_RERUN=1`，避免正式 queue 已消耗時空跑；copy allowlist 排除 tests/docs/mlruns/web 等非 runtime roots，只補入 storage policy，維持 5 GiB／50,000 files lifecycle hard limit而不放寬預算。
- R2 external receipt：仍為 `4.46s / 73,678,848 bytes RSS` 空週期，cycle 2 同樣 `MISSING_VALID_LIVE_RESOURCE_SAMPLE`；證明 `--rerun` 依設計不能繞過 manager policy。直接資料比對確認真正 blocker 是 canonical `artifacts/market_regime_history.json` 僅到 `2026-07-27`，但 features 與既有 append-only authority 已到 `2026-09-01`。
- regime authority candidate：新增 v2 append-only updater，只採用 extension 中晚於 canonical end 的 26 個交易日，逐 byte 保留既有 282 個歷史 rows，並以 features 日期集合拒絕 gap；真實資料 copy 測試得到 `282 → 308 rows / end=2026-09-01`，沒有重算或覆蓋歷史 regime。
- R3 external receipt：regime updater 已產生 canonical 寫入，guard 因 `artifacts/market_regime_history.json` 在 registered `artifacts` 但未列入 fog meter 而以 `REGISTERED_WRITE_OUTSIDE_METER` STOP，依約未跑 cycle 2。當輪 memory pressure=`2`、swap delta=`0`、peak RSS=`51,249,152 bytes`；修正只把該精確 canonical path納入 fog meter，不擴張 write root。
- R4 external receipt：meter gap 已消失，但 no-`.git` sandbox 在 `publish_research_batch_intent.py` 以 `GIT_HEAD_UNAVAILABLE` 失敗；cycle 1 guard 本身 `OK` 是因 fog retry circuit 將 batch failure轉成受控結束，不能視為代表性 PASS，cycle 2則因 circuit skip而 `MISSING_VALID_LIVE_RESOURCE_SAMPLE`。修正以 pinned entrypoint contract 傳入 source commit，僅在 `TOP10_STORAGE_VALIDATION_MODE=1`、root 無 `.git` 且 digest 格式合法時作 batch identity；production checkout仍只信任實際 Git HEAD。
- R5 external receipt：pinned source identity 已通過；regime authority成功 append 26 日至 `2026-09-01`，但 autonomous outcome 仍為 `TOPIC_SUPPLY_EXHAUSTED / topic_runs=[]`。這是同一代表性 workload empty blocker 的第三次觀測，依規則停止 retry。
- R5 同時揭露第二個 live blocker：observation ingest 讀到舊 migration manifest，缺新版 disposition／inference／quality／reconciliation欄位而 fail closed；`data/research/research_ledger.duckdb` 的合法寫入亦尚未列入 fog registered write/meter paths。Guard因此以 `UNREGISTERED_WRITE_PATH` STOP，cycle 2未執行。
- R5 資源證據只可支持「優化沒有造成主機壓力」：memory pressure=`2`、swap delta=`0`、peak RSS=`51,118,080 bytes`；因無 topic run，不得支持代表性 2 GiB capacity PASS。

## Boundary

- 2 GiB ceiling 是保護其他專案的 candidate stop-loss，不等於驗證 PASS；不得為了讓 receipt 變綠再放寬。
- 不清理舊 sandbox、其他專案或不明檔案。
- 不載入、啟用、kickstart 或重啟 launchd；不 push、deploy、publish。
- 代表性驗證若需要數 GiB fresh sandbox 與高記憶體 workload，必須在執行前取得本輪明確資源授權。
- 下一張修復卡必須先建立一個受控、可執行且不繞過 manager policy 的 representative topic fixture，並升級或隔離 legacy migration corpus；在兩者完成前禁止再次重跑本卡或啟用 fog launchd。
