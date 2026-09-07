# REPAIR-NEW-TOP10-FOG-RESOURCE-BUDGET-01 驗證紀錄

## RED

`bash tests/test_fog_resource_budget.sh` 在修改前失敗：

```text
Print: Entry, ":Nice", Does Not Exist
```

## GREEN

- plist 已驗證為 `ProcessType=Background`、`LowPriorityIO=true`、`Nice=10`、`StartInterval=3600`。
- Fog wrapper 預設傳入 replay drain `6` 筆、`1` batch、`1800` 秒，三個 `TOP10_REPLAY_DRAIN_*` 環境變數仍可覆寫。
- worker CLI 的預設與環境覆寫由 `tests/test_fog_resource_budget.sh` 的 Python 斷言驗證。

## 驗證命令

```text
bash tests/test_fog_resource_budget.sh
.venv/bin/python -m unittest tests.test_representative_replay_drain_worker
.venv/bin/python -m unittest tests.test_fog_storage_validation
.venv/bin/python -m unittest tests.test_storage_safety
bash tests/test_fog_runtime_time_wiring.sh
bash tests/test_fog_signal_teardown.sh
bash tests/test_fog_research_retry_circuit.sh
bash -n scripts/run_fog_research_worker.sh scripts/setup_launchd.sh
git diff --check
```

所有列出的命令皆於隔離開發 worktree 成功完成。

## Repair 1：deadline 強制執行

- RED：新增超時測試時，`run_command()` 不接受 timeout 參數，且沒有 timeout return code。
- GREEN：每個 replay、map refresh、verification 與 linkage 子命令收到剩餘 deadline；逾時建立獨立 process group 的子命令會收到終止訊號，超過 2 秒 grace 才強制結束。
- `tests.test_representative_replay_drain_worker` 驗證 0.1 秒 deadline 在 3 秒內返回、child PID 已結束，並驗證 receipt 為 `status=TIMED_OUT`、`stop_reason=command_timeout`、command status 為 `TIMED_OUT`。

## Repair 2：外層群組 containment

- RED：`start_new_session=True` 使 direct child 的 PGID 不等於 worker PGID；模擬外層 Storage Guard 終止後，descendant 仍存活。
- GREEN：子命令保留呼叫者既有 PGID/session。內層 timeout 只依 direct child 的即時 process tree 依序終止 descendants 與 direct child，不對呼叫者群組發送訊號。
- `tests.test_representative_replay_drain_worker` 驗證內層 deadline 與外層 group termination 均不留 descendant，且 timeout receipt 語意不變。

## 殘餘風險

本次未操作自然 Fog run、LaunchAgent 或 production runtime；新的排程與 Nice 設定待 Mainline 在受控 activation 驗證。
