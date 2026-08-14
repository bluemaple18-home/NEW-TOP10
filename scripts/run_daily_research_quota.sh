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

RUN_CONTEXT="${TOP10_FOG_RUN_CONTEXT:-}"
if [ -z "$RUN_CONTEXT" ]; then
  echo "❌ missing immutable time context; TOP10_FOG_RUN_CONTEXT is required"
  exit 1
fi
if ! "${RUNNER_CMD[@]}" scripts/fog_runtime_time_authority.py --context "$RUN_CONTEXT" > /dev/null; then
  echo "❌ immutable time context validation failed"
  exit 1
fi
RUN_DATE="$("${RUNNER_CMD[@]}" scripts/fog_runtime_time_authority.py --context "$RUN_CONTEXT" --field market_run_date)"
RESEARCH_BATCH_ID="research-${RUN_DATE}-$(date +%H%M%S)-$$"
if [ -n "${TOP10_RESEARCH_DATE:-}" ] && [ "$TOP10_RESEARCH_DATE" != "$RUN_DATE" ]; then
  echo "❌ TOP10_RESEARCH_DATE mismatches immutable time context"
  exit 1
fi
if [ -n "${TOP10_RUN_DATE:-}" ] && [ "$TOP10_RUN_DATE" != "$RUN_DATE" ]; then
  echo "❌ TOP10_RUN_DATE mismatches immutable time context"
  exit 1
fi
export TOP10_RESEARCH_DATE="$RUN_DATE"
QUOTA="${TOP10_RESEARCH_QUOTA:-5}"
MAX_RANKING_FILES="${TOP10_RESEARCH_MAX_RANKING_FILES:-8}"
ALLOW_RERUN="${TOP10_RESEARCH_ALLOW_RERUN:-1}"
INCLUDE_REJECTED="${TOP10_RESEARCH_INCLUDE_REJECTED:-0}"
FROM_QUEUE="${TOP10_RESEARCH_FROM_QUEUE:-0}"
MAX_TOPICS="${TOP10_RESEARCH_MAX_TOPICS:-200}"
BASELINE_DIR="${TOP10_RESEARCH_BASELINE_DIR:-artifacts/backtest/historical_rankings_current_model_fog_2025-06-03_2026-07-28_ce643797}"
DEVELOPMENT_SCREEN_ENABLED="${TOP10_RESEARCH_DEVELOPMENT_SCREEN_ENABLED:-1}"
DEVELOPMENT_SCREEN_TOPIC_COUNT="${TOP10_RESEARCH_DEVELOPMENT_SCREEN_TOPIC_COUNT:-1}"
REFRESH_RESEARCH_MAP="${TOP10_REFRESH_RESEARCH_MAP:-1}"
LOG_DIR="$PROJECT_DIR/logs"
OUTPUT="artifacts/autonomous_research/autonomous_research_daily_quota_${RUN_DATE}.json"
RUNTIME_RECEIPT="artifacts/autonomous_research/closed_regime_runtime_receipt_${RUN_DATE}.json"
BATCH_VERIFICATION="artifacts/autonomous_research/research_spine_batch_verification_${RESEARCH_BATCH_ID}.json"
LEDGER_BATCH_VERIFICATION="artifacts/autonomous_research/research_ledger_batch_verification_${RESEARCH_BATCH_ID}.json"
RESEARCH_LEDGER="data/research/research_ledger.duckdb"
RUN_ARCHIVE_DIR="artifacts/autonomous_research/run_outputs"
RUN_ARCHIVE_STEM="autonomous_research_daily_quota_${RUN_DATE}_$(date +%H%M%S)"
LOG_FILE="$LOG_DIR/daily_research_quota_${RUN_DATE//-/}.log"
declare -a RERUN_ARGS=()

if [ "$ALLOW_RERUN" = "1" ] || [ "$ALLOW_RERUN" = "true" ] || [ "$ALLOW_RERUN" = "TRUE" ]; then
  RERUN_ARGS=(--rerun)
fi

RUN_ARGS=(
  scripts/run_autonomous_research.py
  --date "$RUN_DATE"
  --research-batch-id "$RESEARCH_BATCH_ID"
  --execute
  --closed-regime-research
  --market-regime-history artifacts/market_regime_history.json
  --research-contract config/regime_research_contract.json
  --baseline-dir "$BASELINE_DIR"
  --max-topics "$MAX_TOPICS"
  --execute-topic-count "$QUOTA"
  --development-screen-topic-count "$DEVELOPMENT_SCREEN_TOPIC_COUNT"
  --max-ranking-files "$MAX_RANKING_FILES"
)

if [ "$DEVELOPMENT_SCREEN_ENABLED" = "1" ] || [ "$DEVELOPMENT_SCREEN_ENABLED" = "true" ] || [ "$DEVELOPMENT_SCREEN_ENABLED" = "TRUE" ]; then
  RUN_ARGS+=(--development-screen-on-sealed-exhaustion)
fi

if [ "$FROM_QUEUE" = "1" ] || [ "$FROM_QUEUE" = "true" ] || [ "$FROM_QUEUE" = "TRUE" ]; then
  RUN_ARGS+=(--from-queue)
fi

if [ "${#RERUN_ARGS[@]}" -gt 0 ]; then
  RUN_ARGS+=("${RERUN_ARGS[@]}")
fi
if [ "$INCLUDE_REJECTED" = "1" ] || [ "$INCLUDE_REJECTED" = "true" ] || [ "$INCLUDE_REJECTED" = "TRUE" ]; then
  RUN_ARGS+=(--include-rejected)
fi
RUN_ARGS+=(--output "$OUTPUT")

mkdir -p "$LOG_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "開始每日研究配額 - $(date)" | tee -a "$LOG_FILE"
echo "run_date=$RUN_DATE quota=$QUOTA max_topics=$MAX_TOPICS max_ranking_files=$MAX_RANKING_FILES allow_rerun=$ALLOW_RERUN include_rejected=$INCLUDE_REJECTED from_queue=$FROM_QUEUE baseline_dir=$BASELINE_DIR development_screen=$DEVELOPMENT_SCREEN_ENABLED development_screen_topic_count=$DEVELOPMENT_SCREEN_TOPIC_COUNT" | tee -a "$LOG_FILE"
echo "runtime=$RUNTIME_LABEL" | tee -a "$LOG_FILE"
echo "refresh_research_map=$REFRESH_RESEARCH_MAP" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

REQUESTED_RESEARCH_STAGE="COARSE_SCREEN"
if [ "$DEVELOPMENT_SCREEN_ENABLED" = "1" ] || [ "$DEVELOPMENT_SCREEN_ENABLED" = "true" ] || [ "$DEVELOPMENT_SCREEN_ENABLED" = "TRUE" ]; then
  REQUESTED_RESEARCH_STAGE="DEVELOPMENT_SCREEN"
fi

set +e
BATCH_INTENT_ID="$("${RUNNER_CMD[@]}" scripts/publish_research_batch_intent.py \
  --batch-id "$RESEARCH_BATCH_ID" \
  --execution-epoch "$RUN_DATE" \
  --requested-research-stage "$REQUESTED_RESEARCH_STAGE" \
  --allowed-research-stage DEVELOPMENT_SCREEN \
  --allowed-research-stage COARSE_SCREEN \
  --output "$OUTPUT" \
  --corpus-root artifacts/autonomous_research/research_spine \
  --ledger "$RESEARCH_LEDGER" \
  -- "${RUN_ARGS[@]}" 2>> "$LOG_FILE")"
BATCH_INTENT_EXIT_CODE=$?
set -e
if [ "$BATCH_INTENT_EXIT_CODE" -ne 0 ]; then
  echo "❌ research batch intent publication failed exit_code=$BATCH_INTENT_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$BATCH_INTENT_EXIT_CODE"
fi
RUN_ARGS+=(--research-batch-intent "$BATCH_INTENT_ID")

set +e
"${RUNNER_CMD[@]}" "${RUN_ARGS[@]}" >> "$LOG_FILE" 2>&1
RUN_EXIT_CODE=$?
set -e

set +e
"${RUNNER_CMD[@]}" scripts/verify_research_spine_batch.py \
  --batch-id "$RESEARCH_BATCH_ID" \
  --corpus-root artifacts/autonomous_research/research_spine \
  --run-artifact "$OUTPUT" \
  --output "$BATCH_VERIFICATION" >> "$LOG_FILE" 2>&1
BATCH_VERIFY_EXIT_CODE=$?
set -e
if [ "$BATCH_VERIFY_EXIT_CODE" -ne 0 ]; then
  echo "❌ research spine batch verification failed exit_code=$BATCH_VERIFY_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$BATCH_VERIFY_EXIT_CODE"
fi

set +e
"${RUNNER_CMD[@]}" -m app.research.observation_ingest \
  --date "$RUN_DATE" \
  --ledger "$RESEARCH_LEDGER" >> "$LOG_FILE" 2>&1
INGEST_EXIT_CODE=$?
set -e
if [ "$INGEST_EXIT_CODE" -ne 0 ]; then
  echo "❌ research ledger ingest failed exit_code=$INGEST_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$INGEST_EXIT_CODE"
fi

set +e
"${RUNNER_CMD[@]}" scripts/verify_research_ledger_batch.py \
  --batch-verification "$BATCH_VERIFICATION" \
  --ledger "$RESEARCH_LEDGER" \
  --output "$LEDGER_BATCH_VERIFICATION" >> "$LOG_FILE" 2>&1
LEDGER_VERIFY_EXIT_CODE=$?
set -e
if [ "$LEDGER_VERIFY_EXIT_CODE" -ne 0 ]; then
  echo "❌ research ledger batch verification failed exit_code=$LEDGER_VERIFY_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$LEDGER_VERIFY_EXIT_CODE"
fi

if [ "$RUN_EXIT_CODE" -ne 0 ]; then
  echo "❌ autonomous research quota run failed after receipt ingest exit_code=$RUN_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$RUN_EXIT_CODE"
fi

set +e
"${RUNNER_CMD[@]}" scripts/verify_closed_regime_runtime.py \
  --build-receipt \
  --run-context "$RUN_CONTEXT" \
  --output "$RUNTIME_RECEIPT" >> "$LOG_FILE" 2>&1
RECEIPT_EXIT_CODE=$?
set -e

if [ "$RECEIPT_EXIT_CODE" -ne 0 ]; then
  echo "❌ closed-regime runtime receipt build failed exit_code=$RECEIPT_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$RECEIPT_EXIT_CODE"
fi

set +e
"${RUNNER_CMD[@]}" scripts/verify_daily_research_quota.py \
  --artifact "$OUTPUT" \
  --min-quota "$QUOTA" \
  --runtime-receipt "$RUNTIME_RECEIPT" >> "$LOG_FILE" 2>&1
VERIFY_EXIT_CODE=$?
set -e

if [ "$VERIFY_EXIT_CODE" -ne 0 ]; then
  echo "❌ daily research quota verification failed exit_code=$VERIFY_EXIT_CODE" | tee -a "$LOG_FILE"
  exit "$VERIFY_EXIT_CODE"
fi

mkdir -p "$RUN_ARCHIVE_DIR"
cp "$OUTPUT" "$RUN_ARCHIVE_DIR/${RUN_ARCHIVE_STEM}.json"
if [ -f "${OUTPUT%.json}.md" ]; then
  cp "${OUTPUT%.json}.md" "$RUN_ARCHIVE_DIR/${RUN_ARCHIVE_STEM}.md"
fi

if [ "$REFRESH_RESEARCH_MAP" = "1" ] || [ "$REFRESH_RESEARCH_MAP" = "true" ] || [ "$REFRESH_RESEARCH_MAP" = "TRUE" ]; then
  set +e
  "${RUNNER_CMD[@]}" -m app.research.history_compatibility_projection \
    --ledger "$RESEARCH_LEDGER" \
    --output artifacts/autonomous_research/run_history.jsonl \
    --manifest-output artifacts/autonomous_research/run_history_projection_manifest.json >> "$LOG_FILE" 2>&1
  BACKFILL_EXIT_CODE=$?
  set -e

  if [ "$BACKFILL_EXIT_CODE" -ne 0 ]; then
    echo "❌ research history compatibility projection failed exit_code=$BACKFILL_EXIT_CODE" | tee -a "$LOG_FILE"
    exit "$BACKFILL_EXIT_CODE"
  fi

  set +e
  "${RUNNER_CMD[@]}" scripts/verify_research_map_run_history_backfill.py >> "$LOG_FILE" 2>&1
  BACKFILL_VERIFY_EXIT_CODE=$?
  set -e

  if [ "$BACKFILL_VERIFY_EXIT_CODE" -ne 0 ]; then
    echo "❌ research map backfill verification failed exit_code=$BACKFILL_VERIFY_EXIT_CODE" | tee -a "$LOG_FILE"
    exit "$BACKFILL_VERIFY_EXIT_CODE"
  fi

  set +e
  TOP10_RESEARCH_PYTHON="$PYTHON_BIN" TOP10_RESEARCH_DATE="$RUN_DATE" \
    bash scripts/refresh_research_map_from_history.sh >> "$LOG_FILE" 2>&1
  MAP_REFRESH_EXIT_CODE=$?
  set -e

  if [ "$MAP_REFRESH_EXIT_CODE" -ne 0 ]; then
    echo "❌ research map refresh failed exit_code=$MAP_REFRESH_EXIT_CODE" | tee -a "$LOG_FILE"
    exit "$MAP_REFRESH_EXIT_CODE"
  fi
fi

echo "✅ 每日研究配額完成 output=$OUTPUT" | tee -a "$LOG_FILE"
exit 0
