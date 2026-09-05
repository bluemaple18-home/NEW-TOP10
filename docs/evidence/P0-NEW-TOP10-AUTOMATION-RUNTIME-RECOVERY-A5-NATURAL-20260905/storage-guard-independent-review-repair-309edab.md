# Storage Guard 獨立審查修復紀錄

- 被審 SHA：`a2ab4fd35949769680f621608bc0121c99dd38dc`
- 修復 commit：`309edab892e5e7fe60841627527b4d0b2e81dd89`
- base：`fb7022e335c56d0505e9045ba65a8e792eda75ae`
- 範圍：Storage Guard、wrapper、CLI 與回歸測試；未執行 deploy、launchctl 或 production mutation。

## 獨立 Reviewer verdict

兩條 Reviewer 都使用 clean context、獨立 worktree、固定 SHA、唯讀限制，且完整執行到 verdict：

- Reviewer A：`01a06f85-74e7-7772-a1ec-b45bbad22f27`，`VERDICT: NO_GO`。
  - P1：denial marker 持續寫失敗時，下一次 invocation 只看 marker，仍可能啟動 child。
- Reviewer B：`01a06f85-81ec-7871-aeec-ee30cf93abe1`，`VERDICT: NO_GO`。
  - P1：重複 `invocation_id` 在 child 已執行後才被 archive collision 拒絕。
  - P1：marker 成功、root receipt 尚未寫入時死亡，會遺失原始 forensic payload。
  - P1：caller 可將 manual 執行標為 `natural`，造成 natural-cycle metadata 不可信。

## 修復

1. 每個 invocation 在取得 job lock 後、preflight／reclaim／child spawn 前，以 `O_EXCL` 建立 claim；同一 ID 的後續執行在 child 前回 `75`。
2. denial marker 內嵌 hash-bound 完整 STOPPED receipt 與 claim token。若 marker 已落盤但 archive 仍是 claim，下一輪可驗證、還原 archive/latest，再 fail closed。
3. marker 連續寫失敗時，另寫 immutable `marker-write-failed` receipt，latest 明列 `restart_denied_marker_persisted=false`；下一輪即使 marker 不存在也會在 child 前拒絕。
4. wrapper 不再接受 `TOP10_STORAGE_TRIGGER_TYPE` 自述；一般 CLI 的 `natural` 在 parent 非 PID 1 時降為 `manual`。由於 natural launchd fire 與 manual kickstart 對 child 都可能是 PID 1，guard 明列 `natural_trigger_verified=false`，並固定 `consecutive_natural_guard_cycles=0`；完整 A5 natural acceptance 必須由外部 cadence verifier 補足。

## 驗證

- RED：四個聚焦 regression 在修復前分別證明 missing helper／marker crash／duplicate child side effect／marker persistent failure。
- GREEN：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_storage_safety.py tests/test_automation_runtime_activation.py tests/test_fog_runtime_health.py`
  - 結果：`149 passed, 38 subtests passed in 17.63s`
  - `bash -n scripts/run_with_storage_guard.sh`：PASS
  - `jq empty docs/operations/top10-storage-policy.json`：PASS
  - `git diff --check`：PASS

## 尚未滿足

- 本紀錄只證明 candidate code/test；不是 production GO。
- production runtime 仍是舊 SHA，GUI launchd domain 仍需額外授權處理；本輪未啟用 A4。
- A5 仍須等實際自然 cadence、正確 run-date artifact、publish/provider terminal result 與連續兩次 accepted cycle。
