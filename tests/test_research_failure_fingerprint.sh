#!/usr/bin/env bash
# 驗證 retry fingerprint 不會取用目前 batch 之前的舊 handoff 失敗紀錄。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-research-fingerprint.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

RUN_DATE="2099-01-04"
LOG_FILE="$TEST_ROOT/logs/fog_research_worker_20990104.log"
mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs"
cp "$PROJECT_ROOT/scripts/run_fog_research_worker.sh" "$TEST_ROOT/scripts/run_fog_research_worker.sh"
printf '%s\n' 'TOP10_FOG_MAP_HANDOFF_FAILED run_date=2099-01-03 error=stale-prior-batch' > "$LOG_FILE"

TOP10_DAILY_PYTHON=/bin/false \
TOP10_RUN_DATE="$RUN_DATE" \
TOP10_FOG_RESEARCH_MAX_BATCHES=1 \
TOP10_FOG_RESEARCH_MAX_RETRIES=1 \
TOP10_FOG_RESEARCH_RETRY_BACKOFF_SECONDS=0 \
TOP10_REPLAY_DRAIN_ENABLED=0 \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"

STATE_FILE="$TEST_ROOT/logs/fog_research_retry_20990104.state"
LAST_EXIT_CODE="$(sed -n 's/^last_exit_code=//p' "$STATE_FILE")"
EXPECTED_FINGERPRINT="$(printf 'fog_map_handoff_exit_%s' "$LAST_EXIT_CODE" | shasum -a 256 | awk '{print $1}')"
ACTUAL_FINGERPRINT="$(sed -n 's/^fingerprint=//p' "$STATE_FILE")"

test "$ACTUAL_FINGERPRINT" = "$EXPECTED_FINGERPRINT"
if grep -q 'stale-prior-batch' "$TEST_ROOT/logs/fog_research_retry_20990104.context.log"; then
  exit 1
fi
