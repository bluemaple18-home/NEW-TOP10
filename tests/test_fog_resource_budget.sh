#!/usr/bin/env bash
# 驗證 Fog replay drain 的背景資源預算與明示環境覆寫契約。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
PLIST="$PROJECT_ROOT/scripts/com.new-top10.fog-research-worker.plist"

test "$(/usr/libexec/PlistBuddy -c 'Print :ProcessType' "$PLIST")" = "Background"
test "$(/usr/libexec/PlistBuddy -c 'Print :LowPriorityIO' "$PLIST")" = "true"
test "$(/usr/libexec/PlistBuddy -c 'Print :Nice' "$PLIST")" = "10"
test "$(/usr/libexec/PlistBuddy -c 'Print :StartInterval' "$PLIST")" = "3600"

grep -Fq 'REPLAY_BATCH_SIZE="${TOP10_REPLAY_DRAIN_BATCH_SIZE:-6}"' "$PROJECT_ROOT/scripts/run_fog_research_worker.sh"
grep -Fq 'REPLAY_MAX_BATCHES="${TOP10_REPLAY_DRAIN_MAX_BATCHES:-1}"' "$PROJECT_ROOT/scripts/run_fog_research_worker.sh"
grep -Fq 'REPLAY_MAX_SECONDS="${TOP10_REPLAY_DRAIN_MAX_SECONDS:-1800}"' "$PROJECT_ROOT/scripts/run_fog_research_worker.sh"
grep -Fq -- '--batch-size "$REPLAY_BATCH_SIZE"' "$PROJECT_ROOT/scripts/run_fog_research_worker.sh"
grep -Fq -- '--max-batches "$REPLAY_MAX_BATCHES"' "$PROJECT_ROOT/scripts/run_fog_research_worker.sh"
grep -Fq -- '--max-seconds "$REPLAY_MAX_SECONDS"' "$PROJECT_ROOT/scripts/run_fog_research_worker.sh"

PYTHONPATH="$PROJECT_ROOT/scripts" "$PYTHON_BIN" - <<'PY'
import os
import sys
from unittest.mock import patch

import run_representative_replay_drain_worker as worker

with patch.dict(os.environ, {}, clear=True), patch.object(sys, "argv", ["worker"]):
    defaults = worker.parse_args()
assert (defaults.batch_size, defaults.max_batches, defaults.max_seconds) == (6, 1, 1800)

with patch.dict(
    os.environ,
    {
        "TOP10_REPLAY_DRAIN_BATCH_SIZE": "9",
        "TOP10_REPLAY_DRAIN_MAX_BATCHES": "3",
        "TOP10_REPLAY_DRAIN_MAX_SECONDS": "600",
    },
    clear=True,
), patch.object(sys, "argv", ["worker"]):
    overrides = worker.parse_args()
assert (overrides.batch_size, overrides.max_batches, overrides.max_seconds) == (9, 3, 600)
PY
