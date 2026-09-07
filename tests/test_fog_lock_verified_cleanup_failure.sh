#!/usr/bin/env bash
# 驗證完整 identity 建立後，cleanup 查詢失敗不得退化成 PID-only 刪鎖或成功狀態。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-fog-lock-cleanup-failure.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs"
cp "$PROJECT_ROOT/scripts/run_fog_research_worker.sh" "$TEST_ROOT/scripts/run_fog_research_worker.sh"

FAKE_PS="$TEST_ROOT/fake-ps"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'count_file="${TOP10_TEST_PS_COUNT_FILE:?}"' \
  'count=0' \
  '[ ! -f "$count_file" ] || count="$(cat "$count_file")"' \
  'count=$((count + 1))' \
  'printf "%s\n" "$count" > "$count_file"' \
  '[ "$count" -le 2 ] || exit 1' \
  'pid="${@: -1}"' \
  'printf "token-%s\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

FAKE_PYTHON="$TEST_ROOT/fake-python"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'if [ "${1:-}" = "scripts/fog_runtime_time_authority.py" ]; then' \
  '  while [ "$#" -gt 0 ]; do' \
  '    if [ "$1" = "--field" ]; then' \
  '      case "${2:-}" in' \
  '        market_run_date) printf "%s\n" "2099-01-03" ;;' \
  '        run_context_created_at_utc) printf "%s\n" "2099-01-03T00:00:00Z" ;;' \
  '      esac' \
  '      exit 0' \
  '    fi' \
  '    shift' \
  '  done' \
  'fi' \
  'exit 0' > "$FAKE_PYTHON"
chmod +x "$FAKE_PYTHON"

set +e
TOP10_DAILY_PYTHON="$FAKE_PYTHON" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_TEST_PS_COUNT_FILE="$TEST_ROOT/ps-count" \
TOP10_FOG_RESEARCH_MAX_BATCHES=1 \
TOP10_FOG_RESEARCH_BATCH_SLEEP_SECONDS=0 \
TOP10_REPLAY_DRAIN_ENABLED=0 \
TOP10_RESEARCH_QUEUE_OWNER=fog_worker \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh" >/dev/null 2>&1
worker_status=$?
set -e

test "$worker_status" -eq 70
test -d "$TEST_ROOT/logs/fog_research_worker.lock"
test -d "$TEST_ROOT/logs/research_queue_owner.lock"
test -s "$TEST_ROOT/logs/fog_research_worker.lock/start_token"
test -s "$TEST_ROOT/logs/research_queue_owner.lock/start_token"
