# REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01 Worker card

目標：依 `docs/tasks/2026-09-07_REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01.md`，以 TDD 最小修復 Fog 對 `artifacts/external_review` production shared subtree 的容量納管。

限制：只可修改 `docs/operations/top10-storage-policy.json`、`docs/operations/top10-storage-safety.md`、`tests/test_storage_safety.py` 與本卡 result/status evidence；禁止修改 production Python/shell/plist，禁止新增 lock/ledger/scheduler，禁止清 marker、deploy、kickstart、commit、push。

RED/GREEN：先新增一個行為測試，重現 sibling job 對 `artifacts/external_review` 的新增與刪除目前被 Fog 判成 registered-unmetered；確認 RED 後，只把 exact subtree 加入 Fog `meter_paths`。GREEN 必須同時證明 changed paths 不再 unmetered、bytes/files 被 `measure_paths` 計入、`source.py` 等未知寫入仍 fail closed、ceilings/launch_verified/其他 job policy 不變。

驗證：跑新增 test、Storage Guard affected suite、Fog natural acceptance suite、policy load、`git diff --check`。回報 RED 與 GREEN 指令／輸出、changed files與 residual risk；不得自行宣告 production fixed。

若 exact subtree 仍不足、需要擴到整個 artifacts、改 code/plist 或新增並行控制面，立即停止並回報 `BLOCKED_SCOPE_EXPANSION`。
