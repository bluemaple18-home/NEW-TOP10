#!/bin/bash
# PM approval -> research harness -> Discord PM review card loop.
# 只跑 research-only harness，不改 ranking/model/publish。

set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

RUN_DATE="${TOP10_PM_RESEARCH_DATE:-$(date +%F)}"
ENABLED="${TOP10_PM_RESEARCH_ENABLED:-0}"
QUOTA="${TOP10_PM_RESEARCH_QUOTA:-2}"
MAX_RANKING_FILES="${TOP10_PM_RESEARCH_MAX_RANKING_FILES:-8}"
MAX_CONTINUATION_RUNS="${TOP10_PM_RESEARCH_MAX_CONTINUATION_RUNS:-8}"
MIN_QUEUE_DEPTH="${TOP10_PM_RESEARCH_MIN_QUEUE_DEPTH:-12}"
DISCOVERY_MAX_TOPICS="${TOP10_PM_RESEARCH_DISCOVERY_MAX_TOPICS:-30}"
SEND_CARDS="${TOP10_PM_RESEARCH_SEND_CARDS:-0}"
DRY_RUN_SEND="${TOP10_PM_RESEARCH_DRY_RUN_SEND:-1}"
LOG_FILE="$LOG_DIR/pm_research_harness_loop_${RUN_DATE//-/}.log"
LOCK_DIR="$LOG_DIR/pm_research_harness_loop.lock"
LOCK_PID_FILE="$LOCK_DIR/pid"
LOCK_START_TOKEN_FILE="$LOCK_DIR/start_token"
FOG_LOCK_DIR="$LOG_DIR/fog_research_worker.lock"
FOG_LOCK_PID_FILE="$FOG_LOCK_DIR/pid"
FOG_LOCK_START_TOKEN_FILE="$FOG_LOCK_DIR/start_token"
QUEUE_OWNER="${TOP10_RESEARCH_QUEUE_OWNER:-fog_worker}"
QUEUE_OWNER_LOCK_DIR="$LOG_DIR/research_queue_owner.lock"
QUEUE_OWNER_PID_FILE="$QUEUE_OWNER_LOCK_DIR/pid"
QUEUE_OWNER_NAME_FILE="$QUEUE_OWNER_LOCK_DIR/owner"
QUEUE_OWNER_START_TOKEN_FILE="$QUEUE_OWNER_LOCK_DIR/start_token"
PM_LOCK_HELD=0
QUEUE_OWNER_LOCK_HELD=0
PS_BIN="${TOP10_PROCESS_IDENTITY_PS_BIN:-/bin/ps}"

process_start_token() {
  local pid="$1"
  case "$pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  "$PS_BIN" -o lstart= -p "$pid" 2>/dev/null || true
}

write_lock_identity() {
  local pid_file="$1"
  local start_token_file="$2"
  local start_token=""
  start_token="$(process_start_token "$$")"
  if [ -z "$start_token" ]; then
    return 1
  fi
  printf '%s\n' "$$" > "$pid_file"
  printf '%s\n' "$start_token" > "$start_token_file"
}

lock_owner_state() {
  local pid_file="$1"
  local start_token_file="$2"
  local existing_pid=""
  local stored_start_token=""
  local actual_start_token=""

  if [ ! -r "$pid_file" ]; then
    printf '%s\n' "STALE"
    return 0
  fi
  existing_pid="$(cat "$pid_file" 2>/dev/null || true)"
  case "$existing_pid" in
    ''|*[!0-9]*)
      printf '%s\n' "STALE"
      return 0
      ;;
  esac
  if ! kill -0 "$existing_pid" 2>/dev/null; then
    printf '%s\n' "STALE"
    return 0
  fi
  if [ ! -r "$start_token_file" ]; then
    printf '%s\n' "UNKNOWN"
    return 0
  fi
  stored_start_token="$(cat "$start_token_file" 2>/dev/null || true)"
  actual_start_token="$(process_start_token "$existing_pid")"
  if [ -z "$stored_start_token" ] || [ -z "$actual_start_token" ]; then
    printf '%s\n' "UNKNOWN"
  elif [ "$stored_start_token" = "$actual_start_token" ]; then
    printf '%s\n' "ACTIVE"
  else
    printf '%s\n' "STALE"
  fi
}

lock_identity_is_current_process() {
  local pid_file="$1"
  local start_token_file="$2"
  local current_start_token=""
  [ -r "$pid_file" ] || return 1
  [ -r "$start_token_file" ] || return 1
  [ "$(cat "$pid_file" 2>/dev/null || true)" = "$$" ] || return 1
  current_start_token="$(process_start_token "$$")"
  [ -n "$current_start_token" ] || return 1
  [ "$(cat "$start_token_file" 2>/dev/null || true)" = "$current_start_token" ]
}

if [ "$QUEUE_OWNER" != "pm_research_harness" ]; then
  echo "pm research harness loop skipped; queue owner=$QUEUE_OWNER" >> "$LOG_FILE" 2>&1
  exit 0
fi

if [ "$ENABLED" != "1" ] && [ "$ENABLED" != "true" ] && [ "$ENABLED" != "TRUE" ]; then
  {
    echo "pm research harness loop skipped - $(date)"
    echo "reason=disabled TOP10_PM_RESEARCH_ENABLED=${TOP10_PM_RESEARCH_ENABLED:-}"
    echo "enable manually with TOP10_PM_RESEARCH_ENABLED=1 after PM approval contract is ready"
  } >> "$LOG_FILE" 2>&1
  exit 0
fi

if [ -d "$FOG_LOCK_DIR" ]; then
  fog_pid="$(cat "$FOG_LOCK_PID_FILE" 2>/dev/null || true)"
  fog_lock_state="$(lock_owner_state "$FOG_LOCK_PID_FILE" "$FOG_LOCK_START_TOKEN_FILE")"
  if [ "$fog_lock_state" = "ACTIVE" ]; then
    echo "pm research harness loop skipped; fog research worker active pid=$fog_pid" >> "$LOG_FILE" 2>&1
    exit 0
  elif [ "$fog_lock_state" = "UNKNOWN" ]; then
    echo "pm research harness loop skipped; fog research worker lock identity unverified pid=$fog_pid" >> "$LOG_FILE" 2>&1
    exit 0
  fi
fi

cleanup_locks() {
  if [ "$PM_LOCK_HELD" = "1" ] && lock_identity_is_current_process "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"; then
    rm -f "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  if [ "$QUEUE_OWNER_LOCK_HELD" = "1" ] && lock_identity_is_current_process "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"; then
    rm -f "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_NAME_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"
    rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null || true
  fi
}

acquire_queue_owner_lock() {
  if mkdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null; then
    if ! write_lock_identity "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"; then
      rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null || true
      echo "pm research harness loop skipped; cannot establish research queue lock identity" | tee -a "$LOG_FILE"
      exit 0
    fi
    echo "pm_research_harness" > "$QUEUE_OWNER_NAME_FILE"
    QUEUE_OWNER_LOCK_HELD=1
    return 0
  fi

  local existing_pid="$(cat "$QUEUE_OWNER_PID_FILE" 2>/dev/null || true)"
  local owner_state="$(lock_owner_state "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE")"
  if [ "$owner_state" = "ACTIVE" ]; then
    echo "pm research harness loop skipped; research queue owned by pid=$existing_pid" | tee -a "$LOG_FILE"
    exit 0
  elif [ "$owner_state" = "UNKNOWN" ]; then
    echo "pm research harness loop skipped; research queue lock identity unverified pid=$existing_pid" | tee -a "$LOG_FILE"
    exit 0
  fi

  rm -f "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_NAME_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"
  if rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null && mkdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null; then
    if ! write_lock_identity "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"; then
      rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null || true
      echo "pm research harness loop skipped; cannot establish research queue lock identity" | tee -a "$LOG_FILE"
      exit 0
    fi
    echo "pm_research_harness" > "$QUEUE_OWNER_NAME_FILE"
    QUEUE_OWNER_LOCK_HELD=1
    return 0
  fi

  echo "pm research harness loop skipped; cannot acquire research queue ownership" | tee -a "$LOG_FILE"
  exit 0
}

if mkdir "$LOCK_DIR" 2>/dev/null; then
  if ! write_lock_identity "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
    echo "pm research harness loop skipped; cannot establish lock identity" | tee -a "$LOG_FILE"
    exit 0
  fi
  PM_LOCK_HELD=1
else
  existing_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  owner_state="$(lock_owner_state "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE")"
  if [ "$owner_state" = "ACTIVE" ]; then
    echo "pm research harness loop skipped; existing pid=$existing_pid" | tee -a "$LOG_FILE"
    exit 0
  elif [ "$owner_state" = "UNKNOWN" ]; then
    echo "pm research harness loop skipped; lock identity unverified pid=$existing_pid" | tee -a "$LOG_FILE"
    exit 0
  fi
  rm -f "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"
  rmdir "$LOCK_DIR" 2>/dev/null || true
  mkdir "$LOCK_DIR"
  if ! write_lock_identity "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
    echo "pm research harness loop skipped; cannot establish lock identity" | tee -a "$LOG_FILE"
    exit 0
  fi
  PM_LOCK_HELD=1
fi

trap cleanup_locks EXIT INT TERM
acquire_queue_owner_lock

PYTHON_BIN="${TOP10_DAILY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

ARGS=(
  scripts/run_pm_research_harness_loop.py
  --date "$RUN_DATE"
  --quota "$QUOTA"
  --max-ranking-files "$MAX_RANKING_FILES"
  --max-continuation-runs "$MAX_CONTINUATION_RUNS"
  --min-queue-depth "$MIN_QUEUE_DEPTH"
  --discovery-max-topics "$DISCOVERY_MAX_TOPICS"
)

if [ "$SEND_CARDS" = "1" ] || [ "$SEND_CARDS" = "true" ] || [ "$SEND_CARDS" = "TRUE" ]; then
  ARGS+=(--send-cards)
fi
if [ "$DRY_RUN_SEND" = "1" ] || [ "$DRY_RUN_SEND" = "true" ] || [ "$DRY_RUN_SEND" = "TRUE" ]; then
  ARGS+=(--dry-run-send)
fi

{
  echo "========================================"
  echo "pm research harness loop start - $(date)"
  echo "run_date=$RUN_DATE enabled=$ENABLED quota=$QUOTA max_ranking_files=$MAX_RANKING_FILES max_continuation_runs=$MAX_CONTINUATION_RUNS min_queue_depth=$MIN_QUEUE_DEPTH discovery_max_topics=$DISCOVERY_MAX_TOPICS send_cards=$SEND_CARDS dry_run_send=$DRY_RUN_SEND"
  "$PYTHON_BIN" "${ARGS[@]}"
  echo "pm research harness loop finished - $(date)"
} >> "$LOG_FILE" 2>&1
