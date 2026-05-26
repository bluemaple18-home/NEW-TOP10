# REVIEW-DAILY-PROD-04 latest market coverage gate

## 五行派工卡

任務ID：REVIEW-DAILY-PROD-04  
卡片類型｜派工對象：Ops / Daily Data Contract Review｜Reviewer AI  
請讀：`docs/tasks/2026-05-26_DAILY-PROD-04_latest_market_coverage_gate.md`、`scripts/run_automation.py`、`config/automation.yaml`、`scripts/verify_daily_market_coverage_gate.py`、`artifacts/automation_status.json`  
任務目的：複查 daily freshness 是否已補最新交易日 TWSE/TPEX 市場覆蓋 gate，且目前真實資料只有 TPEX 時會 fail，不再產生正式 ranking  
證據路徑：`artifacts/automation_status.json`、`docs/tasks/2026-05-26_DAILY-PROD-04_latest_market_coverage_gate.md`

## Reviewer 注意

- 這張不修 TWSE 抓取來源，只修 daily contract，避免 incomplete latest data 被當 OK。
- 目前真實 dry-run 應該 `FAILED`；這是正確驗收，不是退化。
- synthetic regression 必須同時驗「只有 TPEX fail」與「TWSE/TPEX 都達門檻 pass」。
