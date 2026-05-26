# TWSE-SOURCE-02 requests fallback for 307 security page

## 卡片

任務ID：TWSE-SOURCE-02
卡片類型｜派工對象：Data Source / TWSE Fetch｜Codex
請讀：`app/data_fetcher.py`、`scripts/verify_twse_fetch_retry.py`、`docs/tasks/2026-05-26_TWSE-SOURCE-01_retry_307_fetch.md`
任務目的：當 TWSE 官方 RWD endpoint 透過 aiohttp retry 後仍回 `307` 安全頁時，改用同一官方 endpoint 的 `requests` fallback，恢復最新交易日 TWSE rows，避免 daily market coverage gate 長期卡住
證據路徑：`scripts/verify_twse_fetch_retry.py`、`artifacts/twse_source_02_probe_2026-05-26.json`

## 邊界

- 只使用 TWSE 官方 `https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX`。
- 不新增第三方資料源。
- 不重跑正式 ETL。
- 不產生 ranking。
- 不改模型、feature 權重或監控門檻。

## 問題證據

- TWSE-SOURCE-01 的 aiohttp retry 已可處理暫時性 `307 -> 200`。
- 現場真實 probe 仍遇到 TWSE 安全頁 `307`，而同一 URL 用 `requests` 可回 `200` JSON。
- DAILY-PROD-04 已正確阻擋 TWSE coverage=0 的 daily ranking；本卡目標是修復資料取得路徑，讓下一次 ETL 能通過 coverage gate。

## 驗收

- aiohttp retry 後仍沒有 JSON data 時，才啟動 `requests` fallback。
- fallback 必須使用相同 TWSE 官方 endpoint、相同參數與相同 parser。
- fallback 成功時必須在 source log 標出 method，方便後續追查。
- synthetic regression 必須覆蓋 aiohttp 四次 `307` 後由 `requests` 成功解析 dataframe。
- 小範圍單日 probe 必須看到 `TWSE` 與 `TPEX` 都有 rows。

## 本地驗證

- `uv run --with-requirements requirements.txt python scripts/verify_twse_fetch_retry.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile app/data_fetcher.py scripts/verify_twse_fetch_retry.py`

## 現場 probe 摘要

- `features_shape`: `[1956, 96]`
- `market_counts`: `TWSE=1077`、`TPEX=879`
- 單日 probe 的 `universe` 為 0 是預期結果，因為 rolling/listing filters 需要歷史區間。
