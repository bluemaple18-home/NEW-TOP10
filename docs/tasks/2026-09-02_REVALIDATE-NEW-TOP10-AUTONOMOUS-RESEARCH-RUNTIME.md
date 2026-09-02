---
id: REVALIDATE-NEW-TOP10-AUTONOMOUS-RESEARCH-RUNTIME
status: READY_FOR_REPRESENTATIVE_VALIDATION / LIVE_ACTIVATION_NOT_AUTHORIZED
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

## Validation plan

1. Static/runtime seam：shell、plist、queue-owner 與 targeted suites → `bash -n`、`plutil -lint`、pytest 全綠。
2. Capacity preflight：host free、memory pressure、swap、project bytes/files → start threshold 與 projected reserve PASS。
3. Fresh no-`.git` sandbox：同一 pinned contract 串行兩個 representative fog cycles → 兩份 receipt `OK`、有效 live samples、零 unknown/unmetered writes、process group quiescent。
4. Reclaim／stop-loss：驗證 allowlist 回收與只停止目標 group → PASS 才能提出 `launch_verified=true` candidate。
5. Live activation：不屬本卡；即使 candidate PASS，仍需 Owner 明確授權 load／enable／kickstart。

## Current evidence

- targeted suites：`77 passed, 31 subtests passed`。
- shell：fog、PM harness 均 `bash -n` PASS；兩份 plist 已安裝且 `plutil` PASS。
- host free：約 `53.1 GB`；project meter 約 `1.33 GB / 21,470 files`。
- memory pressure=`2`；swap 約 `5.75 GiB used`。
- production measure：fog 與 PM 均精確 `NO-GO / POLICY_NOT_LIVE_VERIFIED`。

## Boundary

- 本卡不修改 policy ceiling 追求 PASS。
- 不清理舊 sandbox、其他專案或不明檔案。
- 不載入、啟用、kickstart 或重啟 launchd；不 push、deploy、publish。
- 代表性驗證若需要數 GiB fresh sandbox 與高記憶體 workload，必須在執行前取得本輪明確資源授權。
