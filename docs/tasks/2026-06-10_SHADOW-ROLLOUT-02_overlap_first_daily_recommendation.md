# SHADOW-ROLLOUT-02｜Overlap-First Daily Recommendation Shadow

## Root Question

如果未來每日推薦要用新候選邏輯，是否應先把 production Top10 與 candidate trail10 Top10 重複出現的股票排前面。

## Scope

- 讀取正式 `artifacts/ranking_YYYY-MM-DD.csv`。
- 讀取 `candidate_trail10_daily_shadow_monitor_YYYY-MM-DD.json`。
- 產出 overlap-first shadow Top10：
  1. production 與 candidate 都上榜者優先。
  2. candidate-only 且有 trail10 風控計畫者接續。
  3. production-only 作 baseline watch 補足 Top10。
  4. candidate-only 但沒有 trail10 計畫者只作最後補位。
- 產出 verifier，確認 shadow-only contract 與排序規格。

## Non-Goals

- 不改 production ranking。
- 不改 `risk_adjusted_score`。
- 不改 daily report / Clawd 推播。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不宣稱 promotion ready。

## Artifacts

- `artifacts/model_experiments/overlap_first_daily_recommendation_shadow_YYYY-MM-DD.json`
- `artifacts/model_experiments/overlap_first_daily_recommendation_shadow_YYYY-MM-DD.md`
- `artifacts/model_experiments/overlap_first_daily_recommendation_shadow_verification_latest.json`
- `artifacts/model_experiments/overlap_first_recommendation_performance_recent_100_YYYY-MM-DD.json`
- `artifacts/model_experiments/overlap_first_recommendation_performance_recent_6m_YYYY-MM-DD.json`
- `artifacts/model_experiments/overlap_first_recommendation_performance_verification_latest.json`

## Contract

```text
shadow_only = true
overlap_first = true
changes_production_top10_membership = false
changes_risk_adjusted_score = false
changes_production_ranking = false
changes_clawd_message = false
changes_model = false
production_switch_ready = false
promotion_ready = false
```

## Selection Policy

```text
bucket 1: overlap_high_confidence
bucket 2: candidate_trail10_only
bucket 3: production_baseline_only
bucket 4: candidate_no_trail10_only
```

白話：兩套方法都選到的先放前面；candidate-only 要有 trail10 風控計畫才排在 baseline 前面；production-only 保留為 baseline 對照；candidate 無 trail10 只補位。

## Acceptance

- shadow Top10 只能來自 production Top10 或 candidate Top10。
- 重複股必須在非重複股前面。
- 不可有重複股票。
- 不可改任何正式 ranking / model / publish artifact。

## Performance Replay Result

Replay policy:

```text
initial cash: 300000
top_n: 7
D+1 open entry
horizon: 40 trading days
max gross exposure: 75%
max position weight: 12%
stop loss: -12%
trailing stop: high-water -10% after 5 trading days
```

Result:

| Window | Variant | Total Return | Max DD | Win Rate | Trades |
| --- | --- | ---: | ---: | ---: | ---: |
| recent_100 | production | 24.50% | -7.93% | 48.44% | 448 |
| recent_100 | candidate | 11.65% | -9.81% | 41.95% | 379 |
| recent_100 | overlap-first | 10.35% | -10.76% | 43.69% | 396 |
| recent_6m | production | 29.33% | -7.93% | 49.76% | 625 |
| recent_6m | candidate | 7.95% | -9.82% | 42.19% | 493 |
| recent_6m | overlap-first | 6.08% | -10.76% | 42.83% | 495 |

Decision:

```text
MONITOR_ONLY
```

結論：overlap-first 的直覺是合理的，但最近 100 天與近半年績效都輸 production；不能替換正式每日推薦。

這不代表 `candidate ranking + trail10` 要被砍掉。失敗的是「把 production 與 candidate 重複者優先」這個混合排序。`candidate+trail10` 另由 `SHADOW-ROLLOUT-03` 保留為條件式切換研究主候選。
