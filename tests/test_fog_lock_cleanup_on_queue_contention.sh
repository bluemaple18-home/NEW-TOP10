#!/usr/bin/env bash
# 驗證 Fog 已取得自身 lock 後若 queue ownership 阻擋，退出時仍必須釋放自身 lock。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-fog-lock-cleanup.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs/research_queue_owner.lock"
cp "$PROJECT_ROOT/scripts/run_fog_research_worker.sh" "$TEST_ROOT/scripts/run_fog_research_worker.sh"

FAKE_PS="$TEST_ROOT/fake-ps"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'pid="${@: -1}"' \
  'printf "token-%s\\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

# queue lock 由本測試 shell 真實持有，identity 完整且相符。
printf '%s\n' "$$" > "$TEST_ROOT/logs/research_queue_owner.lock/pid"
printf '%s\n' "pm_research_harness" > "$TEST_ROOT/logs/research_queue_owner.lock/owner"
printf 'token-%s\n' "$$" > "$TEST_ROOT/logs/research_queue_owner.lock/start_token"

TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_RESEARCH_QUEUE_OWNER=fog_worker \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"

# queue ownership 必須保留；Fog 自己剛拿到的 lock 必須在早退時釋放。
test -d "$TEST_ROOT/logs/research_queue_owner.lock"
test "$(cat "$TEST_ROOT/logs/research_queue_owner.lock/pid")" = "$$"
test ! -e "$TEST_ROOT/logs/fog_research_worker.lock"
kill -0 "$$"
