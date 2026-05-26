# REVIEW-TWSE-SOURCE-02 requests fallback for 307 security page

## 五行派工卡

任務ID：REVIEW-TWSE-SOURCE-02
卡片類型｜派工對象：Data Source Review｜Reviewer AI
請讀：`docs/tasks/2026-05-26_TWSE-SOURCE-02_requests_fallback.md`、`app/data_fetcher.py`、`scripts/verify_twse_fetch_retry.py`、`artifacts/twse_source_02_probe_2026-05-26.json`
任務目的：複查 TWSE requests fallback 是否只在 aiohttp retry 仍失敗後啟動，且仍使用同一官方 RWD endpoint、同一 parser，沒有新增第三方來源、沒有改 ETL/ranking/model contract
證據路徑：`scripts/verify_twse_fetch_retry.py`、`artifacts/twse_source_02_probe_2026-05-26.json`

## Reviewer 注意

- 這張不是正式全量 ETL rerun，也不宣告 daily 已恢復。
- probe 證據只證明 2026-05-25 單日 source fetch 可同時取得 TWSE/TPEX rows。
- 請特別檢查 fallback 是否可能吞掉非暫時性錯誤，或在 parser 失敗時錯誤地把壞資料當成功。
