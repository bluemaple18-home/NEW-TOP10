#!/usr/bin/env bash
# 收盤後每日主流程：跑 daily，且只有本次 OK run 明確允許時才送 Clawd。

set -uo pipefail

# 單一 opt-in 契約會傳給 runner 與所有子程序；不等同 dry-run。
for arg in "$@"; do
  case "$arg" in
    --backfill) export TOP10_BACKFILL=1 ;;
    *) echo "不支援參數: $arg" >&2; exit 64 ;;
  esac
done


PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ "${TOP10_PUBLISH_LOCK_HELD:-}" != "1" ]; then
  mkdir -p "$PROJECT_DIR/logs"
  PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
  if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
  fi
  export TOP10_PUBLISH_LOCK_HELD=1
  exec "$PYTHON_BIN" "$PROJECT_DIR/scripts/daily_publish_lock.py" "$PROJECT_DIR/scripts/run_daily_publish.sh" "$@"
fi
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi
"$PYTHON_BIN" "$PROJECT_DIR/scripts/daily_publish_lock.py" --verify "$PROJECT_DIR/logs/daily_publish.lock" || exit 75
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
  if [ "${TOP10_BACKFILL:-0}" = "1" ]; then return 0; fi
  # 沿既有旗標跳過已關閉的ops，避免無關入口錯誤改寫Daily送達結果。
  OPS_EXIT_CODE=64
  OPS_ENABLED="$("$PYTHON_BIN" -c '
import sys
from pathlib import Path
import yaml
config = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8")) or {}
notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
print("1" if notify.get("ops_clawd_enabled") is True else "0")
' "$PROJECT_DIR/config/automation.yaml")" || return 64
  case "$OPS_ENABLED" in
    0) echo "ops progress report disabled; skip"; return 0 ;;
    1) ;;
    *) return 64 ;;
  esac
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

# 先讀同日送達狀態，再決定是否可重建 Daily 產物；成功收據僅可唯讀恢復事件。
PREVIOUS_SEND_STATE="$("$PYTHON_BIN" -c '
import json
import sys
from pathlib import Path
from scripts.openclaw_gateway_sender import protected_delivery_receipt

path = Path(sys.argv[1])
try:
    if not protected_delivery_receipt(path):
        print("UNPROTECTED")
    else:
        status = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(status, dict):
            raise ValueError("invalid send receipt")
        if status.get("status") in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"}:
            print("PENDING")
        else:
            print("CONFIRMED" if status.get("status") == "OK" and status.get("send_attempted") is True
                  and status.get("dry_run") is False else "UNRESOLVED")
except (OSError, ValueError, TypeError, RuntimeError):
    print("UNRESOLVED")
' "$PROJECT_DIR/artifacts/clawd_send_status_${RUN_DATE}.json")"
if [ "${TOP10_BACKFILL:-0}" = "1" ] && [ "$PREVIOUS_SEND_STATE" != "UNPROTECTED" ]; then
  echo "補跑保留既有送達收據，拒絕重建或恢復送達事件。" | tee -a "$LOG_FILE"
  exit 2
fi
if [ "$PREVIOUS_SEND_STATE" = "CONFIRMED" ]; then
  MESSAGE_FILE="$PROJECT_DIR/artifacts/clawd_publish_message_${RUN_DATE}.md"
  set +e
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" --status ok --message "$MESSAGE_FILE" \
    --recover-confirmed-send >> "$LOG_FILE" 2>&1
  RECOVERY_EXIT_CODE=$?
  set -e
  if [ "$RECOVERY_EXIT_CODE" -eq 0 ]; then
    send_ops_report || true
  fi
  echo "同日既有送達收據；事件恢復結果=${RECOVERY_EXIT_CODE}，本次不重建 Daily。" | tee -a "$LOG_FILE"
  exit 2
fi
if [ "$PREVIOUS_SEND_STATE" != "UNPROTECTED" ]; then
  if [ "$PREVIOUS_SEND_STATE" = "PENDING" ]; then
    "$PYTHON_BIN" scripts/record_top10_publish_event.py \
      --run-date "$RUN_DATE" --status degraded --decision stop \
      --reason "先前送達結果未決；禁止重送，待唯讀核對" >> "$LOG_FILE" 2>&1 || true
  fi
  echo "同日送達結果未決；保留原訊息，拒絕重新產生 Daily 產物。" | tee -a "$LOG_FILE"
  exit 2
fi

echo "========================================" | tee -a "$LOG_FILE"
echo "開始收盤後 daily publish - $(date)" | tee -a "$LOG_FILE"
echo "publish run_date: $RUN_DATE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
DAILY_STARTED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
bash "$PROJECT_DIR/scripts/run_daily.sh" >> "$LOG_FILE" 2>&1
DAILY_EXIT_CODE=$?
set -e

if [ "${TOP10_BACKFILL:-0}" = "1" ]; then
  echo "補跑結束 exit_code=${DAILY_EXIT_CODE}；訊號與 ops 送達已禁用。" | tee -a "$LOG_FILE"
  exit "$DAILY_EXIT_CODE"
fi

if [ "$DAILY_EXIT_CODE" -ne 0 ]; then
  echo "daily failed; skip Clawd send. exit_code=$DAILY_EXIT_CODE" | tee -a "$LOG_FILE"
  set +e
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" \
    --status skipped \
    --decision stop \
    --started-at "$DAILY_STARTED_AT_UTC" \
    --reason "daily failed before publish; exit_code=$DAILY_EXIT_CODE" >> "$LOG_FILE" 2>&1
  set -e
  send_ops_report || true
  exit "$DAILY_EXIT_CODE"
fi

set +e
MESSAGE_FILE="$(
  "$PYTHON_BIN" -c '
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
  ' "$PROJECT_DIR" "$RUN_DATE" 2>> "$LOG_FILE"
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
  set +e
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" \
    --status ok \
    --message "$MESSAGE_FILE" \
    --recover-confirmed-send \
    --send-exit-code "$SEND_EXIT_CODE" >> "$LOG_FILE" 2>&1
  EVENT_EXIT_CODE=$?
  set -e
  if [ "$EVENT_EXIT_CODE" -ne 0 ]; then
    echo "送達收據與訊息不一致，拒絕記錄成功事件。" | tee -a "$LOG_FILE"
    exit "$EVENT_EXIT_CODE"
  fi
  if ! send_ops_report; then
    exit "$OPS_EXIT_CODE"
  fi
  echo "daily publish finished - $(date)" | tee -a "$LOG_FILE"
else
  echo "Clawd send 未取得成功回執；檢查 send status 並唯讀核對遠端，結果不明時禁止重送。exit_code=$SEND_EXIT_CODE" | tee -a "$LOG_FILE"
  if [ "$SEND_EXIT_CODE" -eq 2 ] && "$PYTHON_BIN" -c '
import json
import sys
from pathlib import Path

status = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if status.get("message_date") != sys.argv[2] or status.get("status") != "OK" or status.get("send_attempted") is not True or status.get("dry_run") is not False:
    raise SystemExit(1)
' "$PROJECT_DIR/artifacts/clawd_send_status_${RUN_DATE}.json" "$RUN_DATE" >/dev/null 2>&1
  then
    set +e
    "$PYTHON_BIN" scripts/record_top10_publish_event.py \
      --run-date "$RUN_DATE" --status ok --message "$MESSAGE_FILE" \
      --recover-confirmed-send >> "$LOG_FILE" 2>&1
    RECOVERY_EXIT_CODE=$?
    set -e
    echo "同日既有送達收據受保護；本次未送出，本地事件恢復結果=${RECOVERY_EXIT_CODE}。" | tee -a "$LOG_FILE"
    exit "$SEND_EXIT_CODE"
  fi
  EVENT_STATUS="failed"
  if "$PYTHON_BIN" -c '
import json
import sys
from pathlib import Path

status = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if status.get("message_date") != sys.argv[2] or status.get("status") not in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"}:
    raise SystemExit(1)
' "$PROJECT_DIR/artifacts/clawd_send_status_${RUN_DATE}.json" "$RUN_DATE" >/dev/null 2>&1
  then
    EVENT_STATUS="degraded"
  fi
  set +e
  "$PYTHON_BIN" scripts/record_top10_publish_event.py \
    --run-date "$RUN_DATE" \
    --status "$EVENT_STATUS" \
    --decision stop \
    --reason "Clawd send 未取得成功回執；送達結果待唯讀核對，禁止直接重送" \
    --message "$MESSAGE_FILE" \
    --send-exit-code "$SEND_EXIT_CODE" >> "$LOG_FILE" 2>&1
  set -e
  send_ops_report || true
  exit "$SEND_EXIT_CODE"
fi

exit 0
