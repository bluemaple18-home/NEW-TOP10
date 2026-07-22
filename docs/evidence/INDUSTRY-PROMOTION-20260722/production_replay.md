# M13-06 Industry Momentum Walkforward Shadow

- 狀態：`OK`
- 產生時間：`2026-07-22T14:25:36.515988+00:00`
- horizon：`10` trading days

## 結論

- 決策：`no_go_insufficient_production_history`
- 理由：只有 26 個成熟 production ranking dates，低於 60 日 promotion floor；不得改 production。

## Method

- `baseline_kind`：committed-production-ranking-artifacts
- `industry_factor`：leave-one-out / ex-self
- `industry_min_members`：5
- `sector_min_members`：20
- `production_score_unchanged`：True
- `writes_production_ranking`：False
- `cost_assumption`：NO_TRANSACTION_COST_APPLIED_TO_EITHER_ARM
- `evaluation_top_n`：5

## Walkforward

- `days`：26
- `production_mean_return`：-0.0138
- `shadow_mean_return`：-0.0213
- `return_uplift`：-0.0075
- `production_hit_rate`：0.3692
- `shadow_hit_rate`：0.3462
- `hit_rate_uplift`：-0.0231
- `production_downside`：-0.0815
- `shadow_downside`：-0.0819
- `production_top_industry_concentration`：0.6615
- `shadow_top_industry_concentration`：0.6308
- `average_overlap_count`：4.0769

## Factor Quality

- `industry_momentum_20d_ex_self`：{'coverage': 1.0, 'latest_coverage': 1.0, 'member_count_min': 6, 'valid_peer_count_min': 5, 'valid_peer_count_p10': 27.0, 'rows_with_lt_2_valid_peers': 0, 'rows_with_lt_3_valid_peers': 0, 'rows_with_lt_5_valid_peers': 0}
- `industry_breadth_ma20_ex_self`：{'coverage': 1.0, 'latest_coverage': 1.0, 'member_count_min': 6, 'valid_peer_count_min': 5, 'valid_peer_count_p10': 27.0, 'rows_with_lt_2_valid_peers': 0, 'rows_with_lt_3_valid_peers': 0, 'rows_with_lt_5_valid_peers': 0}
- `sector_rotation_score_20d_ex_self`：{'coverage': 1.0, 'latest_coverage': 1.0, 'member_count_min': 28, 'valid_peer_count_min': 27, 'valid_peer_count_p10': 128.0, 'rows_with_lt_2_valid_peers': 0, 'rows_with_lt_3_valid_peers': 0, 'rows_with_lt_5_valid_peers': 0}

## Latest Shadow Top

- 2883 凱基金 金融保險 shadow_rank=1.0 production_rank=1
- 3046 建碁 電子工業 shadow_rank=2.0 production_rank=2
- 6442 光聖 未分類 shadow_rank=3.0 production_rank=3
- 7799 禾榮科 未分類 shadow_rank=4.0 production_rank=4
- 6579 研揚 未分類 shadow_rank=5.0 production_rank=5

## 邊界

- 本研究不修改 production `risk_adjusted_score`。
- 本研究不修改 LightGBM feature list。
- shadow score 只存在本 artifact，不寫入正式 ranking CSV/API。
