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

## 殘餘風險

本次未操作自然 Fog run、LaunchAgent 或 production runtime；新的排程與 Nice 設定待 Mainline 在受控 activation 驗證。
