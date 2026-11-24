#!/usr/bin/env bash
# 保留原 CLI；只接既有原生 MCP，不選 transport 或建立環境。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${TOP10_DAILY_PYTHON:-$SCRIPT_DIR/../.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || { echo "existing Python required" >&2; exit 127; }
exec "$PYTHON_BIN" -B "$SCRIPT_DIR/external_review_mcp_adapter.py" --provider chatgpt "$@"
