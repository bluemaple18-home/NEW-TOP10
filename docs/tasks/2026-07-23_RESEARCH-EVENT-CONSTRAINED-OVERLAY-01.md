---
id: RESEARCH-EVENT-CONSTRAINED-OVERLAY-01
status: COMPLETED_SHADOW_DESIGN_CANDIDATE
type: evaluation
---

# Event Turnover-constrained Overlay

## Root question

固定 10% event alpha，但強制保留 baseline 名單，是否能把 turnover delta 壓到 0.10 以下，同時保留正報酬增益？

## Parent evidence

- unconstrained 10% event：return delta `+0.007478`、4/5 正 fold、turnover delta `+0.129630`。
- unconstrained 因換手超標而 NO-GO，不能直接放寬 gate。

## Pre-registered design

- event weight：固定 10%，不再測 20%。
- 每日 Top10 強制保留 baseline 前 7 名。
- 剩餘 3 名只能從 baseline Top30 candidate pool 依 blend score 補入。
- 使用與 parent 相同 OOS、成本、TPEX 缺口排除與 fold。
- 不因結果調整 retain count、pool multiplier 或權重。

## Gates

- 平均 net return delta > 0。
- 至少 3 個正 fold。
- turnover delta <= 0.10。
- 平均最大產業曝險不惡化。
- 通過只代表 `SHADOW_DESIGN_CANDIDATE`；因共用 OOS，不能直接 promotion。

## Result

- 56 個可評分日中，1 日因已驗證 TPEX 市場級缺口成對排除，55 日納入。
- return delta：`+0.005819`。
- positive folds：`3/5`。
- turnover delta：`+0.068519`，低於 `0.10`。
- 平均最大產業曝險 delta：`-0.005454`。
- decision：`SHADOW_CANDIDATE`。
- production 未修改；下一步為凍結本設計並累積 seal 後新日期。
