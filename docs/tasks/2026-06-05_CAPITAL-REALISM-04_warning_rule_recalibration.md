# CAPITAL-REALISM-04｜Warning Rule 重校準

日期：2026-06-05

## Root Question

`CAPITAL-REALISM-03` 顯示：

```text
WEAKENING 有方向性。
RISK_ALERT 不乾淨。
```

本卡要回答：

```text
哪些 warning 條件真的可以升級成 RISK_ALERT？
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

用半年 historical ranking replay，拆開測多個候選條件。

候選規則若要通過，必須相對 WATCH 同時滿足：

```text
10D 平均報酬更低
10D 負報酬率更高
10D 跌超過 5% 比率更高
樣本數 >= 100
```

## 驗收

```text
scripts/build_capital_realism04_warning_rule_recalibration.py 可產 JSON / MD
scripts/verify_capital_realism04_warning_rule_recalibration.py 通過
recommendation_channel = NO_CHANGE
warning_channel = RESEARCH_ONLY_NOT_PUSH
```

## 本輪結果

已完成。

```text
decision = NO_CLEAN_RISK_ALERT_RULE
approved_candidates = []
recommendation_channel = NO_CHANGE
warning_channel = RESEARCH_ONLY_NOT_PUSH
```

主要比較：

```text
WATCH 10D avg_return = +7.04%，negative_rate = 38.60%，loss_gt_5pct = 22.09%

current_risk_alert:
10D avg_return = +6.93%
negative_rate = 38.01%
loss_gt_5pct = 14.39%

dropped_from_top10:
10D avg_return = +6.38%
negative_rate = 40.18%
loss_gt_5pct = 20.75%

dropped_and_below_ma5:
10D avg_return = +6.30%
negative_rate = 40.12%
loss_gt_5pct = 20.00%
```

白話：

```text
目前「掉出 Top10」或「跌破短均線」比較像 WEAKENING，
不是足夠強的 RISK_ALERT。

current_risk_alert 的大跌率反而低於 WATCH，
所以不能叫高風險警告。

下一步：
保留 WEAKENING；
RISK_ALERT 暫停輸出；
做 warning-only dry-run message，
確認小白看得懂且不會被誤解成個人賣出指令。
```

證據：

```text
artifacts/model_experiments/capital_realism04_warning_rule_recalibration_2026-06-05.json
artifacts/model_experiments/capital_realism04_warning_rule_recalibration_2026-06-05.md
scripts/build_capital_realism04_warning_rule_recalibration.py
scripts/verify_capital_realism04_warning_rule_recalibration.py
```
