#!/usr/bin/env bash
# 驗證 Fog worker 收到 TERM 後必須終止，不能在 cleanup 釋放 ownership 後繼續執行後續步驟。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-fog-signal-teardown.XXXXXX")"
WORKER_PID=""
CHILD_PID=""
cleanup() {
  local status=$?
  if [ -n "$CHILD_PID" ]; then
    kill "$CHILD_PID" 2>/dev/null || true
  fi
  if [ -n "$WORKER_PID" ]; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs"
cp "$PROJECT_ROOT/scripts/run_fog_research_worker.sh" "$TEST_ROOT/scripts/run_fog_research_worker.sh"

FAKE_PS="$TEST_ROOT/fake-ps"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'pid="${@: -1}"' \
  'printf "token-%s\\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

FAKE_PYTHON="$TEST_ROOT/fake-python"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -euo pipefail' \
  'case "${1:-}" in' \
  '  scripts/fog_runtime_time_authority.py)' \
  '    if [ "${2:-}" = "--output" ]; then' \
  '      printf "{}\\n" > "$3"' \
  '    elif [ "${4:-}" = "--field" ] && [ "${5:-}" = "market_run_date" ]; then' \
  '      printf "2026-09-04\\n"' \
  '    else' \
  '      printf "2026-09-04T00:00:00Z\\n"' \
  '    fi' \
  '    ;;' \
  '  scripts/run_top10_fog_map_handoff.py)' \
  '    printf "%s\\n" "$$" > "$TOP10_SIGNAL_CHILD_PID_FILE"' \
  '    touch "$TOP10_SIGNAL_CHILD_STARTED_FILE"' \
  '    while :; do /bin/sleep 1; done' \
  '    ;;' \
  '  scripts/build_top10_agent_status_rollup.py)' \
  '    touch "$TOP10_SIGNAL_CONTINUED_FILE"' \
  '    ;;' \
  '  *) exit 0 ;;' \
  'esac' > "$FAKE_PYTHON"
chmod +x "$FAKE_PYTHON"

CHILD_PID_FILE="$TEST_ROOT/child.pid"
CHILD_STARTED_FILE="$TEST_ROOT/child.started"
CONTINUED_FILE="$TEST_ROOT/continued-after-term"

TOP10_DAILY_PYTHON="$FAKE_PYTHON" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_RESEARCH_QUEUE_OWNER=fog_worker \
TOP10_FOG_RESEARCH_MAX_BATCHES=1 \
TOP10_FOG_RESEARCH_MAX_RETRIES=1 \
TOP10_REPLAY_DRAIN_ENABLED=0 \
TOP10_SIGNAL_CHILD_PID_FILE="$CHILD_PID_FILE" \
TOP10_SIGNAL_CHILD_STARTED_FILE="$CHILD_STARTED_FILE" \
TOP10_SIGNAL_CONTINUED_FILE="$CONTINUED_FILE" \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh" >/dev/null 2>&1 &
WORKER_PID=$!

for _ in $(seq 1 100); do
  [ -f "$CHILD_STARTED_FILE" ] && break
  /bin/sleep 0.02
done
test -f "$CHILD_STARTED_FILE"
CHILD_PID="$(cat "$CHILD_PID_FILE")"

kill -TERM "$WORKER_PID"
/bin/sleep 0.05
kill -TERM "$CHILD_PID" 2>/dev/null || true

for _ in $(seq 1 100); do
  if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    break
  fi
  /bin/sleep 0.02
done

if kill -0 "$WORKER_PID" 2>/dev/null; then
  echo "Fog worker 收到 TERM 後仍存活" >&2
  exit 1
fi
if [ -e "$CONTINUED_FILE" ]; then
  echo "Fog worker 在 TERM cleanup 後仍執行 rollup" >&2
  exit 1
fi
test ! -e "$TEST_ROOT/logs/fog_research_worker.lock"
test ! -e "$TEST_ROOT/logs/research_queue_owner.lock"
