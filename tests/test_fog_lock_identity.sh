#!/usr/bin/env bash
# 驗證 Fog worker 自身 lock 不能只靠存活 PID 判定 ownership。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-fog-lock-identity.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs/fog_research_worker.lock"
cp "$PROJECT_ROOT/scripts/run_fog_research_worker.sh" "$TEST_ROOT/scripts/run_fog_research_worker.sh"

# PID 存活，但 start token 故意錯誤；這是可安全回收的 stale identity。
printf '%s\n' "$$" > "$TEST_ROOT/logs/fog_research_worker.lock/pid"
printf '%s\n' "identity-mismatch" > "$TEST_ROOT/logs/fog_research_worker.lock/start_token"

FAKE_PS="$TEST_ROOT/fake-ps"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'pid="${@: -1}"' \
  'printf "token-%s\\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

FAKE_PYTHON="$TEST_ROOT/fake-python"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'if [ "${1:-}" = "scripts/fog_runtime_time_authority.py" ]; then' \
  '  while [ "$#" -gt 0 ]; do' \
  '    if [ "$1" = "--field" ]; then' \
  '      case "${2:-}" in' \
  '        market_run_date) printf "%s\\n" "2099-01-03" ;;' \
  '        run_context_created_at_utc) printf "%s\\n" "2099-01-03T00:00:00Z" ;;' \
  '      esac' \
  '      exit 0' \
  '    fi' \
  '    shift' \
  '  done' \
  'fi' \
  'exit 0' > "$FAKE_PYTHON"
chmod +x "$FAKE_PYTHON"

TOP10_DAILY_PYTHON="$FAKE_PYTHON" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_FOG_RESEARCH_MAX_BATCHES=1 \
TOP10_FOG_RESEARCH_BATCH_SLEEP_SECONDS=0 \
TOP10_RESEARCH_QUEUE_OWNER=fog_worker \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"

grep -q 'fog research worker start' "$TEST_ROOT/logs/fog_research_worker_20990103.log"
kill -0 "$$"
