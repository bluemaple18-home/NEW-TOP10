# DAILY-RECOMMENDATION-QUALITY-01 Entry Factor Diagnostics

日期：2026-06-08
狀態：READY_FOR_SHADOW_RERANK_GUARD

## 目標

承接每日推薦主線，先研究「Top10 入榜後到底哪些條件真的比較有用」。

本卡只做 research / shadow diagnostics：

- 不訓練模型。
- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking。
- 不改 `risk_adjusted_score`。
- 不改 Clawd 訊息。

## 使用資料

- 研究區間：`2025-12-01` ~ `2026-06-05`
- ranking days：`116`
- observations：`1160`
- ranking source：
  - `artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15`
  - `artifacts/ranking_2026-06-01.csv` ~ `artifacts/ranking_2026-06-05.csv`
- features source：`data/clean/features.parquet`

## 產出 Artifact

- `artifacts/model_experiments/daily_recommendation_entry_factor_diagnostics_2026-06-08.json`
- `artifacts/model_experiments/daily_recommendation_score_component_diagnostics_2026-06-08.json`

## Baseline

| Horizon | Avg return | Loss > 5% | Gain > 7% |
| --- | ---: | ---: | ---: |
| 1D | 1.20% | 11.74% | 18.17% |
| 3D | 2.13% | 21.33% | 25.31% |
| 5D | 3.36% | 21.89% | 30.72% |
| 10D | 7.17% | 21.87% | 41.12% |

## 第一輪 Survivor

| Policy | Kept | 5D avg delta | 5D loss>5 delta | 10D avg delta |
| --- | ---: | ---: | ---: | ---: |
| `quality_liquid_not_vertical` | 769 | +0.16% | -1.95% | +0.19% |
| `quality_liquid_not_extended` | 480 | +0.12% | -4.26% | -0.22% |

判讀：

- 這兩個規則有資格進下一輪 shadow rerank / portfolio replay。
- 但幅度不夠大，不能直接改 production。
- 更像是「保護小白不要追到太薄、太垂直的股票」，不是新的 alpha 模型。

## Score Component Finding

最高四分位表現不乾淨的元件：

- `risk_adjusted_score`
- `final_score`
- `setup_score`

最高四分位比較像正向的元件：

- `model_prob`
- `rule_score`
- `prediction_score`
- `value_ma20`

重要判讀：

- Top3 整體比 Rank 4-10 好，但 `risk_adjusted_score` 最高四分位不一定更好。
- 代表目前 Top10 內部可能混到「短線太熱 / 流動性太薄 / setup 過度加分」。
- 不應直接調權重；應先做 shadow rerank guard。

## Interaction Segment

| Segment | Count | 5D avg | 5D loss>5 | 10D avg |
| --- | ---: | ---: | ---: | ---: |
| `high_score_liquid_not_vertical` | 114 | 3.67% | 23.64% | 7.48% |
| `high_score_low_liquidity_or_vertical` | 176 | 1.95% | 26.88% | 5.31% |
| `low_score_liquid_not_vertical` | 350 | 4.15% | 14.84% | 8.37% |
| `low_liquidity` | 580 | 2.26% | 25.81% | 5.29% |

白話結論：

- 「分數高」不是萬靈丹。
- 流動性夠、不要太垂直，反而更像安全墊。
- 低流動性是目前 Top10 裡比較明顯的風險來源。

## 下一步

開下一輪 research，但不要一張一張開散卡：

1. 建立 `quality_liquid_not_vertical` shadow rerank guard。
2. 用 production Top10 只做降級 / 標記 / rerank shadow，不補新股票。
3. 跑 portfolio replay，比較 baseline Top10 vs guarded Top10。
4. 若 guard 只降低風險但犧牲報酬，可放到小白版警語或個股頁 observation，而不是 production 排名。

## 邊界

- 不作投資建議。
- 不作正式模型升版證據。
- 不可用這份結果直接改 production ranking。
- 下一關仍必須用 shadow replay / portfolio replay 驗證。

## 2026-06-08 Shadow Guard / Tiered Exposure Replay

新增 artifacts：

- `artifacts/model_experiments/daily_recommendation_quality_guard_portfolio_replay_2026-06-08.json`
- `artifacts/model_experiments/daily_recommendation_quality_tiered_exposure_replay_2026-06-08.json`

### Guard-only Replay

規則：

- 母體只用既有 production Top10。
- 不從 Top10 以外補股票。
- `quality_liquid_not_vertical`：20D 均額 >= 1 億，且 20D 漲幅 <= 40%。

結果：

| Policy | Avg selected | 5D avg delta | 5D DD delta | 10D avg delta | 10D DD delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `quality_liquid_not_vertical` | 6.63 | +0.33% | -2.32% | +0.45% | +1.45% |
| `quality_liquid_not_extended` | 4.14 | -0.03% | -12.10% | -0.40% | -8.93% |
| `liquid_300m_only` | 5.80 | +0.31% | -9.92% | +0.99% | -15.17% |

判讀：

- 直接剔除不是好解法。
- `quality_liquid_not_vertical` 報酬略好，但 5D drawdown 變差，不能當正式 guard。
- 更嚴格的流動性門檻反而造成集中與回撤惡化。

### Tiered Exposure Replay

規則：

- 符合 `quality_liquid_not_vertical` 的股票視為 primary。
- 不符合者仍保留在 Top10，但降權。
- 降權後多出來的部分視為現金。

結果：

| Policy | Gross | 5D avg delta | 5D DD delta | 10D avg delta | 10D DD delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tier_secondary_75pct` | 91.57% | -0.19% | +2.38% | -0.49% | +2.67% |
| `tier_secondary_50pct` | 83.15% | -0.37% | +4.83% | -0.99% | +5.20% |
| `tier_secondary_25pct` | 74.72% | -0.56% | +7.35% | -1.48% | +7.76% |
| `guard_only_cash_rest` | 66.29% | -0.75% | +9.94% | -1.97% | +10.37% |

判讀：

- 降權能降低回撤，但代價是少賺。
- 這比較像資金管理 / 小白風險提示，不是選股模型變強。
- 若要接產品，應該放在 UI 的「保守觀察」或個股頁說明，不應改每日 Top10 排名。

下一步調整：

- `quality_liquid_not_vertical` 不升正式 ranking guard。
- `tier_secondary_75pct` 可列為 risk-management shadow candidate，但不能出現在短訊息版。
- 主線下一步回到「能不能找出更好的 entry alpha」，而不是靠降權降低風險。

## 2026-06-08 Industry / Theme Context Diagnostics

新增 artifacts：

- `artifacts/model_experiments/daily_recommendation_industry_context_diagnostics_2026-06-08.json`
- `artifacts/model_experiments/daily_recommendation_industry_context_portfolio_replay_2026-06-08.json`

資料邊界：

- 使用 `data/reference/stock_industry_map.csv`、`data/reference/stock_concept_membership.csv`、`config/notification_theme_buckets.csv` 做 static grouping。
- 產業 / 概念只當分群脈絡，不假裝是當時即時新聞。
- 不改模型、不改 ranking score。

### Factor Diagnostics

初輪 survivor：

- `industry_name_value_rank_top_quartile`
- `industry_name_top10_cluster_ge2`
- `industry_name_top10_cluster_ge3`
- `notification_bucket_value_rank_top_quartile`
- `notification_bucket_ret20_rank_top_quartile`
- `notification_bucket_top10_cluster_ge2`
- `notification_bucket_top10_cluster_ge3`

最有訊號的條件：

| Condition | Count | 5D avg delta | 5D loss>5 delta | 10D avg delta |
| --- | ---: | ---: | ---: | ---: |
| `notification_bucket_value_rank_top_quartile` | 937 | +2.23% | -3.26% | +3.18% |
| `notification_bucket_top10_cluster_ge2` | 983 | +1.49% | -0.95% | +1.69% |
| `notification_bucket_ret20_rank_top_quartile` | 622 | +1.18% | -0.97% | +3.44% |
| `industry_name_top10_cluster_ge3` | 186 | +1.14% | -5.63% | +2.30% |

反面發現：

- `sector_name_breadth_rank_top_quartile` 表現反而較差。
- 單純「整個 sector 很多人站上月線」不一定是好事，可能已經太擁擠。

### Portfolio Replay

母體仍只用 production Top10，不從 Top10 外補股。

| Policy | Avg selected | Zero days | 5D avg delta | 5D DD delta | 10D avg delta | 10D DD delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bucket_cluster_ge2` | 8.47 | 0 | +0.20% | +0.88% | +0.23% | +3.57% |
| `bucket_value_top_q` | 8.08 | 0 | +0.30% | +1.14% | +0.50% | +0.69% |
| `bucket_ret20_top_q` | 5.36 | 1 | +0.44% | -7.94% | +1.60% | -14.77% |
| `bucket_value_and_ret20_top_q` | 4.72 | 1 | +0.33% | -6.70% | +1.23% | -12.59% |

判讀：

- `bucket_cluster_ge2` 與 `bucket_value_top_q` 是目前最乾淨的 shadow survivor。
- `bucket_ret20_top_q` 報酬更高，但回撤變差，暫不適合小白版。
- 單純追族群 20D 動能太激進，容易變成追高。

產品含義：

- 每日推薦可以保留 10 檔，但內部標記「主流族群支撐」。
- 小白短訊息可以用白話說：「這檔不是自己一檔在漲，同族群也有資金一起進來。」
- UI / 個股頁可以放更專業的族群資料。
- 不應把這條直接升成 production ranking，下一步要做 shadow monitor / rerank dry-run。

主線下一步：

- 優先追 `bucket_cluster_ge2` 與 `bucket_value_top_q`。
- 測「只改排序 / 標籤，不改 Top10 母體」的 daily shadow monitor。
- 同時保留 baseline Top10 作對照組。
