---
id: RESEARCH-COST-BASIS-INCREMENTAL-01
status: COMPLETED_NO_GO
type: evaluation
---

# Cost Basis Incremental 研究

## Root question

在每日 point-in-time 流動性 Top200 中，成本位置訊號控制 liquidity activity 後，是否仍有獨立增益？

## Data facts

- `close_vs_vwap_5d`、`close_vs_vwap_20d` 在成熟樣本覆蓋 100%。
- `vwap_reclaim_20d`、`vwap_loss_20d` 除首個成熟日期尚未完成初始化外，其餘完整。
- 既有 walk-forward：100 OOS 日、IC `0.020064`、Top-Bottom spread `0.016204`。
- regime 優勢集中於 `RISK_OFF`；本輪不得事後只挑該 regime 放行。

## Pre-registered gates

- primary：`cost_basis`；control：`liquidity_activity`。
- partial IC candidate：至少 40 日、weighted partial IC >= 0.01、穩定 fold/regime buckets 正向比例 >= 60%。
- 只有整體 incremental candidate 才可進成本化 Top10 replay。
- replay 只測固定 10% 與 20% overlay；不得依結果追加權重。
- replay 必須平均 net return delta > 0、至少 3 個正 fold、turnover delta <= 0.10、平均最大產業曝險不惡化。
- 與 IC 共用 OOS window，因此通過也只能是 shadow candidate，不能直接 promotion。

## Result

- mature window：252 日，`2025-06-26`～`2026-07-08`。
- group walk-forward：91 OOS 日、IC `0.013877`、spread `0.015160`、穩定 buckets 正向率 `0.571429`，降為 `MONITOR_ONLY`。
- control liquidity 後：partial IC `0.006802`，7 個穩定 buckets 只有 2 個為正，決策 `NO_INCREMENTAL_EDGE`。
- `RISK_OFF` fold 3 為 `+0.079310`，fold 4 為 `-0.033299`，不具跨 fold 穩定性。
- 依預註冊 gate 停止，未執行 portfolio replay，未修改 production。
