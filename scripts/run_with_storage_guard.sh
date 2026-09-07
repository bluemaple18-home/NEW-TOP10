#!/usr/bin/env bash
# 所有 TOP10 排程的 fail-closed 容量入口；實際命令由 Python guard 監控。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

JOB="${1:-}"
if [ -z "$JOB" ]; then
  echo "storage guard requires a job id" >&2
  exit 64
fi
shift

case "$JOB" in
  daily|retrain|reference|fog-research-worker|pm-research-harness|external-review|external-review-preflight|baseline-harness)
    ;;
  *)
    echo "storage guard rejects unknown job: $JOB" >&2
    exit 64
    ;;
esac

if [ "$#" -eq 0 ]; then
  echo "storage guard requires a child command" >&2
  exit 64
fi

# launchd 直接啟動時 parent 是 PID 1；caller env 不得自述 natural。
# manual kickstart 仍與自然 fire 同為 PID 1，所以 receipt 只記 origin candidate，
# natural acceptance 必須由外部 cadence verifier 完成。
if [ "$PPID" -eq 1 ]; then
  TRIGGER_TYPE="natural"
else
  TRIGGER_TYPE="manual"
fi
INVOCATION_STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
if [ "$JOB" = "fog-research-worker" ]; then
  # Fog acceptance metadata 只能由共同 wrapper 產生，不能沿用 caller／child 自述。
  SCHEDULED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  INVOCATION_ID="${JOB}-${INVOCATION_STAMP}-$$"
else
  # 其他既有排程仍保留 scheduler fixture／replay 所需的 override 契約。
  SCHEDULED_AT="${TOP10_STORAGE_SCHEDULED_AT:-$(date -u '+%Y-%m-%dT%H:%M:%SZ')}"
  INVOCATION_ID="${TOP10_STORAGE_INVOCATION_ID:-${JOB}-${INVOCATION_STAMP}-$$}"
fi
export TOP10_STORAGE_JOB="$JOB"
export TOP10_STORAGE_SCHEDULED_AT="$SCHEDULED_AT"
export TOP10_STORAGE_INVOCATION_ID="$INVOCATION_ID"

# 將 child 的暫存與下載型 cache 收斂到可量測的專案路徑；不改寫 HOME，
# 也不讓 uv、Matplotlib 或 joblib 把排程產物散落到其他專案／使用者 cache。
TOP10_STORAGE_RUNTIME_ROOT="$PROJECT_DIR/logs/storage_safety/runtime/$JOB"
mkdir -p \
  "$TOP10_STORAGE_RUNTIME_ROOT/tmp/joblib" \
  "$TOP10_STORAGE_RUNTIME_ROOT/cache/uv" \
  "$TOP10_STORAGE_RUNTIME_ROOT/cache/xdg" \
  "$TOP10_STORAGE_RUNTIME_ROOT/cache/matplotlib"
export TMPDIR="$TOP10_STORAGE_RUNTIME_ROOT/tmp"
export UV_CACHE_DIR="$TOP10_STORAGE_RUNTIME_ROOT/cache/uv"
export XDG_CACHE_HOME="$TOP10_STORAGE_RUNTIME_ROOT/cache/xdg"
export MPLCONFIGDIR="$TOP10_STORAGE_RUNTIME_ROOT/cache/matplotlib"
export JOBLIB_TEMP_FOLDER="$TOP10_STORAGE_RUNTIME_ROOT/tmp/joblib"
export PYTHONDONTWRITEBYTECODE=1

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "storage guard requires executable .venv/bin/python" >&2
  exit 69
fi

exec "$PYTHON_BIN" scripts/storage_safety.py run \
  --job "$JOB" \
  --trigger-type "$TRIGGER_TYPE" \
  --scheduled-at "$SCHEDULED_AT" \
  --invocation-id "$INVOCATION_ID" \
  -- "$@"
