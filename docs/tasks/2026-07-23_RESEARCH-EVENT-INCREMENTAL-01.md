---
id: RESEARCH-EVENT-INCREMENTAL-01
status: COMPLETED_NO_GO
type: evaluation
---

# Event Incremental 研究

## Root question

在每日 point-in-time 流動性 Top200 中，事件型訊號控制 liquidity activity 後，是否仍有穩定的獨立增益？

## Contract

- universe：每日 trailing 20D 成交額 Top200。
- primary：`event`；control：`liquidity_activity`。
- selection：各 fold/regime 僅使用 train dates。
- horizon／embargo：10 個交易日。
- 使用 append-only regime history。
- coverage 不足、無 frozen train selection 或 outcome 未成熟都必須可觀測。

## Pre-registered gates

- partial IC candidate：至少 40 日、weighted partial IC >= 0.01、穩定 fold/regime buckets 正向比例 >= 60%。
- 只有整體 incremental candidate 才能進成本化 Top10 replay。
- replay 只測固定 10% 與 20% event rank overlay，不得追加權重。
- replay 必須平均 net return delta > 0、至少 3 個正 fold、turnover delta <= 0.10、平均最大產業曝險不惡化。
- 通過也只能是 shadow candidate，不能直接 promotion。

## Data exclusion discovered during replay

- `2026-01-16` features 有 TWSE 1,065 檔、TPEX 0 檔，屬市場級 OHLC 缺口。
- ranking date `2026-01-02` 的 10D holding window 跨過該日；必須對 baseline、10%、20% variants 成對排除並留下 receipt。

## Result

- event coverage：13 欄、252 個成熟日期皆 100%。
- incremental：56 OOS 日、partial IC `0.015619`、4 個穩定 buckets 全為正，通過 IC gate。
- replay：56 個可評分日中，1 日因已驗證 TPEX 市場級缺口成對排除，55 日納入。
- 10% overlay：return delta `+0.007478`、4/5 正 fold、turnover delta `+0.129630`、產業曝險 delta `-0.005454`；因換手超標而 `REJECTED`。
- 20% overlay：return delta `+0.008784`、4/5 正 fold、turnover delta `+0.214815`、產業曝險 delta `+0.001819`；換手與集中度皆失敗。
- overall：`NO_GO`；未修改 production。
