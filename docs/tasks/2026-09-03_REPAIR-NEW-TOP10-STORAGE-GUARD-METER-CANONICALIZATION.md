---
id: REPAIR-NEW-TOP10-STORAGE-GUARD-METER-CANONICALIZATION
status: READY
type: repair
risk: high
baseline: 636519e
model_lane: gpt-5.5-high
parent: ACTIVATE-NEW-TOP10-FOG-RESEARCH-WORKER
---

# 修復 storage guard meter inventory 的 O(files) canonicalization

## 五行派工卡

- 目標：修復 Fog live sampling 在 13k metered files 與 inventory I/O contention 下超過 60 秒 cadence 的最小根因。
- 範圍：`app/storage_safety.py`、`tests/test_storage_safety.py`，以及本卡 History／verification；先查 CodeGraph，再由原始碼確認 seam。
- 禁區：不得改 60 秒 hard maximum、95% target、容量／RSS／swap ceilings、launch policy；不得清 restart-denied、啟用 launchd、重跑 live workload、push 或 deploy。
- 驗收：先跑可抓到 O(files) canonicalization 的 RED；最小修復須維持 overlapping meter dedup、symlink boundary、bytes/file count 語義，再跑 targeted GREEN、完整 storage safety tests 與 `git diff --check`。
- 交付：單一原子 commit，回報 SHA、實際 diff、RED/GREEN、微基準與剩餘風險；Mainline 負責最終 GO／NO-GO。

## 固定失敗證據

- Live receipt：`logs/storage_safety/fog-research-worker_latest.json`。
- 結果：`STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED / child_exit_code=143`；最後兩筆 completion gap 約 `60.470s > 60s`。
- Guard 正確停損且 process group quiescent；restart denial 為 `automatic_clear_allowed=false`。
- 同輪資源並未超限：peak RSS `662,241,280 bytes`、project bytes delta `-173,701,918`、file count delta `-8,345`、swap delta `-192,937,984`。
- 101 筆樣本中，前 99 筆 live completion delta 相對 57 秒 target 多數約 `0.3–1.2s`，最後一筆升至約 `3.854s`；本機 13,140 files 的 `take_sample()` 常態約 `0.39–0.48s`。
- `measure_paths()` 目前對每個 regular file 執行 `Path.resolve()`；兩個重疊 roots／100 files 的暫時性 RED probe 曾量到 `204` 次 resolve，移除逐檔 resolve 的本地探針將 13,140 files 常態 sample 降至約 `0.17–0.24s`。這些只是假說證據，不是可直接承接的 implementation；Worker 必須自行建立 RED。

## 可證偽假說

1. H1：meter root 已 canonicalize 且 walker 拒絕 symlink，逐檔 `Path.resolve()` 是多餘 O(files) I/O；若改成不需逐檔 filesystem canonicalization 的安全去重，resolve call growth與 sample 常態成本應下降，重疊 meter 結果維持不變。
2. H2：95% target 的 3 秒 headroom 本身不足；既有契約禁止本卡改 target。只有 H1 經驗證仍不足時，回 Mainline 另開 architecture fork，不得在本卡擴 scope。

## 停止條件

- 無法建立同症狀的 deterministic RED。
- 修復需要放寬任何 safety ceiling／cadence 語義。
- symlink 或 overlapping meter invariants 退化。
- 發現 canonical path identity 不能由既有 root／walker contract 保證。

## History

- 2026-09-03：Mainline 根據首次 live activation stop-loss 開卡；Fog label 已 disabled／bootout，無殘留 worker，persistent restart denial 保留。
