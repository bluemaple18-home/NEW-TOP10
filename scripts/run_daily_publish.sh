#!/usr/bin/env bash
# 收盤後每日主流程：跑 daily，成功後把最新 Clawd 訊息交給 New Clawd 發送。

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_publish_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "開始收盤後 daily publish - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
bash "$PROJECT_DIR/scripts/run_daily.sh" >> "$LOG_FILE" 2>&1
DAILY_EXIT_CODE=$?
set -e

if [ "$DAILY_EXIT_CODE" -ne 0 ]; then
  echo "daily failed; skip Clawd send. exit_code=$DAILY_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$DAILY_EXIT_CODE"
fi

set +e
MESSAGE_FILE="$(
  python3 - "$PROJECT_DIR" <<'PY'
import json
import sys
from pathlib import Path

project = Path(sys.argv[1])
status_path = project / "artifacts" / "automation_status.json"
if status_path.exists():
    status = json.loads(status_path.read_text(encoding="utf-8"))
    message = status.get("metadata", {}).get("clawd_publish_message") or status.get("metadata", {}).get("expected_clawd_publish_message")
    if message and Path(message).exists():
        print(message)
        raise SystemExit(0)

files = sorted((project / "artifacts").glob("clawd_publish_message_*.md"), key=lambda path: path.stat().st_mtime)
if files:
    print(files[-1])
    raise SystemExit(0)
raise SystemExit("missing clawd_publish_message artifact")
PY
)"
MESSAGE_STATUS=$?
set -e

if [ "$MESSAGE_STATUS" -ne 0 ] || [ -z "$MESSAGE_FILE" ]; then
  echo "missing Clawd message artifact; skip send." | tee -a "$LOG_FILE"
  exit 1
fi

echo "sending Clawd message: $MESSAGE_FILE" | tee -a "$LOG_FILE"
set +e
bash "$PROJECT_DIR/scripts/report_stock_status.sh" --message-file "$MESSAGE_FILE" >> "$LOG_FILE" 2>&1
SEND_EXIT_CODE=$?
set -e

if [ "$SEND_EXIT_CODE" -eq 0 ]; then
  echo "daily publish finished - $(date)" | tee -a "$LOG_FILE"
else
  echo "Clawd send command returned exit_code=$SEND_EXIT_CODE; main daily already completed." | tee -a "$LOG_FILE"
fi

exit 0
