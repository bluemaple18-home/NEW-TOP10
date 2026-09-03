#!/usr/bin/env bash
# 驗證 Fog lock identity 第二段寫入失敗時，不會留下 pid-only／empty-token 半鎖。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/top10-fog-lock-partial-write.XXXXXX")"
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
  'pid="${@: -1}"' \
  'printf "token-%s\\n" "$pid"' > "$FAKE_PS"
chmod +x "$FAKE_PS"

# 非互動 bash 會載入 BASH_ENV；只讓 lock start token 那次 printf 失敗。
BASH_ENV_FILE="$TEST_ROOT/bash-env"
printf '%s\n' \
  'printf() {' \
  '  case "${2:-}" in' \
  '    token-*) return 1 ;;' \
  '  esac' \
  '  builtin printf "$@"' \
  '}' > "$BASH_ENV_FILE"

BASH_ENV="$BASH_ENV_FILE" \
TOP10_PROCESS_IDENTITY_PS_BIN="$FAKE_PS" \
TOP10_RESEARCH_QUEUE_OWNER=fog_worker \
bash "$TEST_ROOT/scripts/run_fog_research_worker.sh"

test ! -e "$TEST_ROOT/logs/fog_research_worker.lock"
