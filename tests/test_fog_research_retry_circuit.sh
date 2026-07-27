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
CANONICAL_BASELINE="artifacts/autonomous_research/fog_production_hash_baseline_${RUN_DATE}.json"
mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs" "$TEST_ROOT/artifacts/autonomous_research"
cp "$PROJECT_ROOT/scripts/run_fog_research_worker.sh" "$TEST_ROOT/scripts/run_fog_research_worker.sh"
cat > "$TEST_ROOT/fake_python.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
script="${1:-}"
shift || true
case "$script" in
  scripts/verify_fog_closed_regime_recovery.py)
    baseline=""
    for ((index=1; index <= $#; index++)); do
      if [ "${!index}" = "--production-hash-baseline" ]; then
        next=$((index + 1))
        baseline="${!next}"
      fi
    done
    [ "$baseline" = "artifacts/autonomous_research/fog_production_hash_baseline_2099-01-06.json" ] || exit 9
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
printf '{"fixture":true}\n' > "$TEST_ROOT/$CANONICAL_BASELINE"

write_open_state() {
  cat > "$STATE_FILE" <<'STATE'
fingerprint=old-fingerprint
attempts=3
last_exit_code=1
circuit_open=1
STATE
  printf '%s\n' 'old failure context' > "$CONTEXT_FILE"
}

write_open_state
TOP10_DAILY_PYTHON="$TEST_ROOT/fake_python.sh" \
TOP10_RUN_DATE="$RUN_DATE" \
TOP10_REPLAY_DRAIN_ENABLED=0 \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"
grep -qx 'circuit_open=1' "$STATE_FILE"
test "$(sed -n 's/^fingerprint=//p' "$STATE_FILE")" = "old-fingerprint"

write_open_state
TOP10_DAILY_PYTHON="$TEST_ROOT/fake_python.sh" \
TOP10_RUN_DATE="$RUN_DATE" \
TOP10_FOG_RESEARCH_RECOVER_CIRCUIT=1 \
TOP10_FOG_PRODUCTION_HASH_BASELINE="$TEST_ROOT/production-baseline.json" \
TOP10_FOG_PRODUCTION_SOURCE_IDENTITY="fixture-source" \
TOP10_REPLAY_DRAIN_ENABLED=0 \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"
grep -qx 'circuit_open=1' "$STATE_FILE"
test "$(sed -n 's/^fingerprint=//p' "$STATE_FILE")" = "old-fingerprint"

write_open_state
FAKE_VERIFY_OK=1 \
TOP10_DAILY_PYTHON="$TEST_ROOT/fake_python.sh" \
TOP10_RUN_DATE="$RUN_DATE" \
TOP10_FOG_RESEARCH_RECOVER_CIRCUIT=1 \
TOP10_FOG_PRODUCTION_HASH_BASELINE="$TEST_ROOT/production-baseline.json" \
TOP10_FOG_PRODUCTION_SOURCE_IDENTITY="fixture-source" \
TOP10_FOG_RESEARCH_MAX_BATCHES=1 \
TOP10_FOG_RESEARCH_MAX_RETRIES=1 \
TOP10_FOG_RESEARCH_RETRY_BACKOFF_SECONDS=0 \
TOP10_REPLAY_DRAIN_ENABLED=0 \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"
test -n "$(find "$TEST_ROOT/logs" -name 'fog_research_retry_20990106.state.recovered.*' -print -quit)"
grep -qx 'circuit_open=1' "$STATE_FILE"
test "$(sed -n 's/^fingerprint=//p' "$STATE_FILE")" != "old-fingerprint"
