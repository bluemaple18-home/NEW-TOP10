#!/bin/bash
# 安裝本機 Web UI launchd agent。此腳本只設定看盤 UI，不設定每日資料排程。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
WEBUI_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.webui.plist"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$PROJECT_DIR/logs"

sed \
  -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
  -e "s|__HOME_DIR__|$HOME|g" \
  "$PROJECT_DIR/scripts/com.new-top10.webui.plist" > "$WEBUI_PLIST"

launchctl unload "$WEBUI_PLIST" 2>/dev/null || true
launchctl load "$WEBUI_PLIST"

echo "WEBUI_LAUNCHD_OK plist=$WEBUI_PLIST"
echo "frontend=http://127.0.0.1:${TOP10_FRONTEND_PORT:-5173}"
echo "api=http://127.0.0.1:${TOP10_API_PORT:-8001}"
