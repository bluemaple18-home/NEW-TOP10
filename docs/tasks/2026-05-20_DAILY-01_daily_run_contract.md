# DAILY-01：每日流程 Contract 與狀態 Schema

任務ID：`DAILY-01`
卡片類型：`Ops / Daily Run Contract`
證據路徑：`artifacts/automation_status.json`、`artifacts/daily_run_summary_2026-05-21.json`、`artifacts/daily_run_summary_2026-05-23.json`

## 背景

每日流程原本會執行 ETL / validate / ranking，但狀態只是一份 generic automation status，缺少 trading-day gate、data freshness、model existence、skip reason 與 daily summary。這會讓 UI / PM 很難判斷「今天是正常跳過、資料過舊、模型缺失，還是流程真的壞了」。

## 範圍

- `scripts/run_automation.py`
  - 加入 `schema_version=daily-run-status.v1`。
  - Daily mode 寫出 `run_date`、`skip_reason`、`metadata`。
  - 支援 `TOP10_RUN_DATE=YYYY-MM-DD` 測試指定日期 gate。
  - Daily mode 會另寫 `artifacts/daily_run_summary_YYYY-MM-DD.json`。
  - `daily.enabled=false` 或週末且 `weekend_enabled=false` 時，狀態為 `SKIPPED` 並寫 skip reason。
  - Daily preflight 檢查 `models/latest_lgbm.pkl` 存在。
  - Daily preflight / ETL 後記錄 `features.parquet`、`events.parquet`、`universe.parquet` 最新日期與 lag days。
  - 資料落後超過 `daily.max_data_lag_days` 時 fail fast。
- `config/automation.yaml`
  - 補 `timezone: Asia/Taipei`。
  - 補 `daily.max_data_lag_days`。
- `scripts/run_daily.sh`
  - log 補 automation status 與 daily summary 路徑。

## 非範圍

- 不重寫 ETL / ranking。
- 不接 UI。
- 不產 Markdown 決策日報；留給 `DAILY-02`。
- 不做 post-run API / UI smoke；留給 `DAILY-03`。

## 驗證命令

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/run_automation.py
uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run
TOP10_RUN_DATE=2026-05-23 uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run
uv run --with-requirements requirements.txt python -m scripts.run_automation status --dry-run
```

## 執行紀錄

- `uv run --with-requirements requirements.txt python -m py_compile scripts/run_automation.py` 通過。
- `uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run` 通過。
- `artifacts/automation_status.json`：
  - `schema_version=daily-run-status.v1`
  - `mode=daily`
  - `status=OK`
  - `dry_run=true`
  - `run_date=2026-05-21`
  - `skip_reason=null`
  - `model.exists=OK`
  - `data.freshness.preflight=OK`
  - `data.freshness.after_etl=OK`
  - `ranking.artifact=DRY_RUN`
  - `expected_ranking_artifact=artifacts/ranking_2026-05-15.csv`
- `artifacts/daily_run_summary_2026-05-21.json` 已產出。
- `TOP10_RUN_DATE=2026-05-23 uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run` 通過：
  - `status=SKIPPED`
  - `skip_reason=non_trading_day weekday=5`
  - `artifacts/daily_run_summary_2026-05-23.json` 已產出。
- `uv run --with-requirements requirements.txt python -m scripts.run_automation status --dry-run` 通過。
- Review finding `P2 ranking.artifact 會 fallback 到最新舊檔` 已修正：
  - non-dry-run 嚴格要求 `artifacts/ranking_{latest_feature_date}.csv` 存在。
  - dry-run 僅記錄 `expected_ranking_artifact`，`ranking.artifact` step 為 `DRY_RUN`，不再把舊檔當正式 OK。
- Review finding `P2 run_daily.sh wrapper 沒有讀 status` 已修正：
  - wrapper 捕捉 `run_automation daily` exit code。
  - 永遠透過 `scripts/print_daily_status.py` 印 `status/run_date/skip_reason/summary`。
  - SKIPPED 時不假印 ranking；FAILED 時仍會印 status/summary 路徑後再以原 exit code 結束。
  - `TOP10_RUN_DATE=2026-05-23 bash scripts/run_daily.sh` 已驗證 `選股結果: 無`。
- Review finding `P2 FAILED 路徑仍可能讀到舊 automation_status.json` 已修正：
  - `run_daily.sh` 在啟動 runner 前記錄 `WRAPPER_STARTED_AT_EPOCH`。
  - `scripts/print_daily_status.py` 支援 `--min-started-at-epoch`。
  - 若 status `started_at` 早於本次 wrapper start，printer 會拒絕讀取並輸出 `本次未產生有效 status`。
  - `uv run --with-requirements requirements.txt python scripts/print_daily_status.py --status artifacts/automation_status.json --min-started-at-epoch 4102444800` 已驗證會拒絕 stale status。
  - `TOP10_RUN_DATE=2026-05-23 bash scripts/run_daily.sh` 已驗證 stale guard 後 SKIPPED 仍可讀到本次 status。
- `REVIEW-DAILY-01-FIX2` 結論：未發現阻塞問題；stale status guard 可放行。剩餘風險僅系統時間大幅倒退或 status 來自未來時間戳，一般 launchd / daily run 情境可接受。

## Review 交接

任務ID：REVIEW-DAILY-01
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-20_DAILY-01_daily_run_contract.md`、`scripts/run_automation.py`、`scripts/run_daily.sh`、`config/automation.yaml`、`docs/AUTOMATION.md`
任務目的：review 每日流程 preflight / trading-day gate / data freshness / model existence / skip reason / status schema 是否成立，且不改 ETL/ranking 本體。
證據路徑：`artifacts/automation_status.json`、`artifacts/daily_run_summary_2026-05-21.json`、`artifacts/daily_run_summary_2026-05-23.json`、`artifacts/daily01_contract_fix_2026-05-21.json`
