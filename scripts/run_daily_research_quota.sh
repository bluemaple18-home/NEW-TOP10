#!/usr/bin/env bash
# 每日研究配額入口：從 autonomous research queue 取固定數量的策略組合做安全回測。
# 不接 launchd、不訓練模型、不改正式 ranking、不做 promotion。

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
UV_BIN="${UV_BIN:-$(command -v uv 2>/dev/null || true)}"
if [ -z "$UV_BIN" ]; then
  echo "❌ uv command not found; set UV_BIN or install uv under $HOME/.local/bin, /opt/homebrew/bin, or /usr/local/bin"
  exit 127
fi

RUN_DATE="${TOP10_RESEARCH_DATE:-$(date +%F)}"
QUOTA="${TOP10_RESEARCH_QUOTA:-5}"
MAX_RANKING_FILES="${TOP10_RESEARCH_MAX_RANKING_FILES:-8}"
ALLOW_RERUN="${TOP10_RESEARCH_ALLOW_RERUN:-1}"
LOG_DIR="$PROJECT_DIR/logs"
OUTPUT="artifacts/autonomous_research/autonomous_research_daily_quota_${RUN_DATE}.json"
LOG_FILE="$LOG_DIR/daily_research_quota_${RUN_DATE//-/}.log"
RERUN_ARGS=()

if [ "$ALLOW_RERUN" = "1" ] || [ "$ALLOW_RERUN" = "true" ] || [ "$ALLOW_RERUN" = "TRUE" ]; then
  RERUN_ARGS=(--rerun)
fi

mkdir -p "$LOG_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "開始每日研究配額 - $(date)" | tee -a "$LOG_FILE"
echo "run_date=$RUN_DATE quota=$QUOTA max_ranking_files=$MAX_RANKING_FILES allow_rerun=$ALLOW_RERUN" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
"$UV_BIN" run --with-requirements requirements.txt python scripts/run_autonomous_research.py \
  --date "$RUN_DATE" \
  --execute \
  --from-queue \
  --execute-topic-count "$QUOTA" \
  --max-ranking-files "$MAX_RANKING_FILES" \
  "${RERUN_ARGS[@]}" \
  --output "$OUTPUT" >> "$LOG_FILE" 2>&1
RUN_EXIT_CODE=$?
set -e

set +e
"$UV_BIN" run --with-requirements requirements.txt python scripts/verify_daily_research_quota.py \
  --artifact "$OUTPUT" \
  --min-quota "$QUOTA" >> "$LOG_FILE" 2>&1
VERIFY_EXIT_CODE=$?
set -e

if [ "$RUN_EXIT_CODE" -ne 0 ]; then
  echo "❌ autonomous research quota run failed exit_code=$RUN_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$RUN_EXIT_CODE"
fi

if [ "$VERIFY_EXIT_CODE" -ne 0 ]; then
  echo "❌ daily research quota verification failed exit_code=$VERIFY_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$VERIFY_EXIT_CODE"
fi

echo "✅ 每日研究配額完成 output=$OUTPUT" | tee -a "$LOG_FILE"
exit 0
