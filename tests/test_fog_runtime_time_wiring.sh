#!/usr/bin/env bash
# 驗證 shell／plist 只傳遞 immutable context，host TZ 不成為日期 authority。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-fog-time-wiring.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

cd "$PROJECT_ROOT"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

for zone in UTC Asia/Taipei America/Los_Angeles; do
  context="$TEST_ROOT/context-${zone//\//-}.json"
  TZ="$zone" "$PYTHON_BIN" scripts/fog_runtime_time_authority.py \
    --instant-utc 2026-07-27T16:30:00Z \
    --output "$context" > /dev/null
  identity="$(TZ="$zone" "$PYTHON_BIN" scripts/fog_runtime_time_authority.py \
    --context "$context" \
    --field market_run_date)"
  test "$identity" = "2026-07-28"
done

"$PYTHON_BIN" scripts/fog_runtime_time_authority.py \
  --instant-utc 2026-07-28T15:59:59.999999Z \
  --output "$TEST_ROOT/before-midnight.json" > /dev/null
"$PYTHON_BIN" scripts/fog_runtime_time_authority.py \
  --instant-utc 2026-07-28T16:00:00Z \
  --output "$TEST_ROOT/after-midnight.json" > /dev/null
before="$("$PYTHON_BIN" scripts/fog_runtime_time_authority.py \
  --context "$TEST_ROOT/before-midnight.json" --field market_run_date)"
after="$("$PYTHON_BIN" scripts/fog_runtime_time_authority.py \
  --context "$TEST_ROOT/after-midnight.json" --field market_run_date)"
test "$before" = "2026-07-28"
test "$after" = "2026-07-29"

if TOP10_RESEARCH_PYTHON="$PYTHON_BIN" \
  TOP10_FOG_RUN_CONTEXT="$TEST_ROOT/context-UTC.json" \
  TOP10_RESEARCH_DATE="2026-07-27" \
  bash scripts/run_daily_research_quota.sh > "$TEST_ROOT/legacy-mismatch.log" 2>&1; then
  echo "legacy date mismatch was accepted" >&2
  exit 1
fi
grep -q 'TOP10_RESEARCH_DATE mismatches immutable time context' \
  "$TEST_ROOT/legacy-mismatch.log"

if grep -Eq 'date[[:space:]]+\+%F' \
  scripts/run_fog_research_worker.sh \
  scripts/run_daily_research_quota.sh; then
  echo "unbound date +%F authority fallback remains" >&2
  exit 1
fi

grep -q 'TOP10_FOG_RUN_CONTEXT' scripts/run_fog_research_worker.sh
grep -q 'TOP10_FOG_RUN_CONTEXT' scripts/run_daily_research_quota.sh
grep -q 'TOP10_RUN_DATE mismatches immutable context' scripts/run_fog_research_worker.sh
grep -q 'TOP10_RESEARCH_DATE mismatches immutable time context' scripts/run_daily_research_quota.sh
grep -q 'TOP10_RESEARCH_BASELINE_DIR' scripts/run_daily_research_quota.sh
grep -q -- '--baseline-dir "$BASELINE_DIR"' scripts/run_daily_research_quota.sh
grep -q 'TOP10_RESEARCH_DEVELOPMENT_SCREEN_ENABLED:-1' scripts/run_daily_research_quota.sh
grep -q -- '--development-screen-on-sealed-exhaustion' scripts/run_daily_research_quota.sh
grep -q -- '--development-screen-topic-count "$DEVELOPMENT_SCREEN_TOPIC_COUNT"' scripts/run_daily_research_quota.sh
grep -q 'TOP10_RESEARCH_FROM_QUEUE:-0' scripts/run_fog_research_worker.sh
grep -q 'TOPIC_SUPPLY_EXHAUSTED' scripts/run_fog_research_worker.sh

if grep -Eq '<key>(TZ|TOP10_RUN_DATE|TOP10_RESEARCH_DATE|TOP10_.*(FRESH|AGE|TIMEZONE))</key>' \
  scripts/com.new-top10.fog-research-worker.plist; then
  echo "plist injects date/timezone/freshness authority" >&2
  exit 1
fi

test "$(grep -c '<string>fog_worker</string>' scripts/com.new-top10.fog-research-worker.plist)" -eq 1
