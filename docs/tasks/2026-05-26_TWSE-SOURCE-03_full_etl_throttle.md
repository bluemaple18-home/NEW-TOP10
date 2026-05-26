# TWSE-SOURCE-03 full ETL throttle

## 卡片

任務ID：TWSE-SOURCE-03
卡片類型｜派工對象：Data Source / Full ETL Stability｜Codex
請讀：`app/data_fetcher.py`、`scripts/verify_twse_fetch_retry.py`、`docs/tasks/2026-05-26_TWSE-SOURCE-02_requests_fallback.md`
任務目的：讓正式三年 ETL 回補在 TWSE 官方 RWD endpoint 下穩定執行，避免全量併發或過快輪詢觸發安全頁 307，並讓 200 非 JSON 回應先走 aiohttp retry
證據路徑：`scripts/verify_twse_fetch_retry.py`、`/private/tmp/top10-etl-throttle-probe-data/clean/features.parquet`

## 邊界

- 不新增第三方資料源。
- 不放寬 requests fallback：仍只有 aiohttp retry 後的 `307` 可觸發 fallback。
- 不提交 production `data/clean`。
- 不產生 ranking。
- 不改模型、權重或門檻。

## 驗收

- 全量 ETL 抓取改成單日序列化，避免同時打太多 TWSE/TPEX request。
- 每個交易日抓取後有保守 delay；可用 `TOP10_FETCH_DAY_DELAY_SECONDS` 調整。
- `200` 但 JSON parse 失敗時，先在 aiohttp 路徑 retry，不走 requests fallback。
- regression 覆蓋 `307` fallback、`429/404/invalid payload` 不 fallback、`200 non-json -> retry -> success`。
- 最近區間 probe 最新日同時有 TWSE/TPEX rows。

## 本地驗證

- `uv run --with-requirements requirements.txt python scripts/verify_twse_fetch_retry.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile app/data_fetcher.py scripts/verify_twse_fetch_retry.py`
- `uv run --with-requirements requirements.txt python -m app.pipeline_cli run --start-date 2026-05-13 --end-date 2026-05-26 --data-dir /private/tmp/top10-etl-throttle-probe-data --artifacts-dir /private/tmp/top10-etl-throttle-probe-artifacts`

## Probe 摘要

- latest date: `2026-05-26`
- latest TWSE stocks: `1078`
- latest TPEX stocks: `875`
