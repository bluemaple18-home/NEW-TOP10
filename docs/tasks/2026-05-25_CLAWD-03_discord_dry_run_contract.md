# CLAWD-03｜Discord Dry-run Send Contract

## 任務

把 Clawd-ready message 接到本機 OpenClaw/Clawd CLI 的 dry-run 發送契約，目標是 Discord `#stock-watchlist`。

## 目標頻道

- channel provider: `discord`
- target: `channel:1507327845003825154`
- 測試頻道: `#stock-watchlist`

## 邊界

- 預設只能 dry-run。
- 正式送出必須同時滿足：
  - CLI 參數有 `--send`
  - `config/automation.yaml` 的 `notify.clawd_enabled=true`
  - `notify.clawd_dry_run=false`
- 不得讀取或輸出 token / webhook / 密碼。
- 不得改 Clawd 專案。
- 不得改 ranking/model/ETL。

## 驗收

- `scripts/send_clawd_publish_message.py --date 2026-05-25` 會以 dry-run 呼叫 Clawd CLI。
- dry-run evidence 必須記錄 channel、target、message path、exit code、send_attempted=false。
- 未滿足正式送出條件時，不能送出正式訊息。

## 證據

- `artifacts/clawd_send_status_2026-05-25.json`
- `artifacts/clawd_send_status_2026-05-25_sendflag_safety.json`
- `artifacts/clawd_publish_message_2026-05-25.md`

## 執行紀錄

- 2026-05-25：已重跑 dry-run。
- 指令：`scripts/send_clawd_publish_message.py --date 2026-05-25`
- 結果：`status=OK`、`dry_run=true`、`send_attempted=false`、`exit_code=0`
- 證據：`artifacts/clawd_send_status_2026-05-25.json`

## 安全閘門驗收

- 正式送出必須同時滿足 `--send`、`notify.clawd_enabled=true`、`notify.clawd_dry_run=false`。
- 目前 config 仍保持 `notify.clawd_enabled=false`、`notify.clawd_dry_run=true`。
- 已補跑 `--send` 負測。
- 指令：`scripts/send_clawd_publish_message.py --date 2026-05-25 --send --output artifacts/clawd_send_status_2026-05-25_sendflag_safety.json`
- 結果：`status=OK`、`dry_run=true`、`send_attempted=false`、`exit_code=0`
- 判定：只開 CLI `--send` 不會正式送出；仍會帶 `--dry-run` 呼叫 Clawd CLI。
