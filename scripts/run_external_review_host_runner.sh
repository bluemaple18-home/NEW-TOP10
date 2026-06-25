#!/bin/bash
# 收盤後外部 review host runner：daily OK 後產 packet，交由 provider adapter 收 raw，再回 repo 驗證。

set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

PYTHON_BIN="${TOP10_DAILY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
RUNNER_CMD=()
if [ -x "$PYTHON_BIN" ]; then
  RUNNER_CMD=("$PYTHON_BIN")
  RUNTIME_LABEL="$PYTHON_BIN"
else
  UV_BIN="${UV_BIN:-$(command -v uv 2>/dev/null || true)}"
  if [ -z "$UV_BIN" ]; then
    echo "python runtime not found; expected $PYTHON_BIN or set UV_BIN"
    exit 127
  fi
  RUNNER_CMD=("$UV_BIN" run --with-requirements requirements.txt python)
  RUNTIME_LABEL="$UV_BIN run --with-requirements requirements.txt python"
fi

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
RUN_DATE="${TOP10_RUN_DATE:-$(date +%F)}"
LOG_FILE="$LOG_DIR/external_review_host_runner_$(date +%Y%m%d).log"
LOCK_DIR="$LOG_DIR/external_review_host_runner.lock"
LOCK_PID_FILE="$LOCK_DIR/pid"

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    trap 'rm -f "$LOCK_PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
    return 0
  fi

  EXISTING_PID=""
  if [ -r "$LOCK_PID_FILE" ]; then
    EXISTING_PID="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  fi
  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "external review host runner skipped; existing pid=$EXISTING_PID lock=$LOCK_DIR" | tee -a "$LOG_FILE"
    exit 0
  fi

  rm -f "$LOCK_PID_FILE"
  if rmdir "$LOCK_DIR" 2>/dev/null && mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    trap 'rm -f "$LOCK_PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
    return 0
  fi

  echo "external review host runner skipped; cannot acquire lock=$LOCK_DIR" | tee -a "$LOG_FILE"
  exit 0
}

acquire_lock

ARGS=(
  scripts/run_external_review_host_runner.py
  --date "$RUN_DATE"
  --wait-daily-ok-seconds "${TOP10_EXTERNAL_REVIEW_WAIT_DAILY_OK_SECONDS:-3600}"
  --poll-seconds "${TOP10_EXTERNAL_REVIEW_POLL_SECONDS:-60}"
)

PROVIDER_MODE="${TOP10_EXTERNAL_REVIEW_PROVIDER_MODE:-browser}"
ARGS+=(--provider-mode "$PROVIDER_MODE")

if [ "${TOP10_EXTERNAL_REVIEW_DRY_RUN_PROVIDER_API:-0}" = "1" ]; then
  ARGS+=(--dry-run-provider-api)
fi

CHATGPT_URL_PART="${TOP10_CHATGPT_URL_PART:-chatgpt.com/g/g-p-6a1ff7db268881918957ff493f2a915b/c/6a38ae69-0660-83ee-91ff-1777ae00688f}"
GEMINI_URL_PART="${TOP10_GEMINI_URL_PART:-gemini.google.com/app/ea58b54eef550ded}"
export TOP10_CHATGPT_URL_PART="$CHATGPT_URL_PART"
export TOP10_GEMINI_URL_PART="$GEMINI_URL_PART"

if [ "${TOP10_EXTERNAL_REVIEW_SKIP_PROVIDER_SUBMIT:-0}" = "1" ]; then
  ARGS+=(--skip-provider-submit)
fi

if [ "${TOP10_EXTERNAL_REVIEW_ALLOW_EXISTING_DAILY_ARTIFACTS:-0}" = "1" ]; then
  ARGS+=(--allow-existing-daily-artifacts)
fi

if [ "${TOP10_SKIP_FOG_MAP_HANDOFF:-0}" = "1" ]; then
  ARGS+=(--skip-fog-map-handoff)
fi

if [ "${TOP10_SKIP_RESEARCH_QUOTA:-0}" = "1" ]; then
  ARGS+=(--skip-research-quota)
fi

echo "========================================" | tee -a "$LOG_FILE"
echo "external review host runner start - $(date)" | tee -a "$LOG_FILE"
echo "run_date: $RUN_DATE" | tee -a "$LOG_FILE"
echo "runtime: $RUNTIME_LABEL" | tee -a "$LOG_FILE"
echo "provider_mode: $PROVIDER_MODE" | tee -a "$LOG_FILE"
echo "dry_run_provider_api: ${TOP10_EXTERNAL_REVIEW_DRY_RUN_PROVIDER_API:-0}" | tee -a "$LOG_FILE"
echo "skip_provider_submit: ${TOP10_EXTERNAL_REVIEW_SKIP_PROVIDER_SUBMIT:-0}" | tee -a "$LOG_FILE"
echo "allow_existing_daily_artifacts: ${TOP10_EXTERNAL_REVIEW_ALLOW_EXISTING_DAILY_ARTIFACTS:-0}" | tee -a "$LOG_FILE"
echo "skip_fog_map_handoff: ${TOP10_SKIP_FOG_MAP_HANDOFF:-0}" | tee -a "$LOG_FILE"
echo "skip_research_quota: ${TOP10_SKIP_RESEARCH_QUOTA:-0}" | tee -a "$LOG_FILE"
echo "chatgpt_url_part: $CHATGPT_URL_PART" | tee -a "$LOG_FILE"
echo "gemini_url_part: $GEMINI_URL_PART" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
"${RUNNER_CMD[@]}" "${ARGS[@]}" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "external review host runner finished - $(date)" | tee -a "$LOG_FILE"
else
  echo "external review host runner failed - $(date) exit_code=$EXIT_CODE" | tee -a "$LOG_FILE"
fi

exit "$EXIT_CODE"
