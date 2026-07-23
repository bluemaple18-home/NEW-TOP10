---
id: EVENT-OVERLAY-SHADOW-01
status: WAITING_FOR_NEW_OOS_DATES
type: shadow-evaluation
---

# Event Constrained Overlay Append-only Shadow

## Root question

固定 10% event、保留 baseline 前 7 名、Top30 補 3 名的設計，在研究 seal 後的新成熟日期是否仍有效？

## Frozen contract

- weight：10%
- TopN：10
- retain baseline：7
- candidate pool multiplier：3
- horizon：D+1 open 至 D+10 close
- universe：逐日 trailing 20D 成交額 Top200
- acceptance：seal 後最早 60 個完整日期
- 同一日期不可重算或覆寫；第 61 日不得改寫前 60 日 verdict
- production promotion 不允許

## Frozen selection scope

- supported：`MIXED_NEUTRAL`、`NARROW_LEADER`
- unsupported：`BROAD_RISK_ON`、`CHOPPY_RANGE`、`EARLY_REVERSAL`、`PANIC_SELLING`、`RISK_OFF`
- unsupported regime 必須輸出 warning，不得借用其他 regime feature。

## Current receipt

- latest source date：`2026-07-22`
- latest mature date：`2026-07-08`
- mature dates after seal：`0`
- observations：`0/60`
- status：`WAITING_FOR_NEW_OOS_DATES`
- 這是正常等待條件，不是 blocker。
