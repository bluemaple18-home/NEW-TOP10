# RESEARCH-CHIP-POINT-IN-TIME-01 Evidence

status: GO（研究收尾）／NO-GO（production promotion）

## Root question

在每日只用當時 trailing 20D 成交額選出的 Top200 流動性股票中，法人籌碼訊號是否有可供後續判斷的獨立增益？

## Evidence

- walk-forward artifact：`artifacts/model_experiments/chip_point_in_time_walkforward_2026-07-23.json`
- portfolio replay artifact：`artifacts/model_experiments/chip_point_in_time_portfolio_replay_2026-07-23.json`
- verifier：
  - `.venv/bin/python scripts/verify_feature_group_regime_walkforward.py`
  - `.venv/bin/python scripts/verify_chip_point_in_time_portfolio_replay.py`
- representative runs：
  - `.venv/bin/python scripts/research_feature_group_regime_walkforward.py --market-regime-history artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json --universe-mode point-in-time-liquidity --liquidity-top-n 200 --output artifacts/model_experiments/chip_point_in_time_walkforward_2026-07-23.json`
  - `.venv/bin/python scripts/research_chip_point_in_time_portfolio_replay.py`

## Facts

- Top200 universe：262 日、每日 200 檔、institutional coverage 平均 `0.801393`。
- chip incremental：122 個 OOS 日、partial Spearman IC `0.011090`、positive stable bucket rate `0.625`。
- `2026-04-13` features 僅有 TWSE 1,069 檔、TPEX 0 檔；8 個跨越該日的 cohort 已對所有 variant 成對排除，receipt 含缺失股票與市場。
- 10% overlay（114 日）：return delta `0.002740`、positive folds `3/5`、turnover delta `0.073451`、industry exposure delta `-0.011404`。
- 20% overlay（114 日）：return delta `0.000988`、positive folds `2/5`、turnover delta `0.148672`。

## Acceptance mapping

- 每日 point-in-time universe 重排：PASS。
- train-only selection、10D label embargo、append-only regime：PASS。
- chip availability 70% gate：PASS；不足日不評分。
- 成本、fold、turnover、集中度 gate：
  - 10% overlay：PASS，僅列 `SHADOW_CANDIDATE`。
  - 20% overlay：FAIL。
- production ranking／權重／模型未修改：PASS。

## Interpretation

籌碼因子不是「沒有結論」。它在高流動性且籌碼資料有效的樣本內出現薄但可重現的增量，10% overlay 可作未來判斷依據；20% 太強，換手與 fold 穩定性不合格。

## Limits and next step

- portfolio replay 與 incremental IC 共用 OOS window，不是獨立確認。
- baseline 與 overlay 使用 chip score 有效的成對樣本，不能外推到全市場。
- 下一步應固定 10% overlay 做 append-only shadow，不再回頭調權重；累積新日期後另開獨立 acceptance。
