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
  daily|retrain|retrain-monitor|reference|fog-research-worker|pm-research-harness|external-review|external-review-preflight|baseline-harness)
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

if [ "$JOB" = "retrain-monitor" ] && {
  [ "$#" -ne 5 ] ||
  [ "$1" != "/bin/bash" ] ||
  [ "$2" != "$PROJECT_DIR/scripts/daily_retrain.sh" ] ||
  [ "$3" != "monitor" ] ||
  [ "$4" != "--trigger" ] ||
  [ "$5" != "scheduled" ]
}; then
  echo "storage guard retrain-monitor requires the canonical monitor command" >&2
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

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "storage guard requires executable .venv/bin/python" >&2
  exit 69
fi

# EXIT 也涵蓋 source 內的 exit、nounset 與契約展開失敗；正常交接前移除。
# 僅傳固定 failure flag，讓原 guard 在持鎖例外路徑產生 receipt／denial。
storage_startup_failed() {
  trap - EXIT
  exec "$PYTHON_BIN" -B "$PROJECT_DIR/scripts/storage_safety.py" run \
    --job "$JOB" --trigger-type "$TRIGGER_TYPE" \
    --scheduled-at "$SCHEDULED_AT" --invocation-id "$INVOCATION_ID" \
    --startup-failure -- "$@"
}
trap 'storage_startup_failed "$@"' EXIT

# runtime 由 Python guard 在 lock、容量與外接身分准入後建立。
# 不在 guard 前覆寫 caller 的外接設定，也不提前建立內建 cache。
# 先讀無 mkdir 的環境層；缺完整映像契約時，不進入 toolchain 的 legacy mkdir 分支。
TOP10_TOOLCHAIN_ROOT="${AI_CORE_DIR:-$HOME/ai-core}"
source "$TOP10_TOOLCHAIN_ROOT/config/ai_core_env.sh"
: "${AI_CORE_CACHE_VOLUME:?storage guard requires external cache volume}"
if [ "${AI_CORE_CACHE_MODE:-image}" = "directory" ]; then
  : "${AI_CORE_CACHE_ROOT:?storage guard requires managed cache root}"
  : "${AI_CORE_CACHE_MAX_FILES:?storage guard requires aggregate file cap}"
  : "${AI_CORE_CACHE_RESERVED_OTHER_BYTES:?storage guard requires shared SR budget}"
else
  : "${AI_CORE_CACHE_IMAGE:?storage guard requires external cache image}"
  : "${AI_CORE_CACHE_BACKING_VOLUME:?storage guard requires external backing volume}"
  : "${AI_CORE_CACHE_BACKING_UUID:?storage guard requires external backing identity}"
fi
: "${AI_CORE_CACHE_VOLUME_UUID:?storage guard requires external image identity}"
: "${AI_CORE_CACHE_MAX_BYTES:?storage guard requires external image cap}"
source "$TOP10_TOOLCHAIN_ROOT/config/toolchain_paths.sh"
export PYTHONDONTWRITEBYTECODE=1
trap - EXIT

exec "$PYTHON_BIN" scripts/storage_safety.py run \
  --job "$JOB" \
  --trigger-type "$TRIGGER_TYPE" \
  --scheduled-at "$SCHEDULED_AT" \
  --invocation-id "$INVOCATION_ID" \
  -- "$@"
