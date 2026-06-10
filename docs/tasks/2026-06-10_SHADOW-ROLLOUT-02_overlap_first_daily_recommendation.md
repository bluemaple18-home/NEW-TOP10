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
