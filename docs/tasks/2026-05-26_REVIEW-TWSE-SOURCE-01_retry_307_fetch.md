# REVIEW-TWSE-SOURCE-01 retry 307 fetch

## 五行派工卡

任務ID：REVIEW-TWSE-SOURCE-01  
卡片類型｜派工對象：Data Source Review｜Reviewer AI  
請讀：`docs/tasks/2026-05-26_TWSE-SOURCE-01_retry_307_fetch.md`、`app/data_fetcher.py`、`scripts/verify_twse_fetch_retry.py`、`logs/daily_20260525.log`  
任務目的：複查 TWSE fetch 是否只針對暫時性 307/429/503 類狀態新增 retry/backoff，且沒有新增非官方來源、沒有重跑 ETL/ranking/model  
證據路徑：`scripts/verify_twse_fetch_retry.py`、`logs/daily_20260525.log`

## Reviewer 注意

- 這張只修「單次暫時性 status 不應直接放棄該日」。
- 不宣稱已完成 TWSE 歷史全量修復；是否恢復要等下一次 ETL 或受控小範圍抓取驗證。
