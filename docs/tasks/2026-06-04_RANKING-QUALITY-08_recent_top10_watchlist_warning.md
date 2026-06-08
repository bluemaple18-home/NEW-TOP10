# RANKING-QUALITY-08 近 7 日 Top10 Watchlist 風險提醒

## 目標

把 Phase 1 的「每日推薦」和「非個人化風險提醒」拆開。

這張卡只處理近 7 個 ranking 日曾進 Top10 的股票，整理哪些仍可觀察、哪些動能降溫、哪些轉弱風險升高。

## 不做

- 不接 Clawd。
- 不改推播頻道。
- 不處理個人持倉。
- 不假設使用者買進日、買進價格或張數。
- 不改 production ranking、risk_adjusted_score 或模型。
- 不把提醒寫成個人交易指令。

## 方法

1. 讀取 `artifacts/ranking_*.csv` 最近 7 個 ranking 日。
2. 取每份 Top10，建立近榜股票聯集。
3. 用 `data/clean/features.parquet` 的目標日前最新資料補價格與均線狀態。
4. 依照是否掉出最新 Top10、排名是否退步、是否跌破短線/月線、是否出現長上影、ranking 風險扣分，產生三種等級：
   - `WATCH`
   - `WEAKENING`
   - `RISK_ALERT`

## 驗收

- `scripts/build_recent_top10_watchlist_warning.py` 可產出 JSON 與 Markdown。
- `scripts/verify_recent_top10_watchlist_warning.py` 驗證通過。
- artifact contract 明確標記 research-only、非個人化、不推播、不改 ranking、不改模型。
- 提醒文字不得出現直接交易指令。

## 本輪結果

已完成。

- 目標日期：`2026-06-03`
- ranking window：`2026-05-26` ~ `2026-06-03`，共 7 個 ranking 日
- watchlist 聯集：61 檔
- 最新 Top10 仍在榜：10 檔
- 近榜後掉出最新 Top10：51 檔
- 分級：
  - `WATCH`: 9
  - `WEAKENING`: 49
  - `RISK_ALERT`: 3

產物：

- `artifacts/model_experiments/recent_top10_watchlist_warning_2026-06-03.json`
- `artifacts/model_experiments/recent_top10_watchlist_warning_2026-06-03.md`

驗證：

- `python3 -m py_compile scripts/build_recent_top10_watchlist_warning.py scripts/verify_recent_top10_watchlist_warning.py`
- `uv run --with-requirements requirements.txt python scripts/build_recent_top10_watchlist_warning.py --watchlist-ranking-days 7 --top-n 10`
- `uv run --with-requirements requirements.txt python scripts/verify_recent_top10_watchlist_warning.py --expected-days 7 --min-items 10`

結論：RQ08 可作為 Phase 1 的「推薦後觀察清單」資料層，但不是個人持倉提醒，也不是推播分頻實作。
