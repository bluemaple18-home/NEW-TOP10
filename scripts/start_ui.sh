#!/bin/bash
# 兼容 README 的本地 UI 啟動入口。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/start_market_ui.sh"
