#!/usr/bin/env bash
# 驗證 retry circuit 只能在 verifier 通過後由明確 recovery mode 輪替。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-retry-circuit.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

RUN_DATE="2099-01-06"
STATE_FILE="$TEST_ROOT/logs/fog_research_retry_20990106.state"
CONTEXT_FILE="$TEST_ROOT/logs/fog_research_retry_20990106.context.log"
mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs"
cp "$PROJECT_ROOT/scripts/run_fog_research_worker.sh" "$TEST_ROOT/scripts/run_fog_research_worker.sh"

FAKE_PS="$TEST_ROOT/fake-ps"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'pid="${@: -1}"' \
  'printf "token-%s\\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

cat > "$TEST_ROOT/fake_python.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
script="${1:-}"
shift || true
case "$script" in
  scripts/fog_runtime_time_authority.py)
    output=""
    field=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --output)
          shift
          output="$1"
          ;;
        --field)
          shift
          field="$1"
          ;;
      esac
      shift || true
    done
    if [ "${FAKE_CONTEXT_OK:-1}" != "1" ]; then
      exit 9
    fi
    if [ -n "$output" ]; then
      printf '%s\n' '{"schema_version":"fog-runtime-run-context.v1"}' > "$output"
    fi
    case "$field" in
      market_run_date)
        printf '%s\n' '2099-01-06'
        ;;
      run_context_created_at_utc)
        printf '%s\n' '2099-01-05T16:30:00Z'
        ;;
    esac
    exit 0
    ;;
  scripts/verify_weekend_universe_inventory.py)
    if [ "${FAKE_VERIFY_OK:-0}" = "1" ]; then
      output=""
      while [ "$#" -gt 0 ]; do
        if [ "$1" = "--output" ]; then
          shift
          output="$1"
        fi
        shift || true
      done
      [ -n "$output" ] && printf '{"status":"OK"}\n' > "$output"
      exit 0
    fi
    exit 2
    ;;
  scripts/run_top10_fog_map_handoff.py)
    echo "handoff failed in test"
    exit 7
    ;;
  scripts/build_top10_agent_status_rollup.py)
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
SH
chmod +x "$TEST_ROOT/fake_python.sh"

write_open_state() {
  cat > "$STATE_FILE" <<'STATE'
fingerprint=old-fingerprint
attempts=3
last_exit_code=1
circuit_open=1
STATE
  printf '%s\n' 'old failure context' > "$CONTEXT_FILE"
}

FOREIGN_CONTEXT="$TEST_ROOT/logs/fog_runtime_run_context.foreign"
printf '%s\n' '{"foreign":true}' > "$FOREIGN_CONTEXT"

write_open_state
TOP10_DAILY_PYTHON="$TEST_ROOT/fake_python.sh" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_RUN_DATE="$RUN_DATE" \
TOP10_REPLAY_DRAIN_ENABLED=0 \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"
grep -qx 'circuit_open=1' "$STATE_FILE"
test "$(sed -n 's/^fingerprint=//p' "$STATE_FILE")" = "old-fingerprint"
test -f "$FOREIGN_CONTEXT"
test -z "$(find "$TEST_ROOT/logs" -name 'fog_runtime_run_context.*' ! -name 'fog_runtime_run_context.foreign' -print -quit)"

write_open_state
TOP10_DAILY_PYTHON="$TEST_ROOT/fake_python.sh" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_RUN_DATE="$RUN_DATE" \
TOP10_FOG_RESEARCH_RECOVER_CIRCUIT=1 \
TOP10_REPLAY_DRAIN_ENABLED=0 \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"
grep -qx 'circuit_open=1' "$STATE_FILE"
test "$(sed -n 's/^fingerprint=//p' "$STATE_FILE")" = "old-fingerprint"
test -f "$FOREIGN_CONTEXT"
test -z "$(find "$TEST_ROOT/logs" -name 'fog_runtime_run_context.*' ! -name 'fog_runtime_run_context.foreign' -print -quit)"

write_open_state
FAKE_VERIFY_OK=1 \
TOP10_DAILY_PYTHON="$TEST_ROOT/fake_python.sh" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_RUN_DATE="$RUN_DATE" \
TOP10_FOG_RESEARCH_RECOVER_CIRCUIT=1 \
TOP10_FOG_RESEARCH_MAX_BATCHES=1 \
TOP10_FOG_RESEARCH_MAX_RETRIES=1 \
TOP10_FOG_RESEARCH_RETRY_BACKOFF_SECONDS=0 \
TOP10_REPLAY_DRAIN_ENABLED=0 \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"
test -n "$(find "$TEST_ROOT/logs" -name 'fog_research_retry_20990106.state.recovered.*' -print -quit)"
grep -qx 'circuit_open=1' "$STATE_FILE"
test "$(sed -n 's/^fingerprint=//p' "$STATE_FILE")" != "old-fingerprint"
test -f "$FOREIGN_CONTEXT"
test -z "$(find "$TEST_ROOT/logs" -name 'fog_runtime_run_context.*' ! -name 'fog_runtime_run_context.foreign' -print -quit)"

if FAKE_CONTEXT_OK=0 \
  TOP10_DAILY_PYTHON="$TEST_ROOT/fake_python.sh" \
  TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
  TOP10_RUN_DATE="$RUN_DATE" \
  TOP10_REPLAY_DRAIN_ENABLED=0 \
  bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"; then
  echo "context creation failure unexpectedly succeeded" >&2
  exit 1
fi
test -f "$FOREIGN_CONTEXT"
test -z "$(find "$TEST_ROOT/logs" -name 'fog_runtime_run_context.*' ! -name 'fog_runtime_run_context.foreign' -print -quit)"
