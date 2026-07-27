#!/bin/bash
# Fog Map / Research Worker 受控長跑入口。
# 只跑白名單研究 quota、刷新 fog map、寫 harness events；不送外部 AI、不改 ranking/model。

set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

if [ "${TOP10_FOG_RESEARCH_ENABLED:-1}" != "1" ]; then
  echo "fog research worker skipped; TOP10_FOG_RESEARCH_ENABLED=${TOP10_FOG_RESEARCH_ENABLED:-}"
  exit 0
fi

PYTHON_BIN="${TOP10_DAILY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
RUN_DATE="${TOP10_RUN_DATE:-$(date +%F)}"
RUN_ID_BASE="${TOP10_FOG_RESEARCH_RUN_ID:-fog-research-${RUN_DATE}-$(date +%H%M%S)}"
LOG_FILE="$LOG_DIR/fog_research_worker_$(date +%Y%m%d).log"
LOCK_DIR="$LOG_DIR/fog_research_worker.lock"
LOCK_PID_FILE="$LOCK_DIR/pid"
PM_LOCK_DIR="$LOG_DIR/pm_research_harness_loop.lock"
PM_LOCK_PID_FILE="$PM_LOCK_DIR/pid"
QUOTA="${TOP10_FOG_RESEARCH_QUOTA:-${TOP10_RESEARCH_QUOTA:-5}}"
MAX_BATCHES="${TOP10_FOG_RESEARCH_MAX_BATCHES:-6}"
MAX_SECONDS="${TOP10_FOG_RESEARCH_MAX_SECONDS:-7200}"
BATCH_SLEEP_SECONDS="${TOP10_FOG_RESEARCH_BATCH_SLEEP_SECONDS:-30}"
QUEUE_OWNER="${TOP10_RESEARCH_QUEUE_OWNER:-fog_worker}"
QUEUE_OWNER_LOCK_DIR="$LOG_DIR/research_queue_owner.lock"
QUEUE_OWNER_PID_FILE="$QUEUE_OWNER_LOCK_DIR/pid"
QUEUE_OWNER_NAME_FILE="$QUEUE_OWNER_LOCK_DIR/owner"
MAX_RETRIES="${TOP10_FOG_RESEARCH_MAX_RETRIES:-3}"
RETRY_BACKOFF_SECONDS="${TOP10_FOG_RESEARCH_RETRY_BACKOFF_SECONDS:-30}"
RETRY_STATE_FILE="$LOG_DIR/fog_research_retry_${RUN_DATE//-/}.state"
RETRY_CONTEXT_FILE="$LOG_DIR/fog_research_retry_${RUN_DATE//-/}.context.log"
FOG_LOCK_HELD=0
QUEUE_OWNER_LOCK_HELD=0

if [ "$QUEUE_OWNER" != "fog_worker" ]; then
  echo "fog research worker skipped; queue owner=$QUEUE_OWNER" | tee -a "$LOG_FILE"
  exit 0
fi

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    FOG_LOCK_HELD=1
    return 0
  fi

  local existing_pid=""
  if [ -r "$LOCK_PID_FILE" ]; then
    existing_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  fi
  if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "fog research worker skipped; existing pid=$existing_pid lock=$LOCK_DIR" | tee -a "$LOG_FILE"
    exit 0
  fi

  rm -f "$LOCK_PID_FILE"
  if rmdir "$LOCK_DIR" 2>/dev/null && mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    FOG_LOCK_HELD=1
    return 0
  fi

  echo "fog research worker skipped; cannot acquire lock=$LOCK_DIR" | tee -a "$LOG_FILE"
  exit 0
}

acquire_queue_owner_lock() {
  if mkdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$QUEUE_OWNER_PID_FILE"
    echo "fog_worker" > "$QUEUE_OWNER_NAME_FILE"
    QUEUE_OWNER_LOCK_HELD=1
    return 0
  fi

  local existing_pid=""
  if [ -r "$QUEUE_OWNER_PID_FILE" ]; then
    existing_pid="$(cat "$QUEUE_OWNER_PID_FILE" 2>/dev/null || true)"
  fi
  if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "fog research worker skipped; research queue owned by pid=$existing_pid" | tee -a "$LOG_FILE"
    exit 0
  fi

  rm -f "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_NAME_FILE"
  if rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null && mkdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$QUEUE_OWNER_PID_FILE"
    echo "fog_worker" > "$QUEUE_OWNER_NAME_FILE"
    QUEUE_OWNER_LOCK_HELD=1
    return 0
  fi

  echo "fog research worker skipped; cannot acquire research queue ownership" | tee -a "$LOG_FILE"
  exit 0
}

cleanup_locks() {
  if [ "$FOG_LOCK_HELD" = "1" ] && [ -r "$LOCK_PID_FILE" ] && [ "$(cat "$LOCK_PID_FILE")" = "$$" ]; then
    rm -f "$LOCK_PID_FILE"
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  if [ "$QUEUE_OWNER_LOCK_HELD" = "1" ] && [ -r "$QUEUE_OWNER_PID_FILE" ] && [ "$(cat "$QUEUE_OWNER_PID_FILE")" = "$$" ]; then
    rm -f "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_NAME_FILE"
    rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null || true
  fi
}

acquire_lock
acquire_queue_owner_lock
trap cleanup_locks EXIT INT TERM

if [ -r "$PM_LOCK_PID_FILE" ]; then
  PM_PID="$(cat "$PM_LOCK_PID_FILE" 2>/dev/null || true)"
  if [ -n "$PM_PID" ] && kill -0 "$PM_PID" 2>/dev/null; then
    echo "fog research worker skipped; PM research harness active pid=$PM_PID" | tee -a "$LOG_FILE"
    exit 0
  fi
fi

export TOP10_RESEARCH_FROM_QUEUE="${TOP10_RESEARCH_FROM_QUEUE:-1}"
export TOP10_RESEARCH_ALLOW_RERUN="${TOP10_RESEARCH_ALLOW_RERUN:-0}"
export TOP10_REFRESH_RESEARCH_MAP="${TOP10_REFRESH_RESEARCH_MAP:-1}"

echo "========================================" | tee -a "$LOG_FILE"
echo "fog research worker start - $(date)" | tee -a "$LOG_FILE"
echo "run_date: $RUN_DATE" | tee -a "$LOG_FILE"
echo "run_id_base: $RUN_ID_BASE" | tee -a "$LOG_FILE"
echo "quota: $QUOTA" | tee -a "$LOG_FILE"
echo "max_batches: $MAX_BATCHES" | tee -a "$LOG_FILE"
echo "max_seconds: $MAX_SECONDS" | tee -a "$LOG_FILE"
echo "from_queue: $TOP10_RESEARCH_FROM_QUEUE" | tee -a "$LOG_FILE"
echo "allow_rerun: $TOP10_RESEARCH_ALLOW_RERUN" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

START_EPOCH="$(date +%s)"
BATCH=1
EXIT_CODE=0
LAST_ROLLUP_EXIT_CODE=0
CIRCUIT_OPEN=0
BATCH_LOG_START_LINE=0

recover_retry_circuit_if_verified() {
  if [ "${TOP10_FOG_RESEARCH_RECOVER_CIRCUIT:-0}" != "1" ]; then
    return 1
  fi

  local recovery_stamp verifier_output regime_history runtime_receipt production_baseline
  recovery_stamp="$(date +%Y%m%d%H%M%S)"
  verifier_output="$LOG_DIR/fog_research_retry_${RUN_DATE//-/}.recovery_verification_${recovery_stamp}.json"
  regime_history="${TOP10_MARKET_REGIME_HISTORY:-artifacts/autonomous_research/market_regime_history_${RUN_DATE}.json}"
  runtime_receipt="artifacts/autonomous_research/closed_regime_runtime_${RUN_DATE}.json"
  production_baseline="${TOP10_FOG_PRODUCTION_HASH_BASELINE:-}"
  if [ -z "$production_baseline" ]; then
    echo "fog research retry circuit recovery denied; trusted production baseline missing" | tee -a "$LOG_FILE"
    return 1
  fi
  echo "fog research retry circuit recovery requested; running bounded recovery gates before state rotation" | tee -a "$LOG_FILE"
  set +e
  "$PYTHON_BIN" scripts/verify_fog_closed_regime_recovery.py \
    --run-date "$RUN_DATE" \
    --market-regime-history "$regime_history" \
    --closed-regime-runtime-receipt "$runtime_receipt" \
    --production-hash-baseline "$production_baseline" \
    --output "$verifier_output" >> "$LOG_FILE" 2>&1
  local verifier_exit_code=$?
  set -e
  if [ "$verifier_exit_code" -ne 0 ]; then
    echo "fog research retry circuit recovery denied; bounded recovery gate failed output=$verifier_output" | tee -a "$LOG_FILE"
    return 1
  fi

  if [ -f "$RETRY_STATE_FILE" ]; then
    mv "$RETRY_STATE_FILE" "$RETRY_STATE_FILE.recovered.$recovery_stamp"
  fi
  if [ -f "$RETRY_CONTEXT_FILE" ]; then
    mv "$RETRY_CONTEXT_FILE" "$RETRY_CONTEXT_FILE.recovered.$recovery_stamp"
  fi
  echo "fog research retry circuit recovered after verification output=$verifier_output" | tee -a "$LOG_FILE"
  return 0
}

if [ -f "$RETRY_STATE_FILE" ] && grep -qx "circuit_open=1" "$RETRY_STATE_FILE"; then
  if ! recover_retry_circuit_if_verified; then
    echo "fog research worker skipped; retry circuit remains open state=$RETRY_STATE_FILE context=$RETRY_CONTEXT_FILE" | tee -a "$LOG_FILE"
    exit 0
  fi
fi

record_failure() {
  local current_batch_start failure_detail fingerprint previous_fingerprint previous_attempts attempt
  current_batch_start=$((BATCH_LOG_START_LINE + 1))
  failure_detail="$(awk -v start="$current_batch_start" 'NR >= start && /TOP10_FOG_MAP_HANDOFF_FAILED/ { detail = $0 } END { print detail }' "$LOG_FILE")"
  if [ -z "$failure_detail" ]; then
    failure_detail="fog_map_handoff_exit_$EXIT_CODE"
  fi
  fingerprint="$(printf '%s' "$failure_detail" | shasum -a 256 | awk '{print $1}')"
  previous_fingerprint="$(sed -n 's/^fingerprint=//p' "$RETRY_STATE_FILE" 2>/dev/null | head -n 1)"
  previous_attempts="$(sed -n 's/^attempts=//p' "$RETRY_STATE_FILE" 2>/dev/null | head -n 1)"
  if [ "$fingerprint" = "$previous_fingerprint" ] && [ -n "$previous_attempts" ]; then
    attempt=$((previous_attempts + 1))
  else
    attempt=1
  fi
  {
    echo "fingerprint=$fingerprint"
    echo "attempts=$attempt"
    echo "last_exit_code=$EXIT_CODE"
    echo "circuit_open=0"
  } > "$RETRY_STATE_FILE"
  tail -n +"$current_batch_start" "$LOG_FILE" > "$RETRY_CONTEXT_FILE"
  echo "$attempt"
}

while [ "$BATCH" -le "$MAX_BATCHES" ]; do
  NOW_EPOCH="$(date +%s)"
  ELAPSED=$((NOW_EPOCH - START_EPOCH))
  if [ "$ELAPSED" -ge "$MAX_SECONDS" ]; then
    echo "fog research worker stop; max_seconds reached elapsed=$ELAPSED max_seconds=$MAX_SECONDS" | tee -a "$LOG_FILE"
    break
  fi

  RUN_ID="${RUN_ID_BASE}-b${BATCH}"
  echo "fog research batch start batch=$BATCH run_id=$RUN_ID elapsed=$ELAPSED" | tee -a "$LOG_FILE"
  BATCH_LOG_START_LINE="$(wc -l < "$LOG_FILE")"

  set +e
  "$PYTHON_BIN" scripts/run_top10_fog_map_handoff.py \
    --run-date "$RUN_DATE" \
    --run-id "$RUN_ID" \
    --research-quota "$QUOTA" >> "$LOG_FILE" 2>&1
  EXIT_CODE=$?
  set -e

  set +e
  "$PYTHON_BIN" scripts/build_top10_agent_status_rollup.py \
    --run-date "$RUN_DATE" \
    --run-id "$RUN_ID" \
    --no-latest >> "$LOG_FILE" 2>&1
  LAST_ROLLUP_EXIT_CODE=$?
  set -e

  if [ "$EXIT_CODE" -ne 0 ]; then
    RETRY_ATTEMPT="$(record_failure)"
    echo "fog research batch failed batch=$BATCH exit_code=$EXIT_CODE fingerprint_state=$RETRY_STATE_FILE attempt=$RETRY_ATTEMPT/$MAX_RETRIES" | tee -a "$LOG_FILE"
    if [ "$RETRY_ATTEMPT" -ge "$MAX_RETRIES" ]; then
      sed -i '' 's/^circuit_open=.*/circuit_open=1/' "$RETRY_STATE_FILE"
      echo "fog research retry circuit opened; retries exhausted fingerprint_state=$RETRY_STATE_FILE context=$RETRY_CONTEXT_FILE" | tee -a "$LOG_FILE"
      CIRCUIT_OPEN=1
      EXIT_CODE=0
      break
    fi
    BATCH=$((BATCH + 1))
    BACKOFF_SECONDS=$((RETRY_BACKOFF_SECONDS * RETRY_ATTEMPT))
    echo "fog research retry backoff seconds=$BACKOFF_SECONDS next_batch=$BATCH" | tee -a "$LOG_FILE"
    sleep "$BACKOFF_SECONDS"
    continue
  fi

  rm -f "$RETRY_STATE_FILE" "$RETRY_CONTEXT_FILE"

  if [ "$LAST_ROLLUP_EXIT_CODE" -ne 0 ]; then
    echo "fog research batch rollup warning batch=$BATCH exit_code=$LAST_ROLLUP_EXIT_CODE" | tee -a "$LOG_FILE"
  fi

  echo "fog research batch finished batch=$BATCH run_id=$RUN_ID" | tee -a "$LOG_FILE"

  QUEUE_EMPTY="$("$PYTHON_BIN" - "$RUN_DATE" <<'PY'
import json
import sys
from pathlib import Path
run_date = sys.argv[1]
path = Path(f"artifacts/autonomous_research/autonomous_research_daily_quota_{run_date}.json")
if not path.exists():
    print("0")
    raise SystemExit
payload = json.loads(path.read_text(encoding="utf-8"))
inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
outcome = payload.get("outcome") if isinstance(payload.get("outcome"), dict) else {}
topic_runs = payload.get("topic_runs") if isinstance(payload.get("topic_runs"), list) else []
print("1" if inputs.get("from_queue") is True and outcome.get("decision") == "NO_EXECUTABLE_TOPIC" and not topic_runs else "0")
PY
)"
  RESEARCH_STATE="$("$PYTHON_BIN" - "$RUN_DATE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(f"artifacts/autonomous_research/daily_research_quota_verification_latest.json")
if not path.exists():
    print("UNKNOWN")
    raise SystemExit
payload = json.loads(path.read_text(encoding="utf-8"))
print(payload.get("status") or "UNKNOWN")
PY
)"
  if [ "$QUEUE_EMPTY" = "1" ] || [ "$RESEARCH_STATE" = "PARTIAL_NO_MORE_WORK" ]; then
    echo "fog research worker stop; terminal_state=$RESEARCH_STATE queue_empty=$QUEUE_EMPTY after batch=$BATCH" | tee -a "$LOG_FILE"
    break
  fi

  BATCH=$((BATCH + 1))
  if [ "$BATCH" -le "$MAX_BATCHES" ] && [ "$BATCH_SLEEP_SECONDS" -gt 0 ]; then
    sleep "$BATCH_SLEEP_SECONDS"
  fi
done

if [ "$LAST_ROLLUP_EXIT_CODE" -ne 0 ]; then
  echo "fog research worker last rollup warning exit_code=$LAST_ROLLUP_EXIT_CODE" | tee -a "$LOG_FILE"
fi

if [ "$EXIT_CODE" -eq 0 ] && [ "$CIRCUIT_OPEN" -eq 0 ] && [ "${TOP10_REPLAY_DRAIN_ENABLED:-1}" = "1" ]; then
  REPLAY_RUN_ID="${RUN_ID_BASE}-replay-drain"
  REPLAY_BATCH_SIZE="${TOP10_REPLAY_DRAIN_BATCH_SIZE:-24}"
  REPLAY_MAX_BATCHES="${TOP10_REPLAY_DRAIN_MAX_BATCHES:-6}"
  REPLAY_MAX_SECONDS="${TOP10_REPLAY_DRAIN_MAX_SECONDS:-7200}"
  echo "representative replay drain start run_id=$REPLAY_RUN_ID batch_size=$REPLAY_BATCH_SIZE max_batches=$REPLAY_MAX_BATCHES" | tee -a "$LOG_FILE"
  set +e
  "$PYTHON_BIN" scripts/run_representative_replay_drain_worker.py \
    --date "$RUN_DATE" \
    --run-id "$REPLAY_RUN_ID" \
    --batch-size "$REPLAY_BATCH_SIZE" \
    --max-batches "$REPLAY_MAX_BATCHES" \
    --max-seconds "$REPLAY_MAX_SECONDS" >> "$LOG_FILE" 2>&1
  REPLAY_EXIT_CODE=$?
  set -e

  set +e
  "$PYTHON_BIN" scripts/build_top10_agent_status_rollup.py \
    --run-date "$RUN_DATE" \
    --run-id "$REPLAY_RUN_ID" \
    --no-latest >> "$LOG_FILE" 2>&1
  REPLAY_ROLLUP_EXIT_CODE=$?
  set -e

  if [ "$REPLAY_EXIT_CODE" -ne 0 ]; then
    echo "representative replay drain failed exit_code=$REPLAY_EXIT_CODE" | tee -a "$LOG_FILE"
    EXIT_CODE="$REPLAY_EXIT_CODE"
  else
    echo "representative replay drain finished" | tee -a "$LOG_FILE"
  fi
  if [ "$REPLAY_ROLLUP_EXIT_CODE" -ne 0 ]; then
    echo "representative replay drain rollup warning exit_code=$REPLAY_ROLLUP_EXIT_CODE" | tee -a "$LOG_FILE"
  fi
else
  echo "representative replay drain skipped; exit_code=$EXIT_CODE enabled=${TOP10_REPLAY_DRAIN_ENABLED:-1}" | tee -a "$LOG_FILE"
fi

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "fog research worker finished - $(date)" | tee -a "$LOG_FILE"
else
  echo "fog research worker failed - $(date) exit_code=$EXIT_CODE" | tee -a "$LOG_FILE"
fi

exit "$EXIT_CODE"
