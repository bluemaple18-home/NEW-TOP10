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
