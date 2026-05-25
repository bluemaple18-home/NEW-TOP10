#!/bin/bash
# 啟動新版 K 線看盤 UI。

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

export PATH="$HOME/.local/bin:$HOME/Library/pnpm:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

API_PORT="${TOP10_API_PORT:-8001}"
FRONTEND_PORT="${TOP10_FRONTEND_PORT:-5173}"
API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:${API_PORT}}"
UV_BIN="${UV_BIN:-$(command -v uv || true)}"
PNPM_BIN="${PNPM_BIN:-$(command -v pnpm || true)}"

if [ -z "$UV_BIN" ] || [ ! -x "$UV_BIN" ]; then
  echo "找不到 uv；請確認 uv 已安裝，或設定 UV_BIN=/absolute/path/to/uv。"
  exit 1
fi

if [ -z "$PNPM_BIN" ] || [ ! -x "$PNPM_BIN" ]; then
  echo "找不到 pnpm；請確認 pnpm 已安裝，或設定 PNPM_BIN=/absolute/path/to/pnpm。"
  exit 1
fi

echo "啟動 TW Top10 Market API: http://127.0.0.1:${API_PORT}"
"$UV_BIN" run --with fastapi --with uvicorn --with pandas --with pyarrow \
  uvicorn app.api.main:app --reload --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "啟動 KLineCharts 前端: http://127.0.0.1:${FRONTEND_PORT}"
cd "$PROJECT_DIR/web/frontend"
VITE_API_BASE_URL="$API_BASE_URL" "$PNPM_BIN" dev --host 127.0.0.1 --port "$FRONTEND_PORT"
