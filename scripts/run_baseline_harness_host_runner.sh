#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

RUN_DATE="${TOP10_RUN_DATE:-$(date +%F)}"
exec "$PYTHON_BIN" scripts/run_baseline_harness_host_runner.py --date "$RUN_DATE"
