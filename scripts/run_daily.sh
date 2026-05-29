#!/bin/bash
# NEW-TOP10 每日自動執行腳本
# 執行時間: 每日 22:00
# 功能: ETL 資料更新 + 選股推論

set -e  # setup 階段遇到錯誤立即停止

# launchd / non-login shell 預設 PATH 很短，需明確納入 uv 常見安裝路徑。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
UV_BIN="${UV_BIN:-$(command -v uv 2>/dev/null || true)}"
if [ -z "$UV_BIN" ]; then
  echo "❌ uv command not found; set UV_BIN or install uv under $HOME/.local/bin, /opt/homebrew/bin, or /usr/local/bin"
  exit 127
fi

# 切換到專案目錄
cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

# 日誌目錄
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_$(date +%Y%m%d).log"
LOCK_DIR="$LOG_DIR/daily.lock"
LOCK_PID_FILE="$LOCK_DIR/pid"
WRAPPER_STARTED_AT_EPOCH="$(date +%s)"
TOP10_RESOURCE_PROFILE="${TOP10_RESOURCE_PROFILE:-standard}"
export TOP10_RESOURCE_PROFILE

acquire_daily_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    trap 'rm -f "$LOCK_PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
    return 0
  fi

  EXISTING_PID=""
  if [ -r "$LOCK_PID_FILE" ]; then
    EXISTING_PID="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  fi

  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "========================================" | tee -a "$LOG_FILE"
    echo "⏭️ 每日流程略過 - $(date)" | tee -a "$LOG_FILE"
    echo "📌 已有 daily run 執行中 pid=$EXISTING_PID lock=$LOCK_DIR" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    exit 0
  fi

  echo "⚠️ 偵測到 stale daily lock，嘗試清理: $LOCK_DIR" | tee -a "$LOG_FILE"
  rm -f "$LOCK_PID_FILE"
  if rmdir "$LOCK_DIR" 2>/dev/null && mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    trap 'rm -f "$LOCK_PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
    return 0
  fi

  echo "========================================" | tee -a "$LOG_FILE"
  echo "⏭️ 每日流程略過 - $(date)" | tee -a "$LOG_FILE"
  echo "📌 無法取得 daily lock=$LOCK_DIR，避免重複寫入 data/artifacts" | tee -a "$LOG_FILE"
  echo "========================================" | tee -a "$LOG_FILE"
  exit 0
}

acquire_daily_lock

echo "========================================" | tee -a "$LOG_FILE"
echo "🚀 開始每日自動執行 - $(date)" | tee -a "$LOG_FILE"
echo "🧯 resource profile: $TOP10_RESOURCE_PROFILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
"$UV_BIN" run --with-requirements requirements.txt python -m scripts.run_automation daily >> "$LOG_FILE" 2>&1
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
STATUS_OUTPUT="$("$UV_BIN" run --with-requirements requirements.txt python scripts/print_daily_status.py --status "$STATUS_PATH" --min-started-at-epoch "$WRAPPER_STARTED_AT_EPOCH" 2>&1)"
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
