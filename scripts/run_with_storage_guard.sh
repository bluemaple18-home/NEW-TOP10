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

exec "$PYTHON_BIN" scripts/storage_safety.py run --job "$JOB" -- "$@"
