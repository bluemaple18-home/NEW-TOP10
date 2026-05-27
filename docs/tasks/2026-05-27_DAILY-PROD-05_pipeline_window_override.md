# DAILY-PROD-05 pipeline window override

任務ID：DAILY-PROD-05
卡片類型｜派工對象：Ops / Daily Run Contract｜Codex
請讀：`scripts/run_automation.py`、`scripts/run_daily.sh`、`app/pipeline_cli.py`、`config/automation.yaml`
任務目的：讓正式 daily ETL 支援明確的 `TOP10_PIPELINE_START_DATE` / `TOP10_PIPELINE_END_DATE` override，當最新日單一市場尚未完整時，可指定上一個完整交易日完成 daily 閉環；不得關閉市場覆蓋 gate，不得沿用舊 ranking。
證據路徑：`artifacts/automation_status.json`、`artifacts/daily_run_summary_YYYY-MM-DD.json`

## 背景

主機完整 ETL 跑到 `2026-05-27` 後，`features.parquet` 最新日出現 `TWSE=857`、`TPEX=0`。`app.pipeline_cli validate` 正確失敗：

`TPEX actual=0 expected=888 ratio=0.0 < min=0.5`

這代表最新日市場資料不完整，不能產生正式 ranking。但 `bash scripts/run_daily.sh` 會重新執行 `python -m app.pipeline_cli run`，預設 end date 是當天；若只是先手動跑 `--end-date 2026-05-26`，daily wrapper 仍會再把 `2026-05-27` 抓回來。

## 實作

- `scripts/run_automation.py` 的 daily ETL command 改由 `_pipeline_run_command()` 建立。
- 支援環境變數：
  - `TOP10_PIPELINE_START_DATE=YYYY-MM-DD`
  - `TOP10_PIPELINE_END_DATE=YYYY-MM-DD`
- 有設定 override 時，寫入 `automation_status.json.metadata.pipeline_window`。
- `scripts/run_daily.sh` 不需改動，環境變數會自然傳入 runner。

## 邊界

- 不修改 `config/automation.yaml` 的 `market_coverage_enabled`。
- 不降低 `min_latest_market_coverage_ratio`。
- 不跳過 `data.validate`。
- 不改 ranking/model/Clawd 發送 gate。

## 驗收

- `TOP10_PIPELINE_END_DATE=2026-05-26 bash scripts/run_daily.sh` 時，daily ETL command 必須包含 `--end-date 2026-05-26`。
- 若 clean 最新日是 `2026-05-26` 且 TWSE/TPEX 覆蓋達標，daily 才可繼續產生 `ranking_2026-05-26.csv`、daily report 與 Clawd payload。
- 若指定日期仍缺任一市場，validate 必須照常失敗。
