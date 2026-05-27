#!/bin/bash
# NEW-TOP10 launchd 排程安裝腳本 (macOS 推薦)
# 功能: 設定 macOS launchd agents

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "========================================="
echo "🔧 NEW-TOP10 launchd 排程設定 (macOS)"
echo "========================================="
echo ""
echo "專案路徑: $PROJECT_DIR"
echo "LaunchAgents: $LAUNCH_AGENTS_DIR"
echo ""
echo "將設定以下排程:"
echo "  1. 每日 17:30 - 執行 ETL + 選股 + New Clawd 推播；週末由 daily gate 跳過"
echo "  2. 每日 02:00 - PSI 漂移監控"
echo "  3. 每月 1 日 03:30 - Reference sources 更新"
echo ""
read -p "確認繼續? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "❌ 取消設定"
    exit 0
fi

# 建立 LaunchAgents 目錄
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$PROJECT_DIR/logs"

# 複製並修改 plist 檔案
echo ""
echo "📝 設定 plist 檔案..."

# Daily plist
DAILY_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.daily.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.daily.plist" > "$DAILY_PLIST"
echo "✅ 已建立: $DAILY_PLIST"

# Retrain plist
RETRAIN_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.retrain.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.retrain.plist" > "$RETRAIN_PLIST"
echo "✅ 已建立: $RETRAIN_PLIST"

# Reference plist
REFERENCE_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.reference.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.reference.plist" > "$REFERENCE_PLIST"
echo "✅ 已建立: $REFERENCE_PLIST"

# 載入排程
echo ""
echo "🚀 載入 launchd agents..."
launchctl unload "$DAILY_PLIST" 2>/dev/null || true
launchctl load "$DAILY_PLIST"
echo "✅ 每日執行排程已載入"

launchctl unload "$RETRAIN_PLIST" 2>/dev/null || true
launchctl load "$RETRAIN_PLIST"
echo "✅ 每日 PSI 監控排程已載入"

launchctl unload "$REFERENCE_PLIST" 2>/dev/null || true
launchctl load "$REFERENCE_PLIST"
echo "✅ 每月 reference 更新排程已載入"

# 驗證
echo ""
echo "========================================="
echo "📋 已載入的排程:"
echo "========================================="
launchctl list | grep new-top10 || echo "(無 NEW-TOP10 排程)"
echo ""

echo "========================================="
echo "✨ 安裝完成！"
echo "========================================="
echo "排程將在以下時間自動執行:"
echo "  • 每日 17:30 - ETL + 選股 + New Clawd 推播；週末由 daily gate 跳過"
echo "  • 每日 02:00 - PSI 漂移監控"
echo "  • 每月 1 日 03:30 - Reference sources 更新"
echo ""
echo "手動重訓:"
echo "  bash $PROJECT_DIR/scripts/daily_retrain.sh retrain"
echo "手動更新 reference:"
echo "  bash $PROJECT_DIR/scripts/run_reference_update.sh"
echo ""
echo "📄 日誌位置:"
echo "  $PROJECT_DIR/logs/"
echo ""
echo "🔧 管理指令:"
echo "  停用: launchctl unload ~/Library/LaunchAgents/com.new-top10.*.plist"
echo "  啟用: launchctl load ~/Library/LaunchAgents/com.new-top10.*.plist"
echo "  查看: launchctl list | grep new-top10"
echo "========================================="
