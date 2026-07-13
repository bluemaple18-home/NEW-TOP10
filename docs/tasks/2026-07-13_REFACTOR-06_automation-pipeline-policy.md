# REFACTOR-06｜Automation Pipeline Policy 抽離

- status: ready
- priority: P1
- owner: Codex worktree
- task thickness: strict

## 目標

從 `scripts/run_automation.py` 抽離每日 ETL command、日期窗口與 resource profile 的純政策邏輯，建立可單測的 deterministic seam；不得改變 daily／monitor／retrain 的既有命令、步驟順序或失敗語意。

## 依賴與 frontier

- 依賴：REFACTOR-01、正式 real-data shadow 與 runtime promotion 已完成。
- blocker：無。
- frontier：可立即開工；不得切換 daily v2 為 live。

## 可改檔案

- `scripts/run_automation.py`
- `app/automation/__init__.py`（可新增）
- `app/automation/pipeline_policy.py`（可新增）
- `scripts/verify_daily_pipeline_window_override.py`
- `scripts/verify_resource_guard.py`
- `tests/test_automation_pipeline_policy.py`（可新增）
- 本卡 result/status

## 不可改

- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`
- `config/automation.yaml`、plist、通知設定
- ranking、model、data artifacts
- daily v2 production switch

## 實作契約

1. 抽離範圍限 `_pipeline_run_command`、pipeline window override/default 與 resource-profile 判定所需的純邏輯。
2. 新 API 輸入為明確 config/env/date 值，輸出為不可變或可比較的 policy result；不得直接讀寫 production artifacts。
3. `AutomationRunner` 保留相容 method，僅委派給 policy；既有 patch/mock tests 不得失效。
4. 先以 table-driven tests 鎖定 explicit window、default lookback、local_safe guard、host_full、invalid profile。
5. dry-run 的 command sequence 與重構前 golden contract 一致。

## 驗收

- 目標 policy 有獨立測試，沒有 subprocess／filesystem side effect。
- `verify_daily_pipeline_window_override.py`、`verify_resource_guard.py`、automation status contract 全通過。
- `python -m scripts.run_automation daily --dry-run` 只在隔離 temp/artifact 路徑或 mock 下驗證，不跑正式 ETL。
- `git diff --check` 通過；live 控制檔 hash 不變。

## 回報

列出 golden command 證據、測試、未驗證原因與剩餘風險；建立單一 atomic commit，不 merge、不 push、不 reload。
