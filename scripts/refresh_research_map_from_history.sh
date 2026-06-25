#!/usr/bin/env bash
# 從 run_history.jsonl 重建 progress 與 fog map latest JSON。
# 給訓練 runner 每 10 組 flush 後呼叫；不跑訓練、不改 production ranking。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${TOP10_RESEARCH_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
RUN_DATE="${TOP10_RESEARCH_DATE:-$(date +%F)}"

"$PYTHON_BIN" scripts/build_research_campaign_progress.py --date "$RUN_DATE"
"$PYTHON_BIN" scripts/build_research_fog_map.py --date "$RUN_DATE"

# Fog map verification depends on burn-down totals from the controlled-grid
# linkage rollup. Rebuild that linkage after the preliminary map refresh so
# inventory/queue/rollup use the latest run_history and topic registry before
# the final map verification.
if [ -f scripts/run_controlled_grid_drain_host_runner.py ]; then
  "$PYTHON_BIN" scripts/run_controlled_grid_drain_host_runner.py --date "$RUN_DATE"
else
  "$PYTHON_BIN" scripts/verify_research_fog_map.py --date "$RUN_DATE"
fi
