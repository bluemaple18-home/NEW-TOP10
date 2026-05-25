# CLAWD-04｜One-shot Send Gate

## 任務

補強正式送出前的 one-shot send gate，確保送出的 Markdown 一定來自同日期且已 READY 的 Clawd payload。

## 邊界

- 可以修改 `scripts/send_clawd_publish_message.py`。
- 不改 Clawd 專案。
- 不正式送出 Discord 訊息。
- 不改 ranking、model、ETL。

## 驗收

- send wrapper 會檢查同日期 `clawd_publish_payload_YYYY-MM-DD.json`。
- payload 必須是 `delivery.status=READY_FOR_CLAWD`。
- payload 的 channel / target 必須與 `config/automation.yaml` 一致。
- status evidence 必須記錄 payload path、payload delivery status、Top1。
- `--send` 但 config 未開時仍是 dry-run。

## 證據

- `artifacts/clawd_send_status_2026-05-25.json`
- `artifacts/clawd_publish_payload_2026-05-25.json`

