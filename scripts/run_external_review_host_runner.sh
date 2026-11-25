#!/bin/bash
# 收盤後外部 review host runner：daily OK 後產 packet，交由 provider adapter 收 raw，再回 repo 驗證。

set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
# 原 browser CLI 沿既有 host AppleScript；不啟用無人 review 排程。

cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

PYTHON_BIN="${TOP10_DAILY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
# 只使用既有環境；缺 Python 時不可由 uv 建立或同步環境。
if [ ! -x "$PYTHON_BIN" ]; then
  echo "python runtime not found; expected existing executable $PYTHON_BIN" >&2
  exit 127
fi
RUNNER_CMD=("$PYTHON_BIN")
RUNTIME_LABEL="$PYTHON_BIN"

ARTIFACTS_DIR="${TOP10_EXTERNAL_REVIEW_ARTIFACTS_DIR:-$PROJECT_DIR/artifacts}"
LOG_DIR="${TOP10_EXTERNAL_REVIEW_LOG_DIR:-$PROJECT_DIR/logs}"
if [ -n "${TOP10_EXTERNAL_REVIEW_ARTIFACTS_DIR:-}" ]; then
  LOG_DIR="${TOP10_EXTERNAL_REVIEW_LOG_DIR:-$ARTIFACTS_DIR/logs}"
fi
LOCK_DIR="${TOP10_EXTERNAL_REVIEW_LOCK_DIR:-$LOG_DIR/external_review_host_runner.lock}"
RUN_DATE="${TOP10_RUN_DATE:-$(date +%F)}"
LOG_FILE="$LOG_DIR/external_review_host_runner_$(date +%Y%m%d).log"
LOCK_PID_FILE="$LOCK_DIR/pid"

if [ -n "${TOP10_EXTERNAL_REVIEW_ARTIFACTS_DIR:-}${TOP10_EXTERNAL_REVIEW_LOG_DIR:-}${TOP10_EXTERNAL_REVIEW_LOCK_DIR:-}${TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT:-}" ]; then
  # 全部路徑驗完才建立子目錄；owner admission 仍由既有 lifecycle 負責。
  if [ -z "${TOP10_EXTERNAL_REVIEW_ARTIFACTS_DIR:-}" ]; then
    echo "external review output/log/lock override requires TOP10_EXTERNAL_REVIEW_ARTIFACTS_DIR" >&2
    exit 64
  fi
  OUTPUT_ROOT="${TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT:-$ARTIFACTS_DIR/external_review}"
  "$PYTHON_BIN" -c '
import sys
from pathlib import Path
root, log, lock, output, logfile, pidfile = map(Path, sys.argv[1:])
try:
    for raw, path in zip(sys.argv[1:], (root, log, lock, output, logfile, pidfile)):
        if not path.is_absolute() or raw == "/" or str(path.resolve()) != raw:
            raise ValueError("paths must be absolute canonical paths without symlinks or traversal")
    if not root.is_dir():
        raise ValueError("artifacts root must already exist")
    if output != root / "external_review":
        raise ValueError("adapter output must equal artifacts root / external_review")
    for path in (log, lock, output, logfile, pidfile):
        if not path.is_relative_to(root) or path == root:
            raise ValueError("output/log/lock must stay inside artifacts root")
    for path in (log, lock, output):
        if path.exists() and not path.is_dir():
            raise ValueError("output/log/lock must be directories")
except (OSError, RuntimeError, ValueError) as exc:
    print("external review root rejected: " + str(exc), file=sys.stderr)
    raise SystemExit(64)
' "$ARTIFACTS_DIR" "$LOG_DIR" "$LOCK_DIR" "$OUTPUT_ROOT" "$LOG_FILE" "$LOCK_PID_FILE"
  mkdir -p "$OUTPUT_ROOT" "$(dirname "$LOCK_DIR")"
  export TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT="$OUTPUT_ROOT"
fi
mkdir -p "$LOG_DIR"

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
  --artifacts-dir "$ARTIFACTS_DIR"
  --wait-daily-ok-seconds "${TOP10_EXTERNAL_REVIEW_WAIT_DAILY_OK_SECONDS:-3600}"
  --poll-seconds "${TOP10_EXTERNAL_REVIEW_POLL_SECONDS:-60}"
  --skip-ops-report
)

PROVIDER_MODE="${TOP10_EXTERNAL_REVIEW_PROVIDER_MODE:-browser}"
ARGS+=(--provider-mode "$PROVIDER_MODE")

if [ "${TOP10_EXTERNAL_REVIEW_DRY_RUN_PROVIDER_API:-0}" = "1" ]; then
  ARGS+=(--dry-run-provider-api)
fi

CHATGPT_URL_PART="${TOP10_CHATGPT_URL_PART:-chatgpt.com/g/g-p-6a27bb719e708191bd6eefae64c7c08c-gu-piao/c/6a27bb97-8f80-8324-ab52-3f861a006ee3}"
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
