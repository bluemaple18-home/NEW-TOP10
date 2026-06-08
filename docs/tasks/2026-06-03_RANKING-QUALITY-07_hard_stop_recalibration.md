# RANKING-QUALITY-07｜Hard Stop 重校準

日期：2026-06-03

## Root Question

RQ06 定義了停損執行原則：

```text
跌破 hard stop：全賣
獲利達標：分批賣
```

但 RQ06 也發現目前 ranking `trade_plan.stop_loss` 當 hard stop 會被洗出場。

本卡繼續測：

```text
1. ranking stop_loss 是否可用。
2. 固定 7/8/9/10/12/15% hard stop 是否可用。
3. 停損第 5 天後才啟動是否可用。
4. 盤中跌破 vs 收盤跌破是否可用。
```

## 本輪修正

`scripts/run_capital_aware_replay.py` 補兩個交易細節：

```text
1. 若 D+1 開盤已低於 ranking stop_loss，不進場，不能買了再立刻停損。
2. stop-trigger=close 時，出場價用收盤價，不用 stop 價。
```

這讓 stop replay 比較接近真實交易。

## 結果

production ranking / regime gross / 40D horizon / 500,000 本金：

| rule | return | max DD | trades | exits |
| --- | ---: | ---: | ---: | --- |
| no_stop | +20.94% | -6.34% | 20 | scheduled 20 |
| ranking low v2 | -23.12% | -40.42% | 59 | scheduled 7 / stop 52 |
| ranking close v2 | -32.56% | -42.99% | 49 | scheduled 8 / stop 41 |
| fixed 7% low | -7.41% | -41.82% | 50 | scheduled 8 / stop 42 |
| fixed 8% low | -14.76% | -37.64% | 50 | scheduled 9 / stop 41 |
| fixed 9% low | -19.98% | -42.88% | 42 | scheduled 8 / stop 34 |
| fixed 10% low | +4.13% | -14.17% | 44 | scheduled 14 / stop 30 |
| fixed 12% low | -15.27% | -35.53% | 35 | scheduled 12 / stop 23 |
| fixed 15% low | -20.42% | -31.07% | 29 | scheduled 11 / stop 18 |
| fixed 8% low, min stop day 5 | -11.86% | -27.36% | 41 | scheduled 10 / stop 31 |
| fixed 12% low, min stop day 5 | -10.41% | -27.10% | 35 | scheduled 11 / stop 24 |

## 判斷

```text
mechanical_hard_stop_ready = false
ranking_stop_loss_ready = false
production_ready = false
```

白話：

```text
不是「停損全賣」這個原則錯。
錯的是把單一價位當成機械出場規則。

目前模型選出的股票常有洗盤波動。
機械停損會把它們停在低點，後面反彈吃不到。
```

## 產品處置

保留：

```text
hard stop 被打到時要全賣。
```

但正式推播/頁面要先改語意：

```text
warning zone：跌破觀察區，不加碼，隔日重評估。
hard stop：劇本失效，才全賣。
```

目前 `trade_plan.stop_loss` 應降級為：

```text
風險提醒 / warning reference
```

不可宣稱：

```text
這條就是已驗證 hard stop。
```

## 下一步

RANKING-QUALITY-08 應該測「狀態式出場」，不是單點停損：

```text
1. 跌破 warning zone：不賣，只標記觀察。
2. 連續 2 天收盤弱於 warning zone：降部位或退出。
3. 跌破 hard stop 且沒有隔日收復：全賣。
4. 跌破後重新進榜，也要等冷卻結束才重買。
5. 搭配每日重新排名，讓 daily report 真正負責「續抱 / 轉弱 / 出場」。
```

這比較符合產品本質：

```text
每天報牌 + 每天更新提醒，
不是買進後用一條死價位機械砍。
```

證據：

```text
artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_production_fixed40_regime_stop_low_full_v2_2026-06-03.json
artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_production_fixed40_regime_stop_close_full_v2_2026-06-03.json
artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_regime_sl08_current_engine_2026-06-03.json
artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_regime_sl08_low_full_minstop5_2026-06-03.json
```
