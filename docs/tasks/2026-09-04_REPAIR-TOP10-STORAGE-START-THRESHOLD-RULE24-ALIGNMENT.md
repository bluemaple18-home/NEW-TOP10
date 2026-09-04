# Repair：TOP10 啟動容量門檻對齊 Rule 24

## 目標

移除 TOP10 過期的 `max(30 GiB, 15%)` 啟動門檻，改為現行全域 Rule 24 唯一允許的主機總容量 `10%` 基線。

## 已確認缺口

- `docs/operations/top10-storage-policy.json` 仍設定 `start_min_free_bytes=30 GiB`、`start_min_free_percent=0.15`。
- `app/storage_safety.py` 要求啟動門檻嚴格高於 runtime 保留線，無法表達現行 Rule 24。
- 現行 AI Core Rule 24 要求啟動前只採用 `10%`，並禁止較高固定 GiB 或 TOP10 15% 特例。

## 範圍

- 修改 storage policy 的啟動門檻。
- 修改 policy loader 的 canonical Rule 24 驗證。
- 補充 synthetic preflight 與 policy drift 測試。
- 更新目前操作手冊的門檻說明。

## 不在範圍

- 不修改 runtime `max(20 GiB, 10%)` 停損。
- 不修改逐 job 容量、檔案數、增長率、retention、reclaim 或 `launch_verified`。
- 不修改歷史 task/evidence。
- 不啟用 launchd、不清 marker、不切 runtime、不碰 production。

## 驗收

1. canonical policy 使用 `start_min_free_bytes=0`、`start_min_free_percent=0.10`。
2. loader 對任何非零固定啟動 bytes 或非 10% 的啟動比例 fail closed。
3. synthetic host 在可用空間高於 10% 但低於舊 15% 時，preflight 不再回 `HOST_START_FREE_SPACE_BELOW_THRESHOLD`。
4. 可用空間低於 10% 時仍回同一 fail-closed reason。
5. runtime 保留線及其他 stop-loss 行為不變。
6. targeted test、storage safety regression 與 `git diff --check` 全部通過。

## 回復方式

只需回復本卡列出的 policy、loader、測試與操作手冊 diff；不涉及外部狀態 rollback。

## 狀態

`VERIFIED_NOT_ACTIVATED`

## 驗證證據

- RED：修改前 targeted 測試為 `10 failed, 1 passed`，證明舊 policy 仍以 15% 拒絕高於 10% 的主機空間。
- GREEN：targeted 測試 `3 passed, 11 subtests passed`。
- Storage safety regression：`78 passed, 37 subtests passed`。
- Daily／Fog／external revalidation／runtime checkout：`25 passed`。
- Activation regression 單檔：`58 passed`；同一批混跑曾出現 5 個 signal-state 隔離失敗，5 案於全新 process 重跑均通過，未改 activation 範圍。
- 正式唯讀 measure：`daily`、`external-review-preflight`、`fog-research-worker` 均為 `PASS`，reasons 為空。
- `git diff --check`：PASS。
- production／launchd／runtime checkout／marker mutation：0。
