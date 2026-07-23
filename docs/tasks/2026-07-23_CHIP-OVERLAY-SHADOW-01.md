---
id: CHIP-OVERLAY-SHADOW-01
status: WAITING_FOR_NEW_OOS_DATES
type: shadow-evaluation
---

# 10% Chip Overlay Append-only Shadow

## Root question

固定 10% chip overlay 在研究 seal date 之後的全新日期，是否仍能改善成本後 Top10 cohort，且不增加過多換手或產業集中？

## Frozen contract

- candidate：`chip_liquidity_overlay_0.10_v1`
- seal date：`2026-07-08`
- universe：每日 trailing 20D 成交額 Top200。
- 僅 `MIXED_NEUTRAL`、`NARROW_LEADER`、`RISK_OFF` 有 frozen selection。
- weight：固定 10%，不得每日重選或調權重。
- outcome：D+1 open 進、D+10 close 出，扣手續費、交易稅與滑價。
- ledger：同一 ranking date 不重算、不覆寫；config digest 改變即拒絕沿用。
- writer：只由 primary integrator machine 維護 runtime ledger，避免兩台機器各自累積不同歷史。
- regime history：seal 日以前 271 列鎖定 anchor digest；歷史標籤漂移即 fail loud。

## Acceptance

- 只使用 seal date 後最早 60 個完整、成熟且 coverage 合格的日期。
- 至少跨 3 個月份，正月度 bucket 比例至少 60%。
- 平均 net return delta > 0。
- turnover delta <= 0.10。
- 平均最大產業曝險 delta <= 0。
- 滿 60 日也只能進獨立 Review，不能直接 promotion。

## Current receipt

- latest source date：`2026-07-22`
- latest mature date：`2026-07-08`
- mature dates after seal：`0`
- observations：`0/60`
- status：`WAITING_FOR_NEW_OOS_DATES`
- 這是正常等待條件，不是程式或權限 blocker。
