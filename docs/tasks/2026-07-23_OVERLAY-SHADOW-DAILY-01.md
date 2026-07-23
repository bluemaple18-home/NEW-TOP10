---
id: OVERLAY-SHADOW-DAILY-01
status: COMPLETED
type: research-monitor-automation
---

# Overlay Append-only Shadow Daily Monitor

## Root question

如何讓 Chip／Event frozen overlay 在新 D+10 日期成熟後自動累積，且不影響正式 daily ranking、推播與成敗？

## Contract

- 每個交易日 daily ETL 完成後：
  1. 用最新 `features.parquet` 產生 regime extension。
  2. 只追加比現有 regime history 更新的日期；舊日期標籤永不覆寫。
  3. 執行 Chip 與 Event append-only shadow ledger。
  4. 產生單一結構化 daily receipt。
- 同一日期重跑不得重複 observation 或 warning。
- 任一 research monitor 失敗必須顯示在 receipt，但 automation 使用 `allow_failure`，不得讓 production daily 失敗。
- `promotion_allowed=false`；不得修改模型、ranking、權重或推播內容。

## Acceptance

- 現有真實資料可成功執行兩個 ledger。
- 連續執行兩次後 observation／warning key 集合不變。
- 既有 Chip verifier 通過。
- daily orchestrator 測試證明 monitor 位於 research shadow 區，且在 status aggregation 前執行。
- config 明確啟用，但 runner failure 不阻斷 production daily。

## Result

- regime history 已 append 至 `2026-07-23`，281 個交易日。
- 最新 D+10 mature date 仍為 `2026-07-08`；`2026-07-09` 後目前只有 9 個交易日。
- Chip／Event observations 均為 `0/60`，兩次連跑皆追加 0 observation、0 warning。
- combined receipt：`OK`；`promotion_allowed=false`、`changes_production_ranking=false`。
- 初次 CLI import failure 已以 repo-root import path 修復，原真實資料指令已完成 red→green。
