# Industry feature promotion decision — 2026-07-22

結論：`NO_GO_INSUFFICIENT_PRODUCTION_HISTORY`；正式動作為 `NO_RANKING_OR_WEIGHT_CHANGE`。

第一版以 proxy score 冒充 production baseline，獨立 Review 判定 P1 後已廢棄。v2 只讀 40 份實際 `artifacts/ranking_YYYY-MM-DD.csv`，將已成熟且 Top10 全部可配對標籤的 26 日納入，同一批 production Top10 內比較原 `risk_adjusted_score` 與產業 overlay 後的 Top5。未對任一 arm 套用交易成本，證據明記為 no-cost comparison，不宣稱成本後績效。

實際結果：production mean return `-0.0138`、shadow `-0.0213`（uplift `-0.0075`）；hit-rate uplift `-0.0231`；產業集中度 `0.6615 → 0.6308`。結果本身偏負，且 26 個成熟日期低於 promotion floor 60 日，因此不得修改 production ranking／weights。

Committed evidence：

- `production_replay.json`：完整 input hashes、40 份 production ranking manifest、14 份排除原因、method、sample、metrics 與 recommendation。
- `decision.json`：只保存 replay path/hash、固定 gate 與 derived decision。
- `scripts/verify_industry_promotion_decision.py`：先驗 replay SHA-256，再驗 production baseline identity／ranking manifest，最後從 replay 重算 decision。

可重現命令：

```bash
<repo-root>/.venv/bin/python scripts/research_industry_momentum_walkforward.py \
  --features <repo-root>/data/clean/features.parquet \
  --production-rankings-dir <repo-root>/artifacts \
  --output docs/evidence/INDUSTRY-PROMOTION-20260722/production_replay.json
<repo-root>/.venv/bin/python scripts/verify_industry_promotion_decision.py
```

這是已完成的 NO_GO，不是未執行。要重開 promotion，必須累積至少 60 個成熟 production ranking dates 後，以同一 v2 contract 重跑。
