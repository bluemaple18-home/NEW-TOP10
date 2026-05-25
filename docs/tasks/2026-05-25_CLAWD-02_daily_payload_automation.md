# CLAWD-02｜Daily Payload Automation

## 任務

把 DAILY-02 決策日報與 CLAWD-01 publish payload 接進 daily runner，讓每日流程在 ranking 後自動產生可交給 Clawd 的訊息 artifact。

## 邊界

- 可以修改 `scripts/run_automation.py` 與 `config/automation.yaml`。
- `daily.report` 可自動產出 `daily_report_YYYY-MM-DD.json/md`。
- `clawd.payload` 可自動產出 `clawd_publish_payload_YYYY-MM-DD.json` 與 `clawd_publish_message_YYYY-MM-DD.md`。
- 不得實際發送訊息，不得呼叫 Clawd CLI / gateway，不得讀取 token。
- 不得更動 ETL、ranking、model training、API scoring。

## 驗收

- dry-run 只記錄 `DRY_RUN`，不得寫新 report / payload。
- 正式 artifact 產出後，status metadata 必須記錄 daily report 與 Clawd payload 路徑。
- 未設定 channel / target 時，Clawd payload 必須維持 `PENDING_TARGET`。
- `notify.clawd_enabled=false` 時不得發送任何訊息。

## 證據

- `artifacts/automation_status.json`
- `artifacts/daily_run_summary_YYYY-MM-DD.json`
- `artifacts/clawd_publish_payload_YYYY-MM-DD.json`
- `artifacts/clawd_publish_message_YYYY-MM-DD.md`

