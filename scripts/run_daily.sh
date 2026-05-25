#!/bin/bash
# NEW-TOP10 每日自動執行腳本
# 執行時間: 每日 22:00
# 功能: ETL 資料更新 + 選股推論

set -e  # setup 階段遇到錯誤立即停止

# 切換到專案目錄
cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

# 日誌目錄
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_$(date +%Y%m%d).log"
WRAPPER_STARTED_AT_EPOCH="$(date +%s)"

echo "========================================" | tee -a "$LOG_FILE"
echo "🚀 開始每日自動執行 - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
uv run --with-requirements requirements.txt python -m scripts.run_automation daily >> "$LOG_FILE" 2>&1
RUN_EXIT_CODE=$?
set -e

STATUS_PATH="$PROJECT_DIR/artifacts/automation_status.json"

# 完成
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
if [ "$RUN_EXIT_CODE" -eq 0 ]; then
  echo "✨ 每日流程結束 - $(date)" | tee -a "$LOG_FILE"
else
  echo "❌ 每日流程失敗 - $(date) exit_code=$RUN_EXIT_CODE" | tee -a "$LOG_FILE"
fi

set +e
STATUS_OUTPUT="$(uv run --with-requirements requirements.txt python scripts/print_daily_status.py --status "$STATUS_PATH" --min-started-at-epoch "$WRAPPER_STARTED_AT_EPOCH" 2>&1)"
STATUS_EXIT_CODE=$?
set -e

if [ "$STATUS_EXIT_CODE" -eq 0 ]; then
  echo "$STATUS_OUTPUT" | tee -a "$LOG_FILE"
else
  echo "📄 每日狀態: $STATUS_PATH" | tee -a "$LOG_FILE"
  echo "$STATUS_OUTPUT" | tee -a "$LOG_FILE"
  echo "⚠️ 無法讀取每日狀態；請查看 log 內 run_automation 輸出。" | tee -a "$LOG_FILE"
fi
echo "========================================" | tee -a "$LOG_FILE"

exit "$RUN_EXIT_CODE"
