#!/bin/bash
# 本機手動送 PM review card 到 review-approval。
# 預設 dry-run；加 --send 才會正式送 Discord。

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/send_pm_review_card_local.sh [--send|--dry-run] <repo-relative-run-dir>

Examples:
  scripts/send_pm_review_card_local.sh artifacts/pm_review_cards/2026-07-09-clarification-resend-153020
  scripts/send_pm_review_card_local.sh --send artifacts/pm_review_cards/2026-07-09-clarification-resend-153020
USAGE
}

MODE="dry-run"
if [ "${1:-}" = "--send" ]; then
  MODE="send"
  shift
elif [ "${1:-}" = "--dry-run" ]; then
  MODE="dry-run"
  shift
fi

RUN_DIR="${1:-}"
if [ -z "$RUN_DIR" ]; then
  usage >&2
  exit 2
fi
if [[ "$RUN_DIR" = /* ]] || [[ "$RUN_DIR" == *".."* ]] || [[ "$RUN_DIR" != artifacts/pm_review_cards/* ]]; then
  echo "run_dir must be repo-relative under artifacts/pm_review_cards/: $RUN_DIR" >&2
  exit 2
fi
if [ ! -f "$PROJECT_DIR/$RUN_DIR/cards.json" ]; then
  echo "cards.json not found: $RUN_DIR/cards.json" >&2
  exit 2
fi

NODE_BIN="${TOP10_CLAWD_NODE:-/opt/homebrew/opt/node/bin/node}"
OPENCLAW_ENTRY="${TOP10_OPENCLAW_ENTRY:-$HOME/new clawd/openclaw.mjs}"
TARGET="${TOP10_REVIEW_APPROVAL_TARGET:-channel:1523986945955463188}"
DRY_RUN="true"
if [ "$MODE" = "send" ]; then
  DRY_RUN="false"
fi

PARAMS=$(printf '{"run_dir":"%s","target":"%s","dry_run":%s}' "$RUN_DIR" "$TARGET" "$DRY_RUN")

exec "$NODE_BIN" "$OPENCLAW_ENTRY" gateway call top10.pm_review.send_cards \
  --json \
  --timeout 15000 \
  --params "$PARAMS"
