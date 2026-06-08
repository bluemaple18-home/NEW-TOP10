# CAPITAL-REALISM-07｜Balanced Sizing 對 Ranking 變體檢查

日期：2026-06-05

## Root Question

`CAPITAL-REALISM-06` 找到 balanced sizing：

```text
每檔最多 12%
最多 8 檔
每天最多新進 2 檔
```

本卡要確認：

```text
這個資金規則是否只對 current ranking 有效？
套到 K9 ranking 變體會不會明顯更好？
```

## 邊界

```text
research_only = true
不改模型
不改 production ranking
不改 risk_adjusted_score
不改推播
```

## 本輪結果

已完成。

```text
decision = BALANCED_SIZING_ROBUST_RANKING_VARIANT_NOT_PROMOTED
sizing_policy_candidate = p12_open8_new2
ranking_variant_promotion = false
production_change = false
```

平均結果：

```text
current:
avg_return +51.72%
avg_drawdown -6.00%
risk_adjusted 8.62

feature_k9:
avg_return +51.59%
avg_drawdown -5.97%
risk_adjusted 8.64

sector_k9:
avg_return +51.65%
avg_drawdown -6.15%
risk_adjusted 8.40
```

白話：

```text
balanced sizing 本身穩，
但 K9 ranking 變體沒有明顯贏 current。

所以這張卡支持「資金規則 shadow」，
不支持「ranking 變體升版」。
```

證據：

```text
artifacts/model_experiments/capital_realism07_balanced_variant_report_2026-06-05.json
artifacts/model_experiments/capital_realism07_balanced_variant_report_2026-06-05.md
scripts/build_capital_realism07_balanced_variant_report.py
scripts/verify_capital_realism07_balanced_variant_report.py
```
