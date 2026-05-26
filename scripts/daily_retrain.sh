#!/bin/bash
# NEW-TOP10 模型維護腳本
# 執行時間: 每日 02:00
# 功能: 透過統一 orchestrator 執行重訓/監控

set -e

# 切換到專案目錄
cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

# 日誌目錄
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/retrain_$(date +%Y%m%d).log"
MODE="${1:-monitor}"
DRY_RUN=false
WRAPPER_STARTED_AT_EPOCH="$(date +%s)"

if [ "${2:-}" = "--dry-run" ]; then
    DRY_RUN=true
elif [ -n "${2:-}" ]; then
    echo "❌ 不支援的參數: $2 (可用: --dry-run)" | tee -a "$LOG_FILE"
    exit 1
fi

case "$MODE" in
    monitor)
        JOB_NAME="每日 PSI 漂移監控"
        FINISH_NAME="PSI 監控完成"
        ;;
    retrain)
        JOB_NAME="手動模型重訓"
        FINISH_NAME="模型重訓完成"
        ;;
    status)
        JOB_NAME="自動化狀態檢查"
        FINISH_NAME="狀態檢查完成"
        ;;
    *)
        echo "❌ 不支援的模式: $MODE (可用: monitor, retrain, status)" | tee -a "$LOG_FILE"
        exit 1
        ;;
esac

echo "========================================" | tee -a "$LOG_FILE"
echo "🔧 開始 $JOB_NAME - $(date)" | tee -a "$LOG_FILE"
if [ "$DRY_RUN" = true ]; then
    echo "🧪 dry-run 模式：不執行長任務、不覆蓋模型" | tee -a "$LOG_FILE"
fi
echo "========================================" | tee -a "$LOG_FILE"

set +e
COMMAND=(uv run --with-requirements requirements.txt python -m scripts.run_automation "$MODE")
if [ "$DRY_RUN" = true ]; then
    COMMAND+=(--dry-run)
fi
"${COMMAND[@]}" >> "$LOG_FILE" 2>&1
RUN_EXIT_CODE=$?
set -e

STATUS_PATH="$PROJECT_DIR/artifacts/automation_status.json"

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
if [ "$RUN_EXIT_CODE" -eq 0 ]; then
    echo "✨ $FINISH_NAME - $(date)" | tee -a "$LOG_FILE"
else
    echo "❌ $JOB_NAME 失敗 - $(date) exit_code=$RUN_EXIT_CODE" | tee -a "$LOG_FILE"
fi

STATUS_ARGS=(scripts/print_daily_status.py --status "$STATUS_PATH" --min-started-at-epoch "$WRAPPER_STARTED_AT_EPOCH" --label "$JOB_NAME")
if [ "$MODE" = "retrain" ]; then
    STATUS_ARGS+=(--summary-prefix retrain_run_summary)
else
    STATUS_ARGS+=(--summary-prefix "")
fi

set +e
STATUS_OUTPUT="$(uv run --with-requirements requirements.txt python "${STATUS_ARGS[@]}" 2>&1)"
STATUS_EXIT_CODE=$?
set -e

if [ "$STATUS_EXIT_CODE" -eq 0 ]; then
    echo "$STATUS_OUTPUT" | tee -a "$LOG_FILE"
else
    echo "📄 狀態檔: $STATUS_PATH" | tee -a "$LOG_FILE"
    echo "$STATUS_OUTPUT" | tee -a "$LOG_FILE"
    echo "⚠️ 無法讀取本次狀態；請查看 log 內 run_automation 輸出。" | tee -a "$LOG_FILE"
fi
echo "========================================" | tee -a "$LOG_FILE"

exit "$RUN_EXIT_CODE"
