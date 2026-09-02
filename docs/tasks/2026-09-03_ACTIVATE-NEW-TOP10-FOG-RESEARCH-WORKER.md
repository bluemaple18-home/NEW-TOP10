---
id: ACTIVATE-NEW-TOP10-FOG-RESEARCH-WORKER
status: IN_PROGRESS
type: operations
risk: high
baseline: 1400573
---

# 啟用 Fog Research Worker 排程

👉 [假設與目標確認] 目標：依 R18 外接雙週期證據，只啟用 `com.new-top10.fog-research-worker`；邊界：不啟用其他 TOP10 jobs、不外送、不 promotion、不 push／deploy；驗收：storage policy 解除本 job 的 fail-closed、installed plist 必須走 storage guard、launchd label enabled／loaded，且正式入口 live receipt 無 stop-loss。

## 固定證據

- R18 runtime 兩輪 `OK`，topic run count 各 `1`。
- peak RSS `799,424,512`／`758,562,816 bytes`，低於 2 GiB ceiling。
- pressure 全程 `1`、unknown writes `[]`、process groups quiescent。
- 外層 lifecycle exit `0` 且 clean-room 已清除。

## 停止條件

- `launch_verified` 契約或受影響測試未通過。
- installed plist 未經 `run_with_storage_guard.sh`。
- 主機保留空間、swap sensor、restart-denied marker或 live receipt 任一 fail closed。
- 發現 production promotion、外送、push 或其他 job 被啟用。

## History

- 2026-09-03：Owner 明確授權正式啟用 Fog 排程；preflight 發現 policy 仍為 `launch_verified=false`，且舊 installed plist 直接呼叫 worker、未經 storage guard，因此先維持 NO-GO 並進行最小修復。
- 2026-09-03：policy contract RED 證實 Fog 尚未解除 live fail-closed；只將 R18 evidence 投影為 `fog-research-worker.launch_verified=true`，2 GiB bytes／30,000 files／2 GiB RSS／2 GiB swap ceilings 全部維持。受影響回歸 `73 passed, 31 subtests passed`，shell syntax 與 plist lint 通過。
- 2026-09-03：production preflight measure `PASS`；project `1,329,698,116 bytes / 21,485 files`、host free `45,370,826,752 bytes`、memory pressure `1`，restart-denied marker 不存在且沒有既有 Fog worker。
- 2026-09-03：首次 live activation 在 representative replay drain 第 4 批由 guard 停止；receipt 為 `STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED / child_exit_code=143`，最後 completion gap 約 `60.470s > 60s`。當時 peak RSS `662,241,280 bytes`、project bytes delta `-173,701,918`、file count delta `-8,345`、swap delta `-192,937,984`，故排除容量、RSS 與 swap 超限；process group 已 quiescent，persistent restart denial 保留。
- 2026-09-03：Owner 明確允許停用；`com.new-top10.fog-research-worker` 已 disabled／bootout，無殘留 worker。RCA 假說排序：(H1) `measure_paths()` 對每個 regular file 執行 `Path.resolve()`，在 worker 同時掃描 inventory 時放大 I/O contention，使 sample duration 從常態約 `0.4s` 尖峰至約 `4.25s`；若移除逐檔 canonicalization 且維持 lexical symlink boundary／overlap dedup，成本與 cadence 症狀應下降。(H2) 95% target headroom 不足；既有契約禁止先改 target 或 60s ceiling，只有 H1 修復仍無法收斂時才重新裁決。
