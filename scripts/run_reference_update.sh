#!/bin/bash
# NEW-TOP10 每月 reference source 更新腳本
# 功能: 概念股 / 產業 / 供應鏈外部來源 probe + import

set -e

cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reference_$(date +%Y%m%d).log"

echo "========================================" | tee -a "$LOG_FILE"
echo "🔎 開始 reference sources 更新 - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

uv run --with-requirements requirements.txt python -m scripts.run_automation reference >> "$LOG_FILE" 2>&1

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "✨ reference sources 更新完成 - $(date)" | tee -a "$LOG_FILE"
echo "📄 匯入摘要: artifacts/reference_import_summary.json" | tee -a "$LOG_FILE"
echo "📄 source probe: artifacts/reference_source_probe.json" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
