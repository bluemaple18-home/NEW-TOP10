#!/bin/bash
# ============================================================
# 一鍵推送腳本 - 提交並推送變更
# 用法: ./scripts/push_changes.sh "提交訊息"
# ============================================================

set -e

# 檢查是否有提交訊息
if [ -z "$1" ]; then
    echo "❌ 請提供提交訊息"
    echo "用法: ./scripts/push_changes.sh \"修改了什麼\""
    exit 1
fi

COMMIT_MSG="$1"

echo "📝 準備提交變更..."
echo ""

# 顯示變更內容
echo "📋 變更清單："
git status --short
echo ""

# 加入所有變更
git add -A

# 提交
echo "💾 提交中..."
git commit -m "$COMMIT_MSG"

# 先拉取再推送（避免衝突）
echo ""
echo "📥 檢查遠端更新..."
git pull --rebase origin main

# 推送
echo ""
echo "📤 推送到遠端..."
git push origin main

echo ""
echo "✅ 推送完成！"
echo ""
echo "📊 最新提交："
git log --oneline -1
