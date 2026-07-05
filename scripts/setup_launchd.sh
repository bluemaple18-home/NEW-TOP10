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
echo "  1. 每日 17:30 - 執行 ETL + 選股 + Clawd-ready payload；週末由 daily gate 跳過"
echo "  2. 每日 17:40 - 外部 AI review provider preflight；只檢查瀏覽器 session，不送 packet"
echo "  3. 每日 17:50 - 外部 AI review + Fog Map / Research Worker harness handoff"
echo "  4. 每 15 分鐘 - Fog Map / Research Worker burn-down worker；lock 會避免重疊"
echo "  5. 每 15 分鐘 - PM approval research harness；launchd 明確啟用研究，Discord 送卡 dry-run"
echo "  6. 每日 02:00 - PSI 漂移監控"
echo "  7. 每月 1 日 03:30 - Reference sources 更新"
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

# 舊 controlled-grid-drain 入口只重建 linkage artifacts，正式迷霧交接已併入 external-review harness。
LEGACY_CONTROLLED_GRID_DRAIN_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.controlled-grid-drain.plist"
if [ -e "$LEGACY_CONTROLLED_GRID_DRAIN_PLIST" ]; then
    launchctl unload "$LEGACY_CONTROLLED_GRID_DRAIN_PLIST" 2>/dev/null || true
    rm -f "$LEGACY_CONTROLLED_GRID_DRAIN_PLIST"
    echo "✅ 已移除 legacy controlled-grid-drain 排程: $LEGACY_CONTROLLED_GRID_DRAIN_PLIST"
fi

# Daily plist
DAILY_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.daily.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.daily.plist" > "$DAILY_PLIST"
echo "✅ 已建立: $DAILY_PLIST"

# Retrain plist
RETRAIN_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.retrain.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.retrain.plist" > "$RETRAIN_PLIST"
echo "✅ 已建立: $RETRAIN_PLIST"

# External review / fog map handoff plist
EXTERNAL_REVIEW_PREFLIGHT_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.external-review-preflight.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.external-review-preflight.plist" > "$EXTERNAL_REVIEW_PREFLIGHT_PLIST"
echo "✅ 已建立: $EXTERNAL_REVIEW_PREFLIGHT_PLIST"

EXTERNAL_REVIEW_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.external-review.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.external-review.plist" > "$EXTERNAL_REVIEW_PLIST"
echo "✅ 已建立: $EXTERNAL_REVIEW_PLIST"

# Fog research worker plist
FOG_RESEARCH_WORKER_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.fog-research-worker.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.fog-research-worker.plist" > "$FOG_RESEARCH_WORKER_PLIST"
echo "✅ 已建立: $FOG_RESEARCH_WORKER_PLIST"

# PM research harness loop plist
PM_RESEARCH_HARNESS_PLIST="$LAUNCH_AGENTS_DIR/com.new-top10.pm-research-harness.plist"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/com.new-top10.pm-research-harness.plist" > "$PM_RESEARCH_HARNESS_PLIST"
echo "✅ 已建立: $PM_RESEARCH_HARNESS_PLIST"

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

launchctl unload "$EXTERNAL_REVIEW_PREFLIGHT_PLIST" 2>/dev/null || true
launchctl load "$EXTERNAL_REVIEW_PREFLIGHT_PLIST"
echo "✅ 外部 review provider preflight 排程已載入"

launchctl unload "$EXTERNAL_REVIEW_PLIST" 2>/dev/null || true
launchctl load "$EXTERNAL_REVIEW_PLIST"
echo "✅ 外部 review / Fog Map handoff 排程已載入"

launchctl unload "$FOG_RESEARCH_WORKER_PLIST" 2>/dev/null || true
launchctl load "$FOG_RESEARCH_WORKER_PLIST"
echo "✅ Fog Map / Research Worker 受控研究排程已載入"

launchctl unload "$PM_RESEARCH_HARNESS_PLIST" 2>/dev/null || true
launchctl load "$PM_RESEARCH_HARNESS_PLIST"
echo "✅ PM approval research harness loop 排程已載入；launchd 明確啟用研究，Discord 送卡 dry-run"

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
echo "  • 每日 17:30 - ETL + 選股 + Clawd-ready payload；週末由 daily gate 跳過"
echo "  • 每日 17:40 - 外部 AI review provider preflight；只檢查瀏覽器 session，不送 packet"
echo "  • 每日 17:50 - 外部 AI review + Fog Map / Research Worker harness handoff"
echo "  • 每 15 分鐘 - Fog Map / Research Worker burn-down worker；lock 會避免重疊"
echo "  • 每 15 分鐘 - PM approval research harness；launchd 明確啟用研究，Discord 送卡 dry-run"
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
