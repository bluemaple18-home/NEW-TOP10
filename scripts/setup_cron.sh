#!/bin/bash
# NEW-TOP10 自動化排程安裝腳本
# 功能: 設定 macOS cron jobs

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================="
echo "🔧 NEW-TOP10 自動化排程設定"
echo "========================================="
echo ""
echo "專案路徑: $PROJECT_DIR"
echo ""
echo "將設定以下排程:"
echo "  1. 每日 22:00 - 執行 ETL + 選股"
echo "  2. 每日 02:00 - PSI 漂移監控"
echo "  3. 每月 1 日 03:30 - Reference sources 更新"
echo ""
read -p "確認繼續? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "❌ 取消設定"
    exit 0
fi

# 建立 crontab 項目
CRON_DAILY="0 22 * * * cd $PROJECT_DIR && bash scripts/run_daily.sh"
CRON_RETRAIN="0 2 * * * cd $PROJECT_DIR && TOP10_RESOURCE_PROFILE=host_full bash scripts/daily_retrain.sh monitor --trigger scheduled"
CRON_REFERENCE="30 3 1 * * cd $PROJECT_DIR && bash scripts/run_reference_update.sh"

# 檢查是否已存在
crontab -l 2>/dev/null | grep -q "run_daily.sh" && DAILY_EXISTS=1 || DAILY_EXISTS=0
crontab -l 2>/dev/null | grep -q "daily_retrain.sh" && RETRAIN_EXISTS=1 || RETRAIN_EXISTS=0
crontab -l 2>/dev/null | grep -q "run_reference_update.sh" && REFERENCE_EXISTS=1 || REFERENCE_EXISTS=0

# 備份現有 crontab
echo "" 
echo "💾 備份現有 crontab..."
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true

# 新增排程
echo ""
echo "➕ 新增排程項目..."

if [ $DAILY_EXISTS -eq 0 ]; then
    (crontab -l 2>/dev/null; echo "$CRON_DAILY") | crontab -
    echo "✅ 已新增每日執行排程 (22:00)"
else
    echo "⚠️ 每日執行排程已存在，跳過"
fi

if [ $RETRAIN_EXISTS -eq 0 ]; then
    (crontab -l 2>/dev/null; echo "$CRON_RETRAIN") | crontab -
    echo "✅ 已新增每日 PSI 監控排程 (02:00)"
else
    echo "⚠️ 每日 PSI 監控排程已存在，跳過"
fi

if [ $REFERENCE_EXISTS -eq 0 ]; then
    (crontab -l 2>/dev/null; echo "$CRON_REFERENCE") | crontab -
    echo "✅ 已新增每月 reference 更新排程 (每月 1 日 03:30)"
else
    echo "⚠️ 每月 reference 更新排程已存在，跳過"
fi

# 顯示當前排程
echo ""
echo "========================================="
echo "📋 當前 crontab 排程:"
echo "========================================="
crontab -l | grep "$PROJECT_DIR" || echo "(無 NEW-TOP10 相關排程)"
echo ""

# macOS 特殊提示
echo "========================================="
echo "⚠️ macOS 使用者注意事項"
echo "========================================="
echo "1. 需授予終端機「完整磁碟存取權限」"
echo "   系統偏好設定 → 安全性與隱私 → 完整磁碟取用權限"
echo ""
echo "2. cron 在 macOS 可能被 launchd 取代"
echo "   若 cron 無法運作，請改用 launchd (scripts/setup_launchd.sh)"
echo ""
echo "3. 手動測試腳本:"
echo "   bash $PROJECT_DIR/scripts/run_daily.sh"
echo "   TOP10_RESOURCE_PROFILE=host_full bash $PROJECT_DIR/scripts/daily_retrain.sh monitor --trigger scheduled"
echo "   bash $PROJECT_DIR/scripts/daily_retrain.sh retrain"
echo "   bash $PROJECT_DIR/scripts/run_reference_update.sh"
echo "========================================="
