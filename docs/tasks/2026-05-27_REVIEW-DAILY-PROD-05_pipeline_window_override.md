# REVIEW-DAILY-PROD-05 pipeline window override

任務ID：REVIEW-DAILY-PROD-05
卡片類型｜派工對象：Review / Ops Contract｜Reviewer
請讀：`docs/tasks/2026-05-27_DAILY-PROD-05_pipeline_window_override.md`、`scripts/run_automation.py`、`scripts/run_daily.sh`
任務目的：複查 daily ETL window override 是否只影響 `app.pipeline_cli run` 的日期參數，且不關閉市場覆蓋 gate、不允許舊 ranking fallback。
證據路徑：`artifacts/automation_status.json`、`artifacts/daily_run_summary_YYYY-MM-DD.json`

## Review 重點

- `TOP10_PIPELINE_END_DATE` 必須只傳給 `app.pipeline_cli run --end-date`。
- `data.validate` 仍必須執行，且 TWSE/TPEX 最新日覆蓋不足時必須失敗。
- `ranking.artifact` 仍必須嚴格要求 `ranking_{latest_feature_date}.csv`。
- `automation_status.json.metadata.pipeline_window` 應揭露 override。
- 不得修改模型、資料契約門檻、Clawd 正式發送 gate。
