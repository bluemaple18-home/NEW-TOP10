# CAPITAL-REALISM-06｜小白資金配置矩陣

日期：2026-06-05

## Root Question

每日推薦不能只說 Top10。

小白真的照著看，還需要知道：

```text
本金有限時，每檔最多放多少？
最多同時看幾檔？
每天最多新進幾檔？
```

## 邊界

```text
research_only = true
不改模型
不改 production ranking
不改 risk_adjusted_score
不改推播
買賣單位 = 1 股
```

## 測試範圍

```text
ranking source = current half-year dense ranking
本金 = 300,000 / 500,000 / 1,000,000
每檔上限 = 10% / 12% / 15%
最大持股數 = 10 / 8 / 7
每天最多新進 = 1 / 2 / 3
出場 = fixed40
進場 = D+1 open
```

## 驗收

```text
27 組 replay artifact 存在
scripts/build_capital_realism06_sizing_policy_report.py 可產 JSON / MD
scripts/verify_capital_realism06_sizing_policy_report.py 通過
production_change = false
```

## 本輪結果

已完成。

```text
decision = SIZING_POLICY_CANDIDATE_FOUND
return_leader = p10_open10_new3
balanced_candidate = p12_open8_new2
recommended_next_shadow = p12_open8_new2
production_change = false
```

比較：

```text
p10_open10_new3
每檔最多 10%，最多 10 檔，每天最多新進 3 檔
平均報酬 +53.84%
平均回撤 -6.85%
平均交易數 30
risk-adjusted 7.86

p12_open8_new2
每檔最多 12%，最多 8 檔，每天最多新進 2 檔
平均報酬 +51.72%
平均回撤 -6.00%
平均交易數 24
risk-adjusted 8.62
```

白話：

```text
如果只看賺最多，10% / 10 檔 / 每天 3 檔最好。

但小白比較適合先看 balanced candidate：
12% / 8 檔 / 每天最多 2 檔。

它少賺一點，但回撤比較小、交易比較少，
比較不像每天一直追新股票。
```

證據：

```text
artifacts/model_experiments/capital_realism06_sizing_policy_report_2026-06-05.json
artifacts/model_experiments/capital_realism06_sizing_policy_report_2026-06-05.md
scripts/build_capital_realism06_sizing_policy_report.py
scripts/verify_capital_realism06_sizing_policy_report.py
```
