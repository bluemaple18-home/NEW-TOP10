#!/usr/bin/env bash
# 驗證 lock 不能只靠存活 PID 判定 ownership；PID identity 不符時應安全回收。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-research-lock-identity.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs/research_queue_owner.lock"
cp "$PROJECT_ROOT/scripts/run_pm_research_harness_loop.sh" "$TEST_ROOT/scripts/run_pm_research_harness_loop.sh"

# 使用本測試 shell 的存活 PID，但刻意放入不可能相符的 start token。
printf '%s\n' "$$" > "$TEST_ROOT/logs/research_queue_owner.lock/pid"
printf '%s\n' "fog_worker" > "$TEST_ROOT/logs/research_queue_owner.lock/owner"
printf '%s\n' "identity-mismatch" > "$TEST_ROOT/logs/research_queue_owner.lock/start_token"

FAKE_PYTHON="$TEST_ROOT/fake-python"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$FAKE_PYTHON"
chmod +x "$FAKE_PYTHON"

FAKE_PS="$TEST_ROOT/fake-ps"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'pid="${@: -1}"' \
  'printf "token-%s\\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

TOP10_PM_RESEARCH_ENABLED=1 \
TOP10_RESEARCH_QUEUE_OWNER=pm_research_harness \
TOP10_PM_RESEARCH_DATE=2099-01-03 \
TOP10_DAILY_PYTHON="$FAKE_PYTHON" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
bash "$TEST_ROOT/scripts/run_pm_research_harness_loop.sh"

# identity mismatch 不得被誤判成仍由 fog 持有；PM 應能進入實際 workflow。
grep -q 'pm research harness loop start' "$TEST_ROOT/logs/pm_research_harness_loop_20990103.log"

# 回收 stale metadata 不得對 PID 指向的活程序送 signal。
kill -0 "$$"
