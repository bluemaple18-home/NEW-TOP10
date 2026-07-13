# OPS-08｜Scheduler 單一所有權防呆

- status: ready
- priority: P0
- owner: Codex worktree
- task thickness: strict

## 目標

消除 `setup_cron.sh` 與正式 launchd 可能同時啟動 daily 的雙排程風險。正式 owner 保持 `com.new-top10.daily` → `scripts/run_daily_publish.sh`；本卡不得 reload 或修改本機排程。

## 依賴與 frontier

- 依賴：正式 daily publish contract 已存在且本輪 hash 驗證通過。
- blocker：無。
- frontier：可立即開工。

## 可改檔案

- `scripts/setup_cron.sh`
- `scripts/verify_scheduler_ownership.py`（可新增）
- `tests/test_scheduler_ownership.py`（可新增）
- `docs/AUTOMATION.md`
- 本卡 result/status

## 不可改

- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`
- `scripts/com.new-top10.daily.plist` 與已安裝 plist
- `config/automation.yaml`
- 不得執行 `crontab` write、`launchctl load/unload/reload`

## 實作契約

1. `setup_cron.sh` 預設 fail-closed，不得再互動後直接新增 TOP10 daily cron。
2. 只有明確 `TOP10_ALLOW_LEGACY_CRON=1` 才能進入舊安裝流程，且必須顯示 launchd 單一 owner 警告。
3. verifier 對文字 fixture／注入內容檢查：launchd only=GO、cron only=warning、同時存在=NO-GO、都不存在=NO-GO。
4. verifier 預設唯讀；支援 `--repo-only`，CI 不依賴實機 launchctl/crontab。
5. 文件移除「cron 備選」的正常路徑描述，明示只作封存相容入口。

## 驗收

- shell syntax 通過。
- fixture tests 覆蓋四種 owner 狀態與 override gate。
- `verify_daily_publish_workflow.py` 仍通過。
- live 三個控制檔 hash 不變；沒有實機排程 mutation。
- `git diff --check` 通過。

## 回報

列出測試與未驗證實機狀態原因；建立單一 atomic commit，不 merge、不 push、不 reload。
