#!/bin/bash
# 外部 review provider 健康檢查：只 probe 瀏覽器，不送 packet。

set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

PYTHON_BIN="${TOP10_DAILY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

RUN_DATE="${TOP10_RUN_DATE:-$(date +%F)}"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/external_review_provider_preflight_$(date +%Y%m%d).log"

CHATGPT_URL_PART="${TOP10_CHATGPT_URL_PART:-chatgpt.com/g/g-p-6a1ff7db268881918957ff493f2a915b/c/6a38ae69-0660-83ee-91ff-1777ae00688f}"
GEMINI_URL_PART="${TOP10_GEMINI_URL_PART:-gemini.google.com/app/ea58b54eef550ded}"
export TOP10_CHATGPT_URL_PART="$CHATGPT_URL_PART"
export TOP10_GEMINI_URL_PART="$GEMINI_URL_PART"

echo "========================================" | tee -a "$LOG_FILE"
echo "external review provider preflight start - $(date)" | tee -a "$LOG_FILE"
echo "run_date: $RUN_DATE" | tee -a "$LOG_FILE"
echo "chatgpt_url_part: $CHATGPT_URL_PART" | tee -a "$LOG_FILE"
echo "gemini_url_part: $GEMINI_URL_PART" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

set +e
"$PYTHON_BIN" scripts/preflight_external_review_providers.py --date "$RUN_DATE" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "external review provider preflight finished - $(date)" | tee -a "$LOG_FILE"
else
  echo "external review provider preflight failed - $(date) exit_code=$EXIT_CODE" | tee -a "$LOG_FILE"
fi

exit "$EXIT_CODE"
