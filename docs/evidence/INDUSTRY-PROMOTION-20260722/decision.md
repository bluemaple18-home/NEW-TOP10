# Industry feature promotion decision — 2026-07-22

結論：`REJECT`，正式動作為 `NO_RANKING_OR_WEIGHT_CHANGE`。

以 SHA-256 `34751b381bd3aac36f52e6bc683ff006801ab44eae5d269e9c2107b0d13cb1c4` 的 `features.parquet` 重跑 10 交易日 horizon、leave-one-out/ex-self 產業 overlay。樣本為 516,134 rows、1,967 stocks、271 trade days；baseline 與 shadow 使用相同 universe、dates 與 cost assumptions。

結果：平均報酬 `0.0121 → 0.0115`（uplift `-0.0005`），命中率 `0.4506 → 0.4424`（uplift `-0.0081`），產業集中度 `0.6539 → 0.5893`。集中度雖改善，但報酬與命中率同時惡化，未通過最低 return uplift `> 0.005` 與 hit-rate uplift `>= 0` 的共同門檻。

可重現命令：

```bash
<repo-root>/.venv/bin/python scripts/research_industry_momentum_walkforward.py \
  --features <repo-root>/data/clean/features.parquet
<repo-root>/.venv/bin/python scripts/verify_industry_promotion_decision.py
```

研究 artifact JSON SHA-256：`7bcdc6ce3a22df1bd8ea5346a8147088d073f148eb4602253cd59914963f3500`。artifact 本身依 repo 政策留在本機、未進 Git；固定摘要與 fail-closed decision contract 位於同目錄 `decision.json`。

這是已完成的 NO_GO，而非待補證據 blocker。依專案 Boris Standard，不得為了完成字面狀態而修改 `RankingPolicy`、`risk_adjusted_score` 或正式權重。
