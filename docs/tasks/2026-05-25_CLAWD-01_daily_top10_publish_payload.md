# CLAWD-01｜Daily Top10 Publish Payload

## 任務

把既有每日決策日報轉成 Clawd 可接手的頻道訊息 payload。

## 邊界

- 只讀 `artifacts/daily_report_YYYY-MM-DD.json`。
- 只寫 `artifacts/clawd_publish_payload_YYYY-MM-DD.json` 與 `artifacts/clawd_publish_message_YYYY-MM-DD.md`。
- 不呼叫 Clawd、不發送訊息、不讀取或寫入任何 token。
- 不重跑 ETL、ranking、model training。

## 驗收

- payload 保留來源日報、ranking date、Top10、曝險摘要、交易計畫、風險摘要。
- message 是可直接貼到頻道的繁中 Markdown。
- 未提供 channel / target 時，delivery status 必須是 `PENDING_TARGET`。
- 提供 channel / target 時，delivery status 必須是 `READY_FOR_CLAWD`，但仍不得真的發送。

## 證據

- `artifacts/clawd_publish_payload_2026-05-15.json`
- `artifacts/clawd_publish_message_2026-05-15.md`

