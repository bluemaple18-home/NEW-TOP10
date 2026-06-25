#!/bin/bash
# controlled-grid-drain 連動入口：重建 gates / rollup / fog map，不執行 replay。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${TOP10_DAILY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

RUN_DATE="${TOP10_RUN_DATE:-$(date +%F)}"
exec "$PYTHON_BIN" scripts/run_controlled_grid_drain_host_runner.py --date "$RUN_DATE"
