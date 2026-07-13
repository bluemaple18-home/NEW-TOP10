#!/usr/bin/env bash
# 驗證 PM 遇到存活的 fog queue ownership lock 時只會跳過，不得清理對方 lock。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-research-lock.XXXXXX")"
cleanup() {
  local status=$?
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/logs/research_queue_owner.lock"
cp "$PROJECT_ROOT/scripts/run_pm_research_harness_loop.sh" "$TEST_ROOT/scripts/run_pm_research_harness_loop.sh"
printf '%s\n' "$$" > "$TEST_ROOT/logs/research_queue_owner.lock/pid"
printf '%s\n' "fog_worker" > "$TEST_ROOT/logs/research_queue_owner.lock/owner"

TOP10_PM_RESEARCH_ENABLED=1 \
TOP10_RESEARCH_QUEUE_OWNER=pm_research_harness \
TOP10_PM_RESEARCH_DATE=2099-01-03 \
bash "$TEST_ROOT/scripts/run_pm_research_harness_loop.sh"

test -d "$TEST_ROOT/logs/research_queue_owner.lock"
test "$(cat "$TEST_ROOT/logs/research_queue_owner.lock/pid")" = "$$"
test "$(cat "$TEST_ROOT/logs/research_queue_owner.lock/owner")" = "fog_worker"
