---
id: REPAIR-NEW-TOP10-FOG-PROCESS-RSS-ATTRIBUTION
status: IMPLEMENTED_LOCAL_VERIFIED / EXTERNAL_ATTRIBUTION_PENDING_AUTHORIZATION
type: runtime-instrumentation-repair
risk: high
baseline: 5a2acfe2e0905a1b9175d64a0b2a7a4c2a046316
---

# Fog Process RSS Attribution Repair

👉 [假設與目標確認] 目標：讓每筆 storage-safety live sample 同時保存 process tree 中各 PID 的 RSS 與 command，供下一輪定位 3.39 GiB 主峰；不碰 2 GiB 上限、workload 內容、模型、排程、外接碟試跑或 production；以可重現 RED→GREEN 單測、受影響測試與 `git diff --check` 判定。

## Evidence baseline

- R12／R13／R14 連續三次以 `PROCESS_TREE_RSS_BUDGET_EXCEEDED` 停止，peak RSS 分別為 `3,688,054,784`、`3,697,852,416`、`3,390,472,192` bytes。
- R14 的 aggregate sample 只有 process-tree `rss_bytes`，沒有 PID、RSS、command，無法判斷最大 contributor。
- stop rule 已命中；本卡不得執行第四次 external validation，只補可驗證的 attribution seam。

## Strict fact gate

- 受影響檔案：`app/storage_safety.py`、`tests/test_storage_safety.py`；本卡與父卡 history。
- Public／observable seam：`take_sample()` 產生 `Sample`；`_receipt_payload()` 透過 `Sample.to_dict()` 寫入 guard receipt 的 `samples[]`。
- 現有資料契約：每筆 sample 含 timestamp、project bytes/files、host bytes、aggregate RSS、swap、phase、memory pressure；新增欄位必須保持既有 aggregate RSS 與所有既有 caller 相容。
- 使用者邊界：接續目前專案唯一安全續作；不重跑已連續失敗三次的高記憶體 workload。

## Falsifiable hypotheses

1. 若不可歸因的原因是 `ps` 只解析 pid/ppid/rss，則同一次取樣加入 command 並保留 tree rows 後，receipt sample 應能列出 root 與 descendants，且各列 RSS 加總等於既有 `rss_bytes`。
2. 若 command 解析會因空白破壞欄位，則使用固定四欄 split 的測試應抓到 command 被截斷；修後完整 command 應保留。
3. 若新增欄位破壞既有 synthetic `Sample(...)` caller，現有 storage safety suite 會失敗；欄位需以相容預設值加入。

## Validation plan

1. 新增 process tree attribution observable test，先確認現況 RED，再做最小修復並轉 GREEN。
2. 跑 `tests/test_storage_safety.py` 與 `tests/test_external_fog_revalidation.py`，確認 receipt 與 harness 回歸全綠。
3. 跑 debug-marker scan 與 `git diff --check`；不執行 external representative cycle。

## History

- 2026-09-02：CodeGraph indexed HEAD `5a2acfe2e0905a1b9175d64a0b2a7a4c2a046316`，task-semantic query 指向 `Sample`、`take_sample()`、`_receipt_payload()` 與 storage safety tests。
- 2026-09-02：RED 已由 `uv run pytest tests/test_storage_safety.py::test_take_sample_attributes_process_tree_rss_by_pid_and_command -q` 重現；既有 `Sample` 缺 `process_rss_attribution`，無法由 aggregate RSS 定位 contributor。
- 2026-09-02：最小修復讓同一次 `ps` snapshot 產生 aggregate RSS 與 process-level attribution，保留既有 `process_tree_rss_bytes()` 介面與 synthetic `Sample(...)` 相容性；單測 GREEN。
- 2026-09-02：受影響回歸 `72 passed, 31 subtests passed`；未執行 external representative cycle。下一步需在明確資源授權後跑一次 attribution cycle，再依最大 contributor 另開單一修復。
