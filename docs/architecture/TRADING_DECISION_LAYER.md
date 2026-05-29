# Trading Decision Layer

## 目標

這一層不是重做模型，而是把既有模型、規則分數、交易計畫、回測摘要收斂成一致的操盤決策管線。

## 已保留

- `LabelGenerator`：保留 D+1 open 進場、D+N close 出場、10 日 5% 目標。
- `LightGBMTrainer`：保留 Optuna、TimeSeriesSplit、Isotonic calibration、SHAP。
- `StockRanker`：保留模型機率、規則分數、SHAP 推薦理由。
- `RiskFilter`：保留處置股、上市天數、流動性、價格過濾。
- `agent_b_vectorbt.py`：保留 vectorbt 原型，不併入 UI request path。

## 新增收斂層

### `TradePlanService`

統一 entry、stop、target、position hint。原本 ranking 與 report 各算一套交易計畫，現在集中在 `app/trading/trade_plan.py`。

### `MarketRegimeService`

先用既有 universe breadth 判斷市場狀態，不額外依賴加權指數資料：

- `breadth_ma20`：站上 MA20 的股票比例。
- `breakout_ratio`：突破訊號比例。
- `avg_rsi`：市場平均 RSI。

輸出 `RISK_ON / NEUTRAL / RISK_OFF` 與 `risk_multiplier`。

### `RankingPolicy`

保留原本 `final_score`，額外產生可拆解的 `risk_adjusted_score`：

```text
risk_adjusted_score =
  prediction_score
  + setup_score
  + quality_score
  - risk_penalty
```

- `prediction_score`：模型勝率或 raw probability。
- `setup_score`：技術型態與事件訊號的規則分數。
- `quality_score`：基本面品質與流動性品質。
- `risk_penalty`：市場狀態、流動性不足與風險訊號扣分。

## 回測隔離

回測摘要仍走 `app/backtesting` 與 `app/services/backtest_service.py`，只讀既有 markdown/png artifacts。

UI/API 只讀：

- `/api/backtests/summary`

不在頁面載入時同步觸發回測。

## 決策品質摘要

`scripts/build_decision_quality.py` 產出 `artifacts/decision_quality_YYYY-MM-DD.json`，把每日 Top10 的決策輔助證據收斂成單一 read-only artifact：

- 入榜天數：讀 `candidate_persistence_YYYY-MM-DD.json`。
- 歷史回測表現：讀 production replay，且只納入 `ranking_date < 目標 ranking_date` 的成熟紀錄。
- Portfolio replay 風險：讀 overlap portfolio replay summary 與風險旗標。
- Market context：daily automation 會先產同日期 `market_context_YYYY-MM-DD.json`；摘要預設只讀同日期 artifact，若手動指定不同日期 artifact，會標記日期不一致。
- Reference annotation：只讀本地 `data/reference` mapping，補中性產業 / sector / market 標籤；不觸發外部抓取，也不作為模型或 ranking score 訊號。

此摘要只複製 ranking score 作為背景欄位，不重算、不覆寫、不回饋到 ranking score。

## 下一步

- 把 `TradePlanService` 的 stop/target 加入更多真實交易欄位，例如 ATR、前低、壓力區。
- 將 `risk_adjusted_score` 的因子權重做離線回測，不用人工拍腦袋固定。
- 將 `agent_b_backtest.py` 與 `agent_b_vectorbt.py` 收斂成離線 backtesting job，但仍保持與 UI 分離。
