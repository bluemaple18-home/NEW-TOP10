# RANKING-QUALITY-05｜流動性品質有限本金 replay

日期：2026-06-03

## Root Question

RQ04 的 bucket replay 很漂亮，但它不是小白真的照推播交易的情境。

本卡用有限本金 replay 檢查：

```text
初始本金 500,000
D+1 開盤進場
最多同時 10 檔
每天最多新買 3 檔
100 股整股買進
固定 20D / 40D horizon 對照
```

## 邊界

```text
research_only = true
不改 production ranking
不改 risk_adjusted_score
不改模型
不改推播
```

## 主要結果

| run | return | max DD | trades | 判斷 |
| --- | ---: | ---: | ---: | --- |
| production_fixed65 | +8.49% | -7.46% | 20 | 比較組 |
| log_gate_fixed65 | +16.92% | -20.91% | 20 | 報酬升，回撤放大 |
| percentile_gate_fixed65 | +14.23% | -21.57% | 20 | 報酬升，回撤放大 |
| production_fixed85 | +11.33% | -8.32% | 20 | 比較組 |
| log_gate_fixed85 | +29.28% | -26.29% | 20 | 太兇 |
| percentile_gate_fixed85 | +16.62% | -23.70% | 20 | 太兇 |
| production_regime | +20.94% | -6.34% | 20 | 目前較適合小白的比較組 |
| log_gate_regime | +34.38% | -27.42% | 20 | 高報酬高回撤 |
| percentile_gate_regime | +14.44% | -25.01% | 20 | 不如 production_regime |
| production_regime_h20 | +15.85% | -7.91% | 50 | 20D 比較組 |
| log_gate_regime_h20 | +10.62% | -27.42% | 50 | 20D 輸 production |
| percentile_gate_regime_h20 | +29.93% | -25.01% | 50 | 報酬高但回撤太大 |

## 判斷

```text
decision = AGGRESSIVE_SHADOW_ONLY
production_ready = false
default_liquidity_score_change = REJECT_AS_DEFAULT
```

白話：

```text
流動性加分不是沒用。
它確實會找到比較會衝的名單。

但對股市小白來說，問題是回撤太大。
你可能多賺，但中間會跌到很難抱。
所以不能直接放進每日 Top10 預設排序。
```

## 後續用途

可以做：

```text
aggressive shadow monitor
個股頁面顯示流動性/可交易性提示
推播裡用白話提醒「這檔波動比較大」
```

不能做：

```text
不能直接合進 production risk_adjusted_score
不能拿 bucket replay 當上線證據
不能把它包裝成小白安全版
```

證據：

```text
artifacts/model_experiments/liquidity_quality_capital_aware_report_2026-06-03.json
artifacts/model_experiments/liquidity_quality_capital_aware_report_2026-06-03.md
scripts/build_liquidity_quality_capital_aware_report.py
scripts/verify_liquidity_quality_capital_aware_report.py
```
