# DAILY-PROD-04 latest market coverage gate

## 卡片

任務ID：DAILY-PROD-04  
卡片類型｜派工對象：Ops / Daily Data Contract｜Codex  
請讀：`scripts/run_automation.py`、`config/automation.yaml`、`scripts/verify_daily_market_coverage_gate.py`、`data/clean/features.parquet`  
任務目的：補上 daily freshness 的最新交易日市場覆蓋檢查，避免 features/events/universe 日期是新的，但最新日只抓到 TPEX 或 TWSE 單一市場仍被標成 OK  
證據路徑：`artifacts/automation_status.json`、`artifacts/daily_run_summary_YYYY-MM-DD.json`、`scripts/verify_daily_market_coverage_gate.py`

## 邊界

- 不重抓外部資料。
- 不重跑 ETL。
- 不產生 ranking。
- 不訓練模型。
- 不改模型權重或 scoring。

## 問題證據

- `data/clean/features.parquet` 最新日為 `2026-05-25`，共有 879 筆。
- 最新日市場分布：`TPEX=879`、`TWSE=0`。
- 2026-05-05 到 2026-05-25 這段最新資料皆為 `TWSE=0`。
- 原本 daily freshness 只看 `latest_date` 與 `lag_days`，因此會把單一市場資料誤判成新鮮完整。

## 驗收

- `config/automation.yaml` 明確設定 `market_coverage_enabled`、`required_market_types`、`min_latest_market_coverage_ratio`。
- `scripts/run_automation.py` 在 `_record_data_freshness()` 中寫入 `latest_market_coverage` metadata。
- 若最新日 required market 覆蓋不足，`data.freshness.*` step 必須 `FAILED`，且錯誤訊息包含 market、actual、expected、coverage ratio。
- synthetic regression 必須覆蓋：只有 TPEX 時失敗；TWSE/TPEX 都達門檻時通過。

## 本地驗證

- `uv run --with-requirements requirements.txt python scripts/verify_daily_market_coverage_gate.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile scripts/run_automation.py scripts/verify_daily_market_coverage_gate.py`
- `uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run` 目前預期失敗，原因為 `TWSE actual=0 expected=1080 ratio=0.0 < min=0.5`。
- `artifacts/automation_status.json` evidence：`mode=daily`、`dry_run=true`、`status=FAILED`、`features.parquet.latest_market_coverage` 中 `TWSE=FAILED`、`TPEX=OK`。
