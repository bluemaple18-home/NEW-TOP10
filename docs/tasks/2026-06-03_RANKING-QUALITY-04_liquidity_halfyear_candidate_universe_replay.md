# RANKING-QUALITY-04｜流動性品質半年完整候選池 replay

日期：2026-06-03

## Root Question

RANKING-QUALITY-03 證明 liquidity shadow 會改變完整候選池 Top10，但只有 6 個交易日。

本卡把測試拉到近半年 matured window：

```text
2025-12-01 ~ 2026-05-15
ranking days = 107
shadow ranking csv = 321
```

目的不是上線，而是確認流動性品質分數是不是值得進下一層有限本金 replay。

## 邊界

```text
research_only = true
不覆蓋 artifacts/ranking_*.csv
不改 production risk_adjusted_score
不改 models/latest_lgbm.pkl
不改 Clawd 推播
```

## 實作

更新：

```text
scripts/research_liquidity_quality_candidate_universe_shadow.py
scripts/build_liquidity_quality_candidate_universe_replay_report.py
scripts/verify_liquidity_quality_candidate_universe_replay_report.py
```

新增能力：

```text
--start-date / --end-date / --max-dates
```

這讓完整候選池 shadow 可以從 features 交易日自動產生日期區間，不用手貼日期。

## Shadow 結果

| variant | vs rebuilt production overlap | Top1 change | avg Top10 value |
| --- | ---: | ---: | ---: |
| production | 100.00% | 0 | 1,332,834,798 |
| percentile_gate | 55.89% | 59 / 107 | 3,673,256,110 |
| log_gate | 61.96% | 48 / 107 | 2,536,862,789 |

白話：

```text
percentile_gate 影響太大，會把 Top10 明顯推向高成交金額股票。
log_gate 也會換名單，但比較溫和。
```

## Bucket Replay

注意：

```text
這是 bucket-only replay。
它適合比較 ranking 方向，不代表有限本金實盤報酬。
```

| variant | horizon | return delta vs production | DD delta vs production |
| --- | ---: | ---: | ---: |
| log_gate | 1D | +9.40% | +9.59% |
| log_gate | 3D | +635.44% | +7.96% |
| log_gate | 5D | +804.89% | +4.68% |
| log_gate | 10D | +6143.09% | +5.87% |
| percentile_gate | 1D | +5.95% | +6.22% |
| percentile_gate | 3D | +645.65% | +7.02% |
| percentile_gate | 5D | +1022.74% | +3.25% |
| percentile_gate | 10D | +10437.54% | +7.46% |

## 判斷

```text
decision = READY_FOR_CAPITAL_AWARE_REPLAY
production_ready = false
```

原因：

```text
半年 bucket replay 顯示 liquidity score 有 ranking 訊號。
但 bucket-only 會放大複利，不能拿來當小白實盤證據。
必須進 RQ05 有限本金 replay。
```

證據：

```text
artifacts/liquidity_quality_candidate_universe_shadow_halfyear_2026-06-03.json
artifacts/liquidity_quality_candidate_universe_replay_report_halfyear_2026-06-03.json
```
