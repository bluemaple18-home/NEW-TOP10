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
FOG_LOCK_DIR="$LOG_DIR/fog_research_worker.lock"
FOG_LOCK_PID_FILE="$FOG_LOCK_DIR/pid"

if [ "$ENABLED" != "1" ] && [ "$ENABLED" != "true" ] && [ "$ENABLED" != "TRUE" ]; then
  {
    echo "pm research harness loop skipped - $(date)"
    echo "reason=disabled TOP10_PM_RESEARCH_ENABLED=${TOP10_PM_RESEARCH_ENABLED:-}"
    echo "enable manually with TOP10_PM_RESEARCH_ENABLED=1 after PM approval contract is ready"
  } >> "$LOG_FILE" 2>&1
  exit 0
fi

if [ -r "$FOG_LOCK_PID_FILE" ]; then
  fog_pid="$(cat "$FOG_LOCK_PID_FILE" 2>/dev/null || true)"
  if [ -n "$fog_pid" ] && kill -0 "$fog_pid" 2>/dev/null; then
    echo "pm research harness loop skipped; fog research worker active pid=$fog_pid" >> "$LOG_FILE" 2>&1
    exit 0
  fi
fi

if mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "$$" > "$LOCK_PID_FILE"
  trap 'rm -f "$LOCK_PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
else
  if [ -r "$LOCK_PID_FILE" ]; then
    existing_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
      echo "pm research harness loop skipped; existing pid=$existing_pid" | tee -a "$LOG_FILE"
      exit 0
    fi
  fi
  rm -f "$LOCK_PID_FILE"
  rmdir "$LOCK_DIR" 2>/dev/null || true
  mkdir "$LOCK_DIR"
  echo "$$" > "$LOCK_PID_FILE"
  trap 'rm -f "$LOCK_PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
fi

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
