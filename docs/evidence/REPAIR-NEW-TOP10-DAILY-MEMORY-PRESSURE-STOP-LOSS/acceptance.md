---
id: REPAIR-NEW-TOP10-DAILY-MEMORY-PRESSURE-STOP-LOSS-ACCEPTANCE
status: pass
type: acceptance
---

# Daily 記憶體壓力停損修正驗收

## 結論

`PASS`。全機 swap 增長不再於 memory pressure 可讀且非 critical 時單獨停止 daily；整機 critical／jetsam、專案 RSS、RSS 與 swap 同步持續上升、磁碟與寫入邊界仍保留停損。memory-pressure sensor 不可讀且 swap 超標時維持 fail-closed fallback。

## 固定來源

- 基準 SHA：`a6fbf839153e66f267e3855b1893147a888e2ef6`
- Source SHA-256：`f358db3f7bd35932ff62f6d163b3f0e64f292b399e0a8f4e916fcc198b707c81`
- Test SHA-256：`b1b2624283ccdd10577d0c7f624fb1b49716d79c547f2c2829969a877a2d108f`
- Real-data snapshot SHA-256：`93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2`
- XNU pressure levels：Apple XNU `doc/vm/memorystatus_notify.md`，Normal=0、Warning=1、Urgent=2、Critical=3、Jetsam=4。

## 停損矩陣

| 情境 | 結果 |
|---|---|
| 啟動前 pressure >= 3 | `HOST_MEMORY_PRESSURE_CRITICAL_OR_JETSAM`，拒絕啟動 |
| 執行中連續兩個 live pressure >= 3 | `MEMORY_PRESSURE_CRITICAL_OR_JETSAM`，停止專案程序群組 |
| swap 超標、最新 pressure 可讀且 < 3、專案 RSS 穩定 | 繼續執行 |
| swap 超標、最新 pressure 不可讀 | `MEMORY_PRESSURE_METRIC_UNAVAILABLE_SWAP_GROWTH_BUDGET_EXCEEDED`，fail closed |
| 專案 RSS 超標 | 既有 `PROCESS_TREE_RSS_BUDGET_EXCEEDED` 保留 |
| 專案 RSS 與 swap 連續三點同步上升 | 既有 `RSS_AND_SWAP_RISING` 保留 |

## 驗證證據

- macOS host 唯讀 sensor probe：`kern.memorystatus_vm_pressure_level=1`，一般 launchd 使用者可讀。
- Targeted＋affected regression：`78 passed, 31 subtests passed`。
- Python compile：`app/storage_safety.py`、`tests/test_storage_safety.py` 通過。
- `git diff --check`：通過。
- 2026-09-01 incident receipt 重播：pressure 可讀且非 critical 時 reasons=`()`；最新 pressure 不可讀時精準回 fallback reason。
- `run_guarded_job()` fallback drill：child exit `70`、receipt `STOPPED`、restart denial marker 建立，無關程序仍存活。

## 代表性兩週期

兩輪皆以 `<repo-root>/data/clean/features.parquet`、run date `2026-08-31`，在無 `.git` 的隔離 sandbox 執行；未 reload launchd、未 external send、未 push。

| Cycle | Status | Elapsed | Peak RSS | Swap delta | Peak pressure | Unknown writes |
|---|---:|---:|---:|---:|---:|---:|
| cycle-2 | OK | 51.82s | 4,030,464 B | +443,484,733 B | 1 | `[]` |
| cycle-3 | OK | 51.51s | 4,030,464 B | -16,840,131 B | 1 | `[]` |

Raw receipts：`cycle-2-guard-receipt.json`、`cycle-3-guard-receipt.json`。

## 操作邊界

- 未調高 2 GiB swap budget，未放寬 4 GiB 專案 RSS、磁碟、寫入路徑或 cadence 停損。
- 未 reload／kickstart 排程；正式 launchd 仍指向 `<repo-root>`，下一次 daily 會讀取目前工作樹的 source diff。
- 本卡沒有 commit／push；回退方式是回退本卡的 `app/storage_safety.py` 與 `tests/test_storage_safety.py` diff。
