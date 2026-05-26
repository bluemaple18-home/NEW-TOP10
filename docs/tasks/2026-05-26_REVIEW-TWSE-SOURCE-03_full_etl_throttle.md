# REVIEW-TWSE-SOURCE-03 full ETL throttle

## 五行派工卡

任務ID：REVIEW-TWSE-SOURCE-03
卡片類型｜派工對象：Data Source Review｜Reviewer AI
請讀：`docs/tasks/2026-05-26_TWSE-SOURCE-03_full_etl_throttle.md`、`app/data_fetcher.py`、`scripts/verify_twse_fetch_retry.py`
任務目的：複查全量 ETL 節流是否只降低抓取速度與補 non-json retry，沒有新增資料源、沒有放寬 307-only requests fallback、沒有改 ranking/model/data contract
證據路徑：`scripts/verify_twse_fetch_retry.py`、`/private/tmp/top10-etl-throttle-probe-data/clean/features.parquet`

## Reviewer 注意

- 本卡不要求本機先完成三年全量 ETL；主機可自行重抓資料。
- 請確認 `TOP10_FETCH_DAY_DELAY_SECONDS` 只是速度調整，不影響資料契約。
- 請確認 429/503 仍不會進 requests fallback。
