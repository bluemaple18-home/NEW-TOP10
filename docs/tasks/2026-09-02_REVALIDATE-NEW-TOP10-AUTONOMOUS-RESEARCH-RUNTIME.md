---
id: REVALIDATE-NEW-TOP10-AUTONOMOUS-RESEARCH-RUNTIME
status: RESOURCE_OPTIMIZED_CANDIDATE / EXTERNAL_REVALIDATION_PENDING / LIVE_ACTIVATION_NOT_AUTHORIZED
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

## Boundary

- 2 GiB ceiling 是保護其他專案的 candidate stop-loss，不等於驗證 PASS；不得為了讓 receipt 變綠再放寬。
- 不清理舊 sandbox、其他專案或不明檔案。
- 不載入、啟用、kickstart 或重啟 launchd；不 push、deploy、publish。
- 代表性驗證若需要數 GiB fresh sandbox 與高記憶體 workload，必須在執行前取得本輪明確資源授權。
