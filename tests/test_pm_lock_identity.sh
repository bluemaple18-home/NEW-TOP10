#!/usr/bin/env bash
# 驗證 PM harness 自身 lock 不能只靠存活 PID 判定 ownership。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-pm-lock-identity.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs/pm_research_harness_loop.lock"
cp "$PROJECT_ROOT/scripts/run_pm_research_harness_loop.sh" "$TEST_ROOT/scripts/run_pm_research_harness_loop.sh"

printf '%s\n' "$$" > "$TEST_ROOT/logs/pm_research_harness_loop.lock/pid"
printf '%s\n' "identity-mismatch" > "$TEST_ROOT/logs/pm_research_harness_loop.lock/start_token"

FAKE_PS="$TEST_ROOT/fake-ps"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'pid="${@: -1}"' \
  'printf "token-%s\\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

FAKE_PYTHON="$TEST_ROOT/fake-python"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$FAKE_PYTHON"
chmod +x "$FAKE_PYTHON"

TOP10_PM_RESEARCH_ENABLED=1 \
TOP10_RESEARCH_QUEUE_OWNER=pm_research_harness \
TOP10_PM_RESEARCH_DATE=2099-01-03 \
TOP10_DAILY_PYTHON="$FAKE_PYTHON" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
bash "$TEST_ROOT/scripts/run_pm_research_harness_loop.sh"

grep -q 'pm research harness loop start' "$TEST_ROOT/logs/pm_research_harness_loop_20990103.log"
kill -0 "$$"
