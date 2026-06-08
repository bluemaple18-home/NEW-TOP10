# RANKING-QUALITY-02｜流動性品質 shadow 測試

日期：2026-06-03

## Root Question

把 `3000 萬成交金額 = quality_score 滿分` 改成「3000 萬最低可交易 gate + 流動性相對分數」後，會不會改善 Top10 排名品質？

## 測試邊界

本輪只做 shadow，不改 production：

```text
不改正式 ranking_*.csv
不改 risk_adjusted_score
不改模型
不改 Clawd 訊息
```

重要限制：

```text
本輪只使用既有 ranking artifact 裡的候選列重排。
它不能把 ranking CSV 裡不存在的股票拉進 Top10。
所以這輪測的是「既有候選池內排序差異」，不是全市場重跑。
```

## 實作

新增：

```text
scripts/research_liquidity_quality_shadow.py
scripts/verify_liquidity_quality_shadow.py
scripts/build_liquidity_quality_shadow_replay_report.py
scripts/verify_liquidity_quality_shadow_replay_report.py
```

產物：

```text
artifacts/liquidity_quality_shadow_2026-06-03.json
artifacts/liquidity_quality_shadow_2026-06-03.md
artifacts/liquidity_quality_shadow_replay_report_2026-06-03.json
artifacts/liquidity_quality_shadow_replay_report_2026-06-03.md
artifacts/backtest/liquidity_quality_shadow_rankings_2026-06-03/
```

測試區間：

```text
2026-05-26 ~ 2026-06-02
```

測試版本：

```text
production
percentile_gate
log_gate
```

規則：

```text
30,000,000 以下：不通過最低可交易 gate
percentile_gate：通過 gate 後用每日可交易股票的成交金額百分位數給分
log_gate：通過 gate 後用 log 成交金額給分，降低超大成交股壓制力
```

## 結果

ranking shadow：

| variant | Top10 overlap | Top1 變動次數 | 平均 Top10 成交金額 | 可用 1D 平均報酬 |
| --- | ---: | ---: | ---: | ---: |
| production | 100% | 0 | 2,002,475,258 | -0.48% |
| percentile_gate | 100% | 4 | 2,002,475,258 | -0.48% |
| log_gate | 100% | 2 | 2,002,475,258 | -0.48% |

replay extension：

```text
decision = NO_PORTFOLIO_EFFECT_IN_CURRENT_WINDOW
production_ready = false
no_membership_change = true
replay_same = true
```

原因：

```text
這 6 天三種版本 Top10 成員完全一樣，只是排序不同。
既有 Top10 portfolio replay 不看名次順序，只看 Top10 組合。
所以 replay 結果完全相同。
```

## 白話結論

這個發現仍然是對的：

```text
3000 萬可以當「能不能買」的最低門檻。
3000 萬不適合當「流動性品質滿分」門檻。
```

但這輪測試還不能證明要改正式排名。

因為目前 shadow 只改了 Top10 裡面的順序，沒有把新的股票換進 Top10。

## 判斷

```text
不直接上 production
不改 risk_adjusted_score
不把 percentile_gate / log_gate 接進正式排名
```

`log_gate` 比 `percentile_gate` 溫和：

- percentile_gate 6 天內換 Top1 4 次，排序比較躁。
- log_gate 6 天內換 Top1 2 次，比較不會過度翻榜。

但因為 Top10 成員沒變，目前只能說：

```text
log_gate 比較適合進下一輪更大候選池測試。
```

## 下一步

開下一張卡：

```text
RANKING-QUALITY-03
用更大的 candidate universe 重跑 liquidity shadow score。
目標是確認它會不會真的改變 Top10 成員，而不只是改 Top10 排序。
```

驗收條件：

```text
輸出 production Top10 vs liquidity shadow Top10
檢查 Top10 overlap / Top1 change / churn
檢查是否過度偏向大型股
檢查中小型強勢股是否被錯殺
接 replay 檢查 forward return / drawdown
仍不可改正式 ranking
```
