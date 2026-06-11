#!/usr/bin/env bash
# 每日研究配額入口：從 autonomous research queue 取固定數量的策略組合做安全回測。
# 不接 launchd、不訓練模型、不改正式 ranking、不做 promotion。

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
PYTHON_BIN="${TOP10_RESEARCH_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
RUNNER_CMD=()
if [ -x "$PYTHON_BIN" ]; then
  RUNNER_CMD=("$PYTHON_BIN")
  RUNTIME_LABEL="$PYTHON_BIN"
else
  UV_BIN="${UV_BIN:-$(command -v uv 2>/dev/null || true)}"
  if [ -z "$UV_BIN" ]; then
    echo "❌ python runtime not found; expected $PYTHON_BIN or set UV_BIN"
    exit 127
  fi
  RUNNER_CMD=("$UV_BIN" run --with-requirements requirements.txt python)
  RUNTIME_LABEL="$UV_BIN run --with-requirements requirements.txt python"
fi

RUN_DATE="${TOP10_RESEARCH_DATE:-$(date +%F)}"
QUOTA="${TOP10_RESEARCH_QUOTA:-5}"
MAX_RANKING_FILES="${TOP10_RESEARCH_MAX_RANKING_FILES:-8}"
ALLOW_RERUN="${TOP10_RESEARCH_ALLOW_RERUN:-1}"
INCLUDE_REJECTED="${TOP10_RESEARCH_INCLUDE_REJECTED:-0}"
FROM_QUEUE="${TOP10_RESEARCH_FROM_QUEUE:-0}"
MAX_TOPICS="${TOP10_RESEARCH_MAX_TOPICS:-200}"
LOG_DIR="$PROJECT_DIR/logs"
OUTPUT="artifacts/autonomous_research/autonomous_research_daily_quota_${RUN_DATE}.json"
LOG_FILE="$LOG_DIR/daily_research_quota_${RUN_DATE//-/}.log"
RERUN_ARGS=()

if [ "$ALLOW_RERUN" = "1" ] || [ "$ALLOW_RERUN" = "true" ] || [ "$ALLOW_RERUN" = "TRUE" ]; then
  RERUN_ARGS=(--rerun)
fi

RUN_ARGS=(
  scripts/run_autonomous_research.py
  --date "$RUN_DATE"
  --execute
  --max-topics "$MAX_TOPICS"
  --execute-topic-count "$QUOTA"
  --max-ranking-files "$MAX_RANKING_FILES"
)

if [ "$FROM_QUEUE" = "1" ] || [ "$FROM_QUEUE" = "true" ] || [ "$FROM_QUEUE" = "TRUE" ]; then
  RUN_ARGS+=(--from-queue)
fi

RUN_ARGS+=("${RERUN_ARGS[@]}")
if [ "$INCLUDE_REJECTED" = "1" ] || [ "$INCLUDE_REJECTED" = "true" ] || [ "$INCLUDE_REJECTED" = "TRUE" ]; then
  RUN_ARGS+=(--include-rejected)
fi
RUN_ARGS+=(--output "$OUTPUT")

mkdir -p "$LOG_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "開始每日研究配額 - $(date)" | tee -a "$LOG_FILE"
echo "run_date=$RUN_DATE quota=$QUOTA max_topics=$MAX_TOPICS max_ranking_files=$MAX_RANKING_FILES allow_rerun=$ALLOW_RERUN include_rejected=$INCLUDE_REJECTED from_queue=$FROM_QUEUE" | tee -a "$LOG_FILE"
echo "runtime=$RUNTIME_LABEL" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
"${RUNNER_CMD[@]}" "${RUN_ARGS[@]}" >> "$LOG_FILE" 2>&1
RUN_EXIT_CODE=$?
set -e

set +e
"${RUNNER_CMD[@]}" scripts/verify_daily_research_quota.py \
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
