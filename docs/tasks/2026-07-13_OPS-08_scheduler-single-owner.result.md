# OPS-08 驗收結果

## 通過

- `uv run --group dev python -m unittest tests/test_scheduler_ownership.py -v`：8 tests OK。
- `uv run python scripts/verify_scheduler_ownership.py --repo-only`：GO；repo plist 指向 `scripts/run_daily_publish.sh`。
- `bash -n scripts/setup_cron.sh`、`git diff --check`：通過。
- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`、`scripts/com.new-top10.daily.plist` 的 SHA-256 維持原值。

## 未驗證與原因

- 未執行 crontab write 或 launchctl mutation，遵守本卡邊界。
- `verify_daily_publish_workflow.py` 因此 worktree 沒有 `artifacts/automation_status.json` 與同日 daily artifacts 而失敗；不是 scheduler 契約失敗，待有完整 daily artifact 的環境重跑。
