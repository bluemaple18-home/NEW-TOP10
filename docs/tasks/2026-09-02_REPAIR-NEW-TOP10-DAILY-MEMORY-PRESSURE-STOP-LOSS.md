---
id: REPAIR-NEW-TOP10-DAILY-MEMORY-PRESSURE-STOP-LOSS
status: completed
type: implementation
---

# Daily 記憶體壓力停損修正

## Root question

如何保留整機即將失去回應時的緊急停損，同時避免 daily 因其他工作造成的全機 swap 增長而被單獨誤殺？

## 已確認事實

- 2026-09-01 daily 在專案程序樹 peak RSS 約 388 MB 時，因全機 swap 相對啟動基線增加約 2.157 GB，超過 2 GiB 上限而停止。
- `Sample.host_free_bytes` 來自 `shutil.disk_usage`，代表磁碟空間，不代表 RAM。
- 現況 `evaluate_runtime()` 會讓 `SWAP_GROWTH_BUDGET_EXCEEDED` 單獨成為停止理由；另有連續三點 `RSS_AND_SWAP_RISING` 複合停損。
- Apple XNU 將 memory pressure 定義為 Normal=0、Warning=1、Urgent=2、Critical=3、Jetsam=4；macOS host 目前可查詢 `kern.memorystatus_vm_pressure_level`，但 sandbox 內可能因權限而不可讀。
- 近期 forecast／capacity delivery 未修改 daily ETL；2026-09-01 full-720 benchmark 發生於 daily 停止後。

## 影響面與介面

- 來源：`app/storage_safety.py`
- 政策：`docs/operations/top10-storage-policy.json`
- 回歸：`tests/test_storage_safety.py`
- public seam：`load_policy()`、`take_sample()`、`evaluate_preflight()`、`evaluate_runtime()`、`run_guarded_job()` 與 receipt `samples`。
- 呼叫端：`scripts/run_with_storage_guard.sh` → `scripts/storage_safety.py` → `app.storage_safety.run_guarded_job()`。

## 實作契約

1. 新增可測試的 macOS memory-pressure level sensor；只接受 XNU 已定義的 0..4，讀取失敗回 `None`。
2. `Sample` 與 receipt 必須保留 pressure level，讓停損可稽核。
3. Critical/Jetsam（>=3）是全機緊急停損；至少連續兩個 live sample 才停止，避免單點瞬時誤判。
4. 全機 swap 超過 job budget 不得單獨停止；只有與專案 RSS 同步持續上升時沿用既有 `RSS_AND_SWAP_RISING` 停損。
5. pressure metric 不可讀時不得假裝安全：若 swap 超標，保留 fail-closed fallback 停損，理由須能與可讀 pressure 情境區分。
6. 專案 RSS、磁碟、寫入路徑、取樣 cadence、restart denial 等既有停損不得放寬。
7. 不調高 2 GiB swap 數字；本卡修正歸因與緊急停損語意，不做無實測的 tuning。

## Red→green 驗收

- RED：低且穩定的專案 RSS、pressure 可讀且非 critical、只有全機 swap 超標時，現況錯誤停止。
- GREEN：上述情境繼續；連續 critical pressure、專案 RSS 超標、RSS+swap 連續上升、pressure 不可讀且 swap 超標時都停止。
- sensor 覆蓋正常值、格式錯誤、command failure 與非 macOS／不可讀情境。
- receipt schema／policy contract 測試更新且受影響 `tests/test_storage_safety.py` 通過。
- `git diff --check` 通過；diff 僅限本卡、來源、政策、測試與必要操作文件。

## 上線與 rollback 邊界

- 本卡不 reload launchd、不執行 production daily、不 deploy、不 push。
- 修改後仍是 `NO-GO` 上線，直到用代表性資料完成至少兩個完整 validation cycles，涵蓋 pressure sensor 可讀與 fallback 停損演練。
- rollback：回退本卡 source／policy／test diff，即恢復原本 swap 單獨停損行為。

## 完成紀錄

- 結果：`PASS`
- 驗收：`docs/evidence/REPAIR-NEW-TOP10-DAILY-MEMORY-PRESSURE-STOP-LOSS/acceptance.md`
- 代表性 cycles：`cycle-2-guard-receipt.json`、`cycle-3-guard-receipt.json`
- 驗證：affected tests `78 passed`、Python compile PASS、`git diff --check` PASS。
- 排程：未 reload／kickstart；未 external send、未 commit、未 push。
