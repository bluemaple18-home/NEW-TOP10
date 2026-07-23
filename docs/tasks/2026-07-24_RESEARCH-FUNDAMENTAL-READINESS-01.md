---
id: RESEARCH-FUNDAMENTAL-READINESS-01
status: COMPLETED_BLOCKED_DATA
type: data-readiness-research
---

# Fundamental Point-in-time Research Readiness

## Root question

Fundamental feature group 的 0 OOS 日，究竟是負訊號、pipeline 錯誤，還是 point-in-time 資料覆蓋不足？

## Contract

- 只讀既有本機 fundamental cache；不即時抓 Goodinfo／MOPS。
- 使用與 strict walk-forward 相同的 M4 as-of join。
- universe：每日 trailing 20D 成交額 Top200。
- row available：九個 `fundamental_*` 欄位至少一個非空。
- research gate：
  - 每日至少 30 檔。
  - 每日 coverage 至少 70%。
- model gate：cache stock coverage 至少 80%。
- 低 coverage 下的 IC／spread 只能記為 selection-biased hint，不得作選股結論。

## Decision

- `READY_FOR_POINT_IN_TIME_RESEARCH`：最近 252 個已成熟交易日全部滿足 research gate。
- `BLOCKED_DATA_COVERAGE`：任一 coverage gate 未滿足。

D+10 尚未成熟的最後 10 個交易日不進 readiness 判定。

## Boundaries

- 不補假值、不把缺資料視為零。
- 不改 production model、ranking、feature 或權重。
- 外部批次補資料須另有 source／rate／retention 授權。

## Result

- decision：`BLOCKED_DATA_COVERAGE`
- usable stocks：`23/1967`（`1.17%`）
- latest Top200：`3/200`（`1.50%`）
- 最近 252 個已成熟交易日通過 research gate：`0/252`
- promotion：禁止

完整 receipt 見 `docs/evidence/RESEARCH-FUNDAMENTAL-READINESS-01/result.md`。
