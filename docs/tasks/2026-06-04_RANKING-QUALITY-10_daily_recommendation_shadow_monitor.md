# RANKING-QUALITY-10 每日推薦 K9 Shadow Monitor

## 目標

把 RQ09 通過 PM 風險驗證的 `feature_group_constrained_k9` 轉成可每日觀察的 shadow monitor。

K9 定義：保留 production Top9，只用 feature-group shadow ranking 補第 10 名。

## 不做

- 不改 production ranking。
- 不訓練模型。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不接推播。
- 不宣稱 promotion ready。

## 本輪流程

1. 用 `scripts/research_regime_shadow_ranking.py` 對 production 最新 7 個 ranking 日產 research-only feature-group shadow ranking。
2. 用 `scripts/build_constrained_shadow_rankings.py` 套 K9 constrained rule。
3. 用 `scripts/build_daily_recommendation_shadow_monitor.py` 比較 production Top10 與 K9 shadow Top10。
4. 用 `scripts/verify_daily_recommendation_shadow_monitor.py` 驗證 contract。

## 本輪結果

- candidate：`feature_group_constrained_k9`
- window：`2026-05-26` ~ `2026-06-03`
- date_count：7
- avg_overlap_count：9.0
- min_overlap_count：9
- avg_added_vs_production：1.0
- decision：`DAILY_SHADOW_READY_WITH_REGIME_GAP`
- regime gap：`2026-06-01`, `2026-06-02`, `2026-06-03`

最新日 `2026-06-03`：

- K9 shadow 新增：`8112 至上`
- production 被替換：`9933 中鼎`
- 其餘 9 檔保留 production Top9

產物：

- `artifacts/backtest/shadow_rankings_daily_recommendation_feature_group_k9_source_2026-06-04/regime_shadow_ranking.json`
- `artifacts/backtest/shadow_rankings_daily_recommendation_feature_group_constrained_k9_2026-06-04/constrained_shadow_ranking.json`
- `artifacts/model_experiments/daily_recommendation_shadow_monitor_2026-06-04.json`
- `artifacts/model_experiments/daily_recommendation_shadow_monitor_2026-06-04.md`

結論：K9 可以開始 daily shadow monitor；但 6/01 之後 market regime history 尚未補齊，所以還不能視為完整 production-adjacent shadow。
