# RANKING-QUALITY-06｜停損執行規則與推播停損價回測

日期：2026-06-03

## Root Question

前一輪 capital-aware replay 是固定抱 20/40 天，沒有模擬使用者照推播「跌破就收手」。

本卡補上兩件事：

```text
1. 停損執行機制：跌破停損預設全賣，不做半賣。
2. 回測實際推播 stop_loss：用 ranking trade_plan 裡的 stop_loss 當出場價。
```

## 機制決策

```text
停損 = thesis broken，所以預設全賣。
停利 = thesis may continue，所以可以分批。
```

白話：

```text
跌破停損不是「先賣一點看看」。
對小白來說，這是原本推薦理由失效，應該先離場。
```

## 本輪實作

新增/更新：

```text
scripts/research_liquidity_quality_candidate_universe_shadow.py
scripts/run_backtest_replay.py
scripts/run_capital_aware_replay.py
```

重點：

```text
shadow ranking CSV 現在會輸出 entry_low / entry_high / stop_loss / target_price / risk_reward。
capital-aware replay 支援 --stop-loss-source ranking。
capital-aware replay 支援 --stop-trigger low / close。
```

## 半年 stop_loss coverage

```text
production rows = 1070, stop_loss coverage = 100%
log_gate rows = 1070, stop_loss coverage = 100%
percentile_gate rows = 1070, stop_loss coverage = 100%
```

## 回測結果

| rule | return | max DD | trades | exits | 判斷 |
| --- | ---: | ---: | ---: | --- | --- |
| no_stop production | +20.94% | -6.34% | 20 | scheduled 20 | 壓力測試基準 |
| fixed8 production | +35.76% | -11.91% | 49 | scheduled 13 / stop 36 | 固定 8% 有研究價值 |
| ranking low production | -9.16% | -23.85% | 68 | scheduled 14 / stop 54 | 不可用 |
| ranking close production | -7.85% | -19.09% | 52 | scheduled 15 / stop 37 | 不可用 |
| no_stop log_gate | +34.38% | -27.42% | 20 | scheduled 20 | 高報酬高回撤 |
| ranking low log_gate | -6.40% | -32.61% | 60 | scheduled 16 / stop 44 | 不可用 |
| ranking close log_gate | -12.51% | -32.70% | 47 | scheduled 14 / stop 33 | 不可用 |

## 判斷

```text
stop_execution_policy = FULL_EXIT_ON_INVALIDATION
current_ranking_stop_loss_ready = false
production_ready = false
```

關鍵結論：

```text
停損機制應該是全賣。
但目前 trade_plan stop_loss 生成邏輯不能直接拿來當正式出場規則。
它太容易觸發，會把策略洗出場，回測結果反而變差。
```

## 後續方向

下一步不是改成半賣，而是重校準 stop_loss 價位：

```text
1. 區分 hard stop 與 warning zone。
2. hard stop 才全賣。
3. warning zone 只是不加碼 / 隔日重新評估。
4. 測固定 8% hard stop、結構停損、收盤確認、跳空處理。
5. 推播文案不能把未驗證的 stop_loss 包裝成正式可交易停損。
```

目前可以保留的產品規則：

```text
跌破 hard stop：全賣。
獲利達標：分批賣。
目前 ranking stop_loss：只能當風險提醒，不能當已驗證交易出場規則。
```

證據：

```text
artifacts/liquidity_quality_candidate_universe_shadow_halfyear_with_trade_plan_2026-06-03.json
artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_production_fixed40_regime_stop_full_2026-06-03.json
artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_production_fixed40_regime_stop_close_full_2026-06-03.json
artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_log_gate_fixed40_regime_stop_full_2026-06-03.json
artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_log_gate_fixed40_regime_stop_close_full_2026-06-03.json
```
