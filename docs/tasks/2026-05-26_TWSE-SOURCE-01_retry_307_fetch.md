# TWSE-SOURCE-01 retry 307 fetch

## 卡片

任務ID：TWSE-SOURCE-01  
卡片類型｜派工對象：Data Source / TWSE Fetch｜Codex  
請讀：`app/data_fetcher.py`、`scripts/verify_twse_fetch_retry.py`、`artifacts/twse_history_source_gate.md`、`logs/daily_20260525.log`  
任務目的：處理全量 ETL 期間 TWSE RWD API 偶發 `307` / rate-limit 類暫時狀態，避免單次 307 直接放棄該交易日造成最新日只剩 TPEX  
證據路徑：`scripts/verify_twse_fetch_retry.py`、`logs/daily_20260525.log`

## 邊界

- 不新增非官方資料源。
- 不重跑全量 ETL。
- 不補舊專案資料。
- 不產生 ranking。
- 不改模型或權重。

## 問題證據

- `logs/daily_20260525.log` 顯示全量 ETL 期間大量 `TWSE 連線失敗 (...): Status 307`。
- 現場單獨 probe `AsyncTWSEFetcher.fetch_daily_quotes("20260525")` 可回傳 TWSE rows，因此 parser 可用；問題偏向全量併發期間的暫時性 307 / CDN 限流。
- DAILY-PROD-04 已阻止這類不完整資料進入 ranking；本卡只補 fetch retry，讓下一次 ETL 有機會自行恢復。

## 驗收

- TWSE fetch 對 `301/302/303/307/308/429/503` 類暫時狀態 retry。
- retry 成功後仍走既有 parser，不改欄位契約。
- synthetic regression 必須驗證第一次 307、第二次 200 時能成功產生 dataframe。

## 本地驗證

- `uv run --with-requirements requirements.txt python scripts/verify_twse_fetch_retry.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile app/data_fetcher.py scripts/verify_twse_fetch_retry.py`
