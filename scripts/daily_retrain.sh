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
echo "========================================" | tee -a "$LOG_FILE"

uv run --with-requirements requirements.txt python -m scripts.run_automation "$MODE" >> "$LOG_FILE" 2>&1

# 完成
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "✨ $FINISH_NAME - $(date)" | tee -a "$LOG_FILE"
if [ "$MODE" = "retrain" ]; then
    echo "📄 新模型: models/latest_lgbm.pkl" | tee -a "$LOG_FILE"
else
    echo "📄 狀態檔: artifacts/automation_status.json" | tee -a "$LOG_FILE"
fi
echo "========================================" | tee -a "$LOG_FILE"
