#!/usr/bin/env bash
# 收盤後每日主流程：跑 daily，且只有本次 OK run 明確允許時才送 Clawd。

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_publish_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi
RUN_DATE="${TOP10_RUN_DATE:-$(date +%F)}"
export TOP10_RUN_DATE="$RUN_DATE"

send_ops_report() {
  set +e
  OPS_ARGS=(scripts/send_top10_ops_report.py --run-date "$RUN_DATE" --send)
  if [ "$RUN_DATE" != "$(date +%F)" ]; then
    OPS_ARGS+=(--allow-stale-send)
  fi
  "$PYTHON_BIN" "${OPS_ARGS[@]}" >> "$LOG_FILE" 2>&1
  OPS_EXIT_CODE=$?
  set -e
  if [ "$OPS_EXIT_CODE" -eq 0 ]; then
    echo "ops progress report sent/recorded" | tee -a "$LOG_FILE"
  else
    echo "ops progress report failed exit_code=$OPS_EXIT_CODE" | tee -a "$LOG_FILE"
  fi
  return "$OPS_EXIT_CODE"
}

echo "========================================" | tee -a "$LOG_FILE"
echo "開始收盤後 daily publish - $(date)" | tee -a "$LOG_FILE"
echo "publish run_date: $RUN_DATE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
bash "$PROJECT_DIR/scripts/run_daily.sh" >> "$LOG_FILE" 2>&1
DAILY_EXIT_CODE=$?
set -e

if [ "$DAILY_EXIT_CODE" -ne 0 ]; then
  echo "daily failed; skip Clawd send. exit_code=$DAILY_EXIT_CODE" | tee -a "$LOG_FILE"
  set +e
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" \
    --status skipped \
    --decision stop \
    --reason "daily failed before publish; exit_code=$DAILY_EXIT_CODE" >> "$LOG_FILE" 2>&1
  set -e
  send_ops_report || true
  exit "$DAILY_EXIT_CODE"
fi

set +e
MESSAGE_FILE="$(
  "$PYTHON_BIN" - "$PROJECT_DIR" "$RUN_DATE" 2>> "$LOG_FILE" <<'PY'
import json
import sys
from pathlib import Path

import yaml

project = Path(sys.argv[1])
today = sys.argv[2]
status_path = project / "artifacts" / "automation_status.json"
config_path = project / "config" / "automation.yaml"
if not status_path.exists():
    raise SystemExit("automation_status.json missing; skip Clawd send")
status = json.loads(status_path.read_text(encoding="utf-8"))
if status.get("status") != "OK":
    raise SystemExit(f"daily status is not OK: {status.get('status')}; skip Clawd send")
if status.get("run_date") != today:
    raise SystemExit(f"daily run_date mismatch: {status.get('run_date')} != {today}; skip Clawd send")
metadata = status.get("metadata") if isinstance(status.get("metadata"), dict) else {}
message = metadata.get("clawd_publish_message")
if not message:
    raise SystemExit("metadata.clawd_publish_message missing for this run; skip Clawd send")
message_path = Path(message)
if not message_path.exists():
    raise SystemExit(f"metadata.clawd_publish_message missing on disk: {message}; skip Clawd send")
config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
if notify.get("clawd_enabled") is not True:
    raise SystemExit("notify.clawd_enabled is not true; skip Clawd send")
if notify.get("clawd_dry_run") is not False:
    raise SystemExit("notify.clawd_dry_run is not false; skip Clawd send")
print(message_path)
PY
)"
MESSAGE_STATUS=$?
set -e

if [ "$MESSAGE_STATUS" -ne 0 ] || [ -z "$MESSAGE_FILE" ]; then
  echo "Clawd live send not allowed for this run; skip send." | tee -a "$LOG_FILE"
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" \
    --status skipped \
    --reason "Clawd live send not allowed for this run" >> "$LOG_FILE" 2>&1
  if ! send_ops_report; then
    exit "$OPS_EXIT_CODE"
  fi
  exit 0
fi

echo "sending Clawd message from current OK run: $MESSAGE_FILE" | tee -a "$LOG_FILE"
set +e
SEND_ARGS=("$PROJECT_DIR/scripts/send_clawd_publish_message.py" --message "$MESSAGE_FILE" --send)
if [ "$RUN_DATE" != "$(date +%F)" ]; then
  SEND_ARGS+=(--allow-stale-send)
fi
"$PYTHON_BIN" "${SEND_ARGS[@]}" >> "$LOG_FILE" 2>&1
SEND_EXIT_CODE=$?
set -e

if [ "$SEND_EXIT_CODE" -eq 0 ]; then
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" \
    --status ok \
    --message "$MESSAGE_FILE" \
    --send-exit-code "$SEND_EXIT_CODE" >> "$LOG_FILE" 2>&1
  if ! send_ops_report; then
    exit "$OPS_EXIT_CODE"
  fi
  echo "daily publish finished - $(date)" | tee -a "$LOG_FILE"
else
  echo "Clawd send command failed; fail publish wrapper. exit_code=$SEND_EXIT_CODE" | tee -a "$LOG_FILE"
  set +e
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" \
    --status failed \
    --decision stop \
    --reason "Clawd send command failed" \
    --message "$MESSAGE_FILE" \
    --send-exit-code "$SEND_EXIT_CODE" >> "$LOG_FILE" 2>&1
  set -e
  send_ops_report || true
  exit "$SEND_EXIT_CODE"
fi

exit 0
