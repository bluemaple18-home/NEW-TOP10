#!/usr/bin/env bash
# 將股票專案訊息交給 New Clawd；失敗只寫本地 fallback log，不阻斷主流程。

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NEWCLAWD_NODE="${NEWCLAWD_NODE:-/opt/homebrew/opt/node/bin/node}"
NEWCLAWD_CLI="${NEWCLAWD_CLI:-/Users/mattkuo/new clawd/dist/index.js}"
NEWCLAWD_CHANNEL="${NEWCLAWD_CHANNEL:-discord}"
NEWCLAWD_TARGET="${NEWCLAWD_TARGET:-channel:1507327845003825154}"
NEWCLAWD_TIMEOUT_SECONDS="${NEWCLAWD_TIMEOUT_SECONDS:-60}"

DRY_RUN=0
MESSAGE=""
MESSAGE_FILE=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/report_stock_status.sh [--dry-run] --message "..."
  scripts/report_stock_status.sh [--dry-run] --message-file artifacts/clawd_publish_message_YYYY-MM-DD.md
  printf '%s\n' "message" | scripts/report_stock_status.sh [--dry-run]
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --message)
      if [ "$#" -lt 2 ]; then
        echo "missing value for --message" >&2
        usage >&2
        exit 2
      fi
      MESSAGE="$2"
      shift 2
      ;;
    --message-file)
      if [ "$#" -lt 2 ]; then
        echo "missing value for --message-file" >&2
        usage >&2
        exit 2
      fi
      MESSAGE_FILE="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      if [ -z "$MESSAGE" ]; then
        MESSAGE="$1"
      else
        MESSAGE="${MESSAGE} $1"
      fi
      shift
      ;;
  esac
done

if [ -n "$MESSAGE_FILE" ]; then
  if [ ! -f "$MESSAGE_FILE" ]; then
    echo "message file not found: $MESSAGE_FILE" >&2
    exit 2
  fi
  MESSAGE="$(cat "$MESSAGE_FILE")"
elif [ -z "$MESSAGE" ] && [ ! -t 0 ]; then
  MESSAGE="$(cat)"
fi

if [ -z "$MESSAGE" ]; then
  echo "message is required" >&2
  usage >&2
  exit 2
fi

case "$NEWCLAWD_TIMEOUT_SECONDS" in
  ''|*[!0-9]*)
    echo "NEWCLAWD_TIMEOUT_SECONDS must be a non-negative integer" >&2
    exit 2
    ;;
esac

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

write_fallback_log() {
  local exit_code="$1"
  local stdout_text="$2"
  local stderr_text="$3"
  local log_dir="$PROJECT_DIR/logs"
  local log_path="$log_dir/stock_notify.jsonl"
  local dry_run_json="false"
  if [ "$DRY_RUN" -eq 1 ]; then
    dry_run_json="true"
  fi

  mkdir -p "$log_dir"
  printf '{"ts":"%s","status":"FAILED","exit_code":%s,"channel":"%s","target":"%s","dry_run":%s,"message_chars":%s,"stdout":"%s","stderr":"%s"}\n' \
    "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    "$exit_code" \
    "$(json_escape "$NEWCLAWD_CHANNEL")" \
    "$(json_escape "$NEWCLAWD_TARGET")" \
    "$dry_run_json" \
    "${#MESSAGE}" \
    "$(json_escape "$stdout_text")" \
    "$(json_escape "$stderr_text")" >> "$log_path"
}

CMD=(
  "$NEWCLAWD_NODE"
  "$NEWCLAWD_CLI"
  message
  send
  --channel "$NEWCLAWD_CHANNEL"
  --target "$NEWCLAWD_TARGET"
  --message "$MESSAGE"
  --json
)

if [ "$DRY_RUN" -eq 1 ]; then
  CMD+=(--dry-run)
fi

STDOUT_FILE="$(mktemp "${TMPDIR:-/tmp}/stock_notify_stdout.XXXXXX")"
STDERR_FILE="$(mktemp "${TMPDIR:-/tmp}/stock_notify_stderr.XXXXXX")"
trap 'rm -f "$STDOUT_FILE" "$STDERR_FILE"' EXIT

if [ "$NEWCLAWD_TIMEOUT_SECONDS" -eq 0 ]; then
  "${CMD[@]}" > "$STDOUT_FILE" 2> "$STDERR_FILE"
  EXIT_CODE=$?
else
  "${CMD[@]}" > "$STDOUT_FILE" 2> "$STDERR_FILE" &
  CMD_PID=$!
  ELAPSED=0
  EXIT_CODE=""

  while kill -0 "$CMD_PID" 2>/dev/null; do
    if [ "$ELAPSED" -ge "$NEWCLAWD_TIMEOUT_SECONDS" ]; then
      kill "$CMD_PID" 2>/dev/null
      sleep 1
      kill -9 "$CMD_PID" 2>/dev/null
      wait "$CMD_PID" 2>/dev/null
      EXIT_CODE=124
      printf 'New Clawd send timed out after %s seconds\n' "$NEWCLAWD_TIMEOUT_SECONDS" >> "$STDERR_FILE"
      break
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
  done

  if [ -z "$EXIT_CODE" ]; then
    wait "$CMD_PID"
    EXIT_CODE=$?
  fi
fi

if [ "$EXIT_CODE" -eq 0 ]; then
  cat "$STDOUT_FILE"
  exit 0
fi

STDOUT_TEXT="$(cat "$STDOUT_FILE")"
STDERR_TEXT="$(cat "$STDERR_FILE")"
write_fallback_log "$EXIT_CODE" "$STDOUT_TEXT" "$STDERR_TEXT"

if [ -n "$STDOUT_TEXT" ]; then
  printf '%s\n' "$STDOUT_TEXT"
fi
if [ -n "$STDERR_TEXT" ]; then
  printf '%s\n' "$STDERR_TEXT" >&2
fi

exit 0
