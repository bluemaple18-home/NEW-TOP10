#!/bin/bash
# ============================================================
# 一鍵同步腳本 - 從遠端拉取最新版本
# 用法: ./scripts/sync_from_remote.sh
# ============================================================

set -e

echo "🔄 開始同步遠端變更..."
echo ""

# 確認當前狀態
if [[ -n $(git status --porcelain) ]]; then
    echo "⚠️  發現未提交的變更："
    git status --short
    echo ""
    read -p "是否要暫存這些變更並繼續？(y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git stash push -m "auto-stash before sync $(date +%Y%m%d_%H%M%S)"
        echo "✅ 變更已暫存"
        STASHED=true
    else
        echo "❌ 取消同步"
        exit 1
    fi
fi

# 拉取遠端
echo ""
echo "📥 拉取遠端變更..."
git fetch origin

# 合併（使用 rebase 保持線性歷史）
echo ""
echo "🔀 合併變更..."
git pull --rebase origin main

# 還原暫存
if [[ "$STASHED" == "true" ]]; then
    echo ""
    echo "📦 還原暫存的變更..."
    git stash pop || echo "⚠️ 暫存還原失敗，請手動處理: git stash list"
fi

echo ""
echo "✅ 同步完成！"
echo ""
echo "📊 目前狀態："
git log --oneline -3
