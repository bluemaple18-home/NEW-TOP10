# CAPITAL-REALISM-03｜近 7 日 Top10 Warning-only 半年有效性驗證

日期：2026-06-05

## Root Question

每日推薦和警告不能混在同一條訊息裡。

本卡只回答：

```text
近 7 個 ranking 日曾進 Top10 的股票，
如果被標成 WATCH / WEAKENING / RISK_ALERT，
後面 1 / 3 / 5 / 10 天表現是否真的有差？
```

## 邊界

```text
research_only = true
不送推播
不接第二頻道
不改 production ranking
不改 risk_adjusted_score
不改模型
不處理個人持倉
```

## 方法

```text
ranking source:
artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15

features:
data/clean/features.parquet

warning source:
scripts/build_recent_top10_watchlist_warning.py 的同一套分級邏輯

evaluation:
用未來價格只做 1D / 3D / 5D / 10D outcome 評估，
不允許用未來 ranking 產生 warning。
```

## 驗收

```text
scripts/build_capital_realism03_warning_effectiveness_report.py 可產出 JSON / MD
scripts/verify_capital_realism03_warning_effectiveness_report.py 通過
evaluated_target_dates >= 80
observation_count >= 1000
recommendation_channel = NO_CHANGE
warning_channel = RESEARCH_ONLY_NOT_PUSH
```

## 本輪結果

已完成。

```text
decision = PARTIAL_WEAKENING_SIGNAL_MONITOR_ONLY
recommendation_channel = NO_CHANGE
warning_channel = RESEARCH_ONLY_NOT_PUSH
evaluated_target_dates = 101
observation_count = 5,622
```

10D 結果：

```text
WATCH avg_return = +7.04%，negative_rate = 38.60%
WEAKENING avg_return = +6.43%，negative_rate = 40.25%
RISK_ALERT avg_return = +6.93%，negative_rate = 38.01%
```

白話：

```text
WEAKENING 有方向性：
它比 WATCH 平均報酬低，負報酬率也較高。

但 RISK_ALERT 還不乾淨：
它沒有穩定比 WATCH 更差。

所以警告層可以繼續研究，
但不能直接變成推播或賣出提醒。
下一步要重做 RISK_ALERT 定義，
或先只把 WEAKENING 當 warning-only dry-run。
```

證據：

```text
artifacts/model_experiments/capital_realism03_warning_effectiveness_report_2026-06-05.json
artifacts/model_experiments/capital_realism03_warning_effectiveness_report_2026-06-05.md
scripts/build_capital_realism03_warning_effectiveness_report.py
scripts/verify_capital_realism03_warning_effectiveness_report.py
```
