---
id: OVERLAY-ROBUSTNESS-REPLAY-01
status: COMPLETED_RESEARCH
type: historical-robustness-replay
---

# Chip／Event Overlay Historical Robustness Replay

## Root question

在 prospective shadow 尚無 seal 後 D+10 成熟日期時，既有 paired walk-forward
日報酬增量是否能通過考慮持有期重疊的歷史不確定性壓力測試？

## Frozen contract

- candidates：
  - `chip_0.10`，來源為既有 point-in-time portfolio replay。
  - `event_0.10`，來源為既有 constrained portfolio replay。
- 不重新挑 feature、不調權重、不搜尋參數。
- statistic：同一 ranking date 的 `overlay avg_net_return - baseline avg_net_return`。
- moving-block bootstrap：
  - fold-stratified circular block；block 不得跨越 walk-forward fold。
  - block length `10`，對齊 D+10 holding horizon。
  - repetitions `10000`。
  - seed `20260723`。
  - percentile interval `95%`。
- leave-one-fold-out：逐一移除原 walk-forward fold 後重算平均增量。

## Decision policy

- `ROBUST_HISTORICAL_SUPPORT`：95% CI lower bound > 0，且所有 leave-one-fold-out 平均增量 > 0。
- `HISTORICAL_SUPPORT_UNCERTAIN`：bootstrap `P(mean>0) >= 0.80`，且至少 4/5 leave-one-fold-out 為正。
- `HISTORICAL_SUPPORT_WEAK`：其餘情況。

## Boundaries

- 本卡只能判斷歷史 robustness，不得取代 prospective `60` 日 acceptance。
- 不修改 production model、ranking、feature 或權重。
- 結果無論好壞都不得直接 promotion。

## Result

- Chip 10%：`HISTORICAL_SUPPORT_UNCERTAIN`
  - paired days：114
  - mean delta：`+0.002740`
  - 95% block-bootstrap CI：`[-0.001251, +0.006371]`
  - `P(mean>0)=0.9115`
  - leave-one-fold-out：`5/5` 為正
- Event constrained 10%：`ROBUST_HISTORICAL_SUPPORT`
  - paired days：55
  - mean delta：`+0.005819`
  - 95% block-bootstrap CI：`[+0.002715, +0.008958]`
  - `P(mean>0)=1.0000`
  - leave-one-fold-out：`5/5` 為正

結論：Event 值得優先累積 prospective shadow；Chip 保留 shadow，但歷史不確定性較高。
