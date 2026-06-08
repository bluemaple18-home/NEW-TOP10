# RANKING-QUALITY-03｜完整候選池流動性 shadow 測試

日期：2026-06-03

## Root Question

RANKING-QUALITY-02 只重排既有 ranking artifact 內的候選列，沒有改變 Top10 成員。

本卡改用 `StockRanker` 同模型、同資料重建完整每日候選池，確認 liquidity shadow score 是否真的會把新股票換進 Top10。

## 邊界

```text
research_only = true
不覆蓋 artifacts/ranking_*.csv
不改 production risk_adjusted_score
不改模型
不改 Clawd 訊息
```

## 實作

新增：

```text
scripts/research_liquidity_quality_candidate_universe_shadow.py
scripts/verify_liquidity_quality_candidate_universe_shadow.py
scripts/build_liquidity_quality_candidate_universe_replay_report.py
scripts/verify_liquidity_quality_candidate_universe_replay_report.py
```

產物：

```text
artifacts/liquidity_quality_candidate_universe_shadow_2026-06-03.json
artifacts/liquidity_quality_candidate_universe_shadow_2026-06-03.md
artifacts/liquidity_quality_candidate_universe_replay_report_2026-06-03.json
artifacts/liquidity_quality_candidate_universe_replay_report_2026-06-03.md
artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_2026-06-03/
```

測試區間：

```text
2026-05-26 ~ 2026-06-02
```

測試版本：

```text
production：重建候選池後的原 ranking policy
percentile_gate：3000 萬 gate + 成交金額 percentile score
log_gate：3000 萬 gate + log 成交金額 score
```

## Shadow 結果

| variant | vs 重建 production Top10 overlap | vs 官方 Top10 overlap | Top1 變動 | 平均 Top10 成交金額 |
| --- | ---: | ---: | ---: | ---: |
| production | 100.00% | 68.33% | 0 | 2,293,829,111 |
| percentile_gate | 53.33% | 36.67% | 1 | 5,849,504,783 |
| log_gate | 58.33% | 38.33% | 1 | 3,564,725,345 |

白話解讀：

```text
完整候選池測試下，流動性分數真的會換掉不少 Top10 成員。
percentile_gate 換得比較多，也更偏向高成交金額股票。
log_gate 較溫和，但也會明顯改變名單。
```

注意：

```text
重建 production 與官方 ranking overlap 只有 68.33%。
這代表本輪是「同模型同資料重新推論」的研究基準，
不能直接拿來說官方榜單已被替代。
```

## Replay 結果

| variant | horizon | candidate return | baseline return | delta | candidate DD | baseline DD | DD delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| log_gate | 1 | -6.52% | -6.71% | +0.20% | -7.17% | -6.71% | -0.45% |
| log_gate | 3 | -9.07% | -5.27% | -3.80% | -9.07% | -5.27% | -3.80% |
| log_gate | 5 | -2.52% | -3.47% | +0.95% | -2.52% | -3.47% | +0.95% |
| percentile_gate | 1 | -6.70% | -6.71% | +0.02% | -7.33% | -6.71% | -0.61% |
| percentile_gate | 3 | -4.25% | -5.27% | +1.03% | -4.33% | -5.27% | +0.95% |
| percentile_gate | 5 | -1.47% | -3.47% | +2.01% | -1.47% | -3.47% | +2.01% |

## 判斷

```text
decision = FOLLOWUP_EXTENDED_WINDOW_REQUIRED
production_ready = false
```

原因：

```text
完整候選池版本會改變 Top10 成員。
但目前只有 6 個 ranking days。
而且 production / log_gate / percentile_gate 這段短期 replay 都還是負報酬。
所以不能當正式上線證據。
```

目前比較值得延伸的是：

```text
percentile_gate：3D / 5D 短期相對改善較明顯，但更偏大型高流動性股票。
log_gate：較溫和，5D 有改善，但 3D 輸 baseline。
```

## 下一步

```text
RANKING-QUALITY-04
把完整候選池 liquidity shadow 拉長到近半年。
至少比較：
- production
- log_gate
- percentile_gate

必須檢查：
- Top10 overlap
- Top1 change
- 是否過度偏大型股
- 中小型強勢股是否被錯殺
- 1D / 3D / 5D / 10D replay
- capital-aware replay
```

上線條件：

```text
長區間不能只改善成交金額，報酬或回撤也要有實質改善。
不能把榜單變成純大型股榜。
不能只靠 6 天樣本決策。
```
