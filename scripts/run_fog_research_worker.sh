#!/bin/bash
# Fog Map / Research Worker 受控長跑入口。
# 只跑白名單研究 quota、刷新 fog map、寫 harness events；不送外部 AI、不改 ranking/model。

set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# 背景研究預設限制數值函式庫為單執行緒，避免 BLAS／OpenMP 在 16 GiB 主機上
# 同時建立多份工作區。手動診斷仍可用明確環境變數覆寫。
: "${OMP_NUM_THREADS:=1}"
: "${OPENBLAS_NUM_THREADS:=1}"
: "${MKL_NUM_THREADS:=1}"
: "${NUMEXPR_NUM_THREADS:=1}"
: "${VECLIB_MAXIMUM_THREADS:=1}"
export OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS NUMEXPR_NUM_THREADS VECLIB_MAXIMUM_THREADS

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
LOG_FILE="$LOG_DIR/fog_research_worker_bootstrap.log"
LOCK_DIR="$LOG_DIR/fog_research_worker.lock"
LOCK_PID_FILE="$LOCK_DIR/pid"
LOCK_START_TOKEN_FILE="$LOCK_DIR/start_token"
PM_LOCK_DIR="$LOG_DIR/pm_research_harness_loop.lock"
PM_LOCK_PID_FILE="$PM_LOCK_DIR/pid"
PM_LOCK_START_TOKEN_FILE="$PM_LOCK_DIR/start_token"
QUOTA="${TOP10_FOG_RESEARCH_QUOTA:-${TOP10_RESEARCH_QUOTA:-5}}"
MAX_BATCHES="${TOP10_FOG_RESEARCH_MAX_BATCHES:-6}"
MAX_SECONDS="${TOP10_FOG_RESEARCH_MAX_SECONDS:-7200}"
BATCH_SLEEP_SECONDS="${TOP10_FOG_RESEARCH_BATCH_SLEEP_SECONDS:-30}"
QUEUE_OWNER="${TOP10_RESEARCH_QUEUE_OWNER:-fog_worker}"
QUEUE_OWNER_LOCK_DIR="$LOG_DIR/research_queue_owner.lock"
QUEUE_OWNER_PID_FILE="$QUEUE_OWNER_LOCK_DIR/pid"
QUEUE_OWNER_NAME_FILE="$QUEUE_OWNER_LOCK_DIR/owner"
QUEUE_OWNER_START_TOKEN_FILE="$QUEUE_OWNER_LOCK_DIR/start_token"
MAX_RETRIES="${TOP10_FOG_RESEARCH_MAX_RETRIES:-3}"
RETRY_BACKOFF_SECONDS="${TOP10_FOG_RESEARCH_RETRY_BACKOFF_SECONDS:-30}"
FOG_LOCK_HELD=0
QUEUE_OWNER_LOCK_HELD=0
RUN_CONTEXT_FILE=""
PS_BIN="${TOP10_PROCESS_IDENTITY_PS_BIN:-/bin/ps}"

process_start_token() {
  local pid="$1"
  case "$pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  "$PS_BIN" -o lstart= -p "$pid" 2>/dev/null || true
}

write_lock_identity() {
  local pid_file="$1"
  local start_token_file="$2"
  local start_token=""
  start_token="$(process_start_token "$$")"
  if [ -z "$start_token" ]; then
    return 1
  fi
  printf '%s\n' "$$" > "$pid_file"
  printf '%s\n' "$start_token" > "$start_token_file"
}

lock_owner_state() {
  local pid_file="$1"
  local start_token_file="$2"
  local existing_pid=""
  local stored_start_token=""
  local actual_start_token=""

  if [ ! -r "$pid_file" ]; then
    printf '%s\n' "STALE"
    return 0
  fi
  existing_pid="$(cat "$pid_file" 2>/dev/null || true)"
  case "$existing_pid" in
    ''|*[!0-9]*)
      printf '%s\n' "STALE"
      return 0
      ;;
  esac
  if ! kill -0 "$existing_pid" 2>/dev/null; then
    printf '%s\n' "STALE"
    return 0
  fi
  if [ ! -r "$start_token_file" ]; then
    printf '%s\n' "UNKNOWN"
    return 0
  fi
  stored_start_token="$(cat "$start_token_file" 2>/dev/null || true)"
  actual_start_token="$(process_start_token "$existing_pid")"
  if [ -z "$stored_start_token" ] || [ -z "$actual_start_token" ]; then
    printf '%s\n' "UNKNOWN"
  elif [ "$stored_start_token" = "$actual_start_token" ]; then
    printf '%s\n' "ACTIVE"
  else
    printf '%s\n' "STALE"
  fi
}

lock_identity_is_current_process() {
  local pid_file="$1"
  local start_token_file="$2"
  local current_start_token=""
  [ -r "$pid_file" ] || return 1
  [ -r "$start_token_file" ] || return 1
  [ "$(cat "$pid_file" 2>/dev/null || true)" = "$$" ] || return 1
  current_start_token="$(process_start_token "$$")"
  [ -n "$current_start_token" ] || return 1
  [ "$(cat "$start_token_file" 2>/dev/null || true)" = "$current_start_token" ]
}

if [ "$QUEUE_OWNER" != "fog_worker" ]; then
  echo "fog research worker skipped; queue owner=$QUEUE_OWNER" | tee -a "$LOG_FILE"
  exit 0
fi

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    if ! write_lock_identity "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"; then
      rmdir "$LOCK_DIR" 2>/dev/null || true
      echo "fog research worker skipped; cannot establish lock identity" | tee -a "$LOG_FILE"
      exit 0
    fi
    FOG_LOCK_HELD=1
    return 0
  fi

  local existing_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  local owner_state="$(lock_owner_state "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE")"
  if [ "$owner_state" = "ACTIVE" ]; then
    echo "fog research worker skipped; existing pid=$existing_pid lock=$LOCK_DIR" | tee -a "$LOG_FILE"
    exit 0
  elif [ "$owner_state" = "UNKNOWN" ]; then
    echo "fog research worker skipped; lock identity unverified pid=$existing_pid lock=$LOCK_DIR" | tee -a "$LOG_FILE"
    exit 0
  fi

  rm -f "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"
  if rmdir "$LOCK_DIR" 2>/dev/null && mkdir "$LOCK_DIR" 2>/dev/null; then
    if ! write_lock_identity "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"; then
      rmdir "$LOCK_DIR" 2>/dev/null || true
      echo "fog research worker skipped; cannot establish lock identity" | tee -a "$LOG_FILE"
      exit 0
    fi
    FOG_LOCK_HELD=1
    return 0
  fi

  echo "fog research worker skipped; cannot acquire lock=$LOCK_DIR" | tee -a "$LOG_FILE"
  exit 0
}

acquire_queue_owner_lock() {
  if mkdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null; then
    if ! write_lock_identity "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"; then
      rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null || true
      echo "fog research worker skipped; cannot establish research queue lock identity" | tee -a "$LOG_FILE"
      exit 0
    fi
    echo "fog_worker" > "$QUEUE_OWNER_NAME_FILE"
    QUEUE_OWNER_LOCK_HELD=1
    return 0
  fi

  local existing_pid="$(cat "$QUEUE_OWNER_PID_FILE" 2>/dev/null || true)"
  local owner_state="$(lock_owner_state "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE")"
  if [ "$owner_state" = "ACTIVE" ]; then
    echo "fog research worker skipped; research queue owned by pid=$existing_pid" | tee -a "$LOG_FILE"
    exit 0
  elif [ "$owner_state" = "UNKNOWN" ]; then
    echo "fog research worker skipped; research queue lock identity unverified pid=$existing_pid" | tee -a "$LOG_FILE"
    exit 0
  fi

  rm -f "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_NAME_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"
  if rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null && mkdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null; then
    if ! write_lock_identity "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"; then
      rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null || true
      echo "fog research worker skipped; cannot establish research queue lock identity" | tee -a "$LOG_FILE"
      exit 0
    fi
    echo "fog_worker" > "$QUEUE_OWNER_NAME_FILE"
    QUEUE_OWNER_LOCK_HELD=1
    return 0
  fi

  echo "fog research worker skipped; cannot acquire research queue ownership" | tee -a "$LOG_FILE"
  exit 0
}

cleanup_locks() {
  if [ "$FOG_LOCK_HELD" = "1" ] && lock_identity_is_current_process "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"; then
    rm -f "$LOCK_PID_FILE" "$LOCK_START_TOKEN_FILE"
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  if [ "$QUEUE_OWNER_LOCK_HELD" = "1" ] && lock_identity_is_current_process "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"; then
    rm -f "$QUEUE_OWNER_PID_FILE" "$QUEUE_OWNER_NAME_FILE" "$QUEUE_OWNER_START_TOKEN_FILE"
    rmdir "$QUEUE_OWNER_LOCK_DIR" 2>/dev/null || true
  fi
}

cleanup_context() {
  if [ -n "$RUN_CONTEXT_FILE" ] && [ -f "$RUN_CONTEXT_FILE" ]; then
    rm -f -- "$RUN_CONTEXT_FILE"
  fi
  RUN_CONTEXT_FILE=""
}

cleanup() {
  cleanup_context
  cleanup_locks
}

trap cleanup EXIT INT TERM
acquire_lock
acquire_queue_owner_lock

if [ -d "$PM_LOCK_DIR" ]; then
  PM_PID="$(cat "$PM_LOCK_PID_FILE" 2>/dev/null || true)"
  PM_LOCK_STATE="$(lock_owner_state "$PM_LOCK_PID_FILE" "$PM_LOCK_START_TOKEN_FILE")"
  if [ "$PM_LOCK_STATE" = "ACTIVE" ]; then
    echo "fog research worker skipped; PM research harness active pid=$PM_PID" | tee -a "$LOG_FILE"
    exit 0
  elif [ "$PM_LOCK_STATE" = "UNKNOWN" ]; then
    echo "fog research worker skipped; PM research harness lock identity unverified pid=$PM_PID" | tee -a "$LOG_FILE"
    exit 0
  fi
fi

LEGACY_RUN_DATE="${TOP10_RUN_DATE:-}"
LEGACY_RESEARCH_DATE="${TOP10_RESEARCH_DATE:-}"
RUN_CONTEXT_FILE="$(mktemp "$LOG_DIR/fog_runtime_run_context.XXXXXX")"
if ! "$PYTHON_BIN" scripts/fog_runtime_time_authority.py --output "$RUN_CONTEXT_FILE" >> "$LOG_FILE" 2>&1; then
  echo "fog research worker failed; cannot establish immutable time context" | tee -a "$LOG_FILE"
  exit 1
fi
chmod 0444 "$RUN_CONTEXT_FILE"
RUN_CONTEXT_RELATIVE="logs/$(basename "$RUN_CONTEXT_FILE")"
RUN_DATE="$("$PYTHON_BIN" scripts/fog_runtime_time_authority.py --context "$RUN_CONTEXT_FILE" --field market_run_date)"
RUN_CONTEXT_CREATED_AT_UTC="$("$PYTHON_BIN" scripts/fog_runtime_time_authority.py --context "$RUN_CONTEXT_FILE" --field run_context_created_at_utc)"
if [ -n "$LEGACY_RUN_DATE" ] && [ "$LEGACY_RUN_DATE" != "$RUN_DATE" ]; then
  echo "fog research worker failed; TOP10_RUN_DATE mismatches immutable context" | tee -a "$LOG_FILE"
  exit 1
fi
if [ -n "$LEGACY_RESEARCH_DATE" ] && [ "$LEGACY_RESEARCH_DATE" != "$RUN_DATE" ]; then
  echo "fog research worker failed; TOP10_RESEARCH_DATE mismatches immutable context" | tee -a "$LOG_FILE"
  exit 1
fi
CONTEXT_STAMP="$(printf '%s' "$RUN_CONTEXT_CREATED_AT_UTC" | tr -cd '0-9')"
RUN_ID_BASE="fog-research-${RUN_DATE}-${CONTEXT_STAMP}"
LOG_FILE="$LOG_DIR/fog_research_worker_${RUN_DATE//-/}.log"
RETRY_STATE_FILE="$LOG_DIR/fog_research_retry_${RUN_DATE//-/}.state"
RETRY_CONTEXT_FILE="$LOG_DIR/fog_research_retry_${RUN_DATE//-/}.context.log"
export TOP10_FOG_RUN_CONTEXT="$RUN_CONTEXT_RELATIVE"
export TOP10_RUN_DATE="$RUN_DATE"
export TOP10_RESEARCH_DATE="$RUN_DATE"

export TOP10_RESEARCH_FROM_QUEUE="${TOP10_RESEARCH_FROM_QUEUE:-0}"
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

  local recovery_stamp verifier_output
  recovery_stamp="$(date +%Y%m%d%H%M%S)"
  verifier_output="$LOG_DIR/fog_research_retry_${RUN_DATE//-/}.recovery_verification_${recovery_stamp}.json"
  echo "fog research retry circuit recovery requested; verifying weekend inventory before state rotation" | tee -a "$LOG_FILE"
  set +e
  "$PYTHON_BIN" scripts/verify_weekend_universe_inventory.py \
    --date "$RUN_DATE" \
    --output "$verifier_output" >> "$LOG_FILE" 2>&1
  local verifier_exit_code=$?
  set -e
  if [ "$verifier_exit_code" -ne 0 ]; then
    echo "fog research retry circuit recovery denied; inventory verification failed output=$verifier_output" | tee -a "$LOG_FILE"
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

  NO_MORE_WORK="$("$PYTHON_BIN" - "$RUN_DATE" <<'PY'
import json
import sys
from pathlib import Path
run_date = sys.argv[1]
path = Path(f"artifacts/autonomous_research/autonomous_research_daily_quota_{run_date}.json")
if not path.exists():
    print("0")
    raise SystemExit
payload = json.loads(path.read_text(encoding="utf-8"))
outcome = payload.get("outcome") if isinstance(payload.get("outcome"), dict) else {}
topic_runs = payload.get("topic_runs") if isinstance(payload.get("topic_runs"), list) else []
decision = outcome.get("decision")
topic_supply = outcome.get("topic_supply") if isinstance(outcome.get("topic_supply"), dict) else {}
budget_incomplete = (
    decision == "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED"
    or topic_supply.get("status") == "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED"
)
terminal = decision in {"NO_EXECUTABLE_TOPIC", "TOPIC_SUPPLY_EXHAUSTED"} and not budget_incomplete
print("1" if terminal and not topic_runs else "0")
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
  if [ "$RESEARCH_STATE" = "PARTIAL_RETRYABLE_TOPIC_SUPPLY" ]; then
    echo "fog research worker continue; retryable_topic_supply state=$RESEARCH_STATE no_more_work=$NO_MORE_WORK after batch=$BATCH" | tee -a "$LOG_FILE"
  elif [ "$NO_MORE_WORK" = "1" ] || [ "$RESEARCH_STATE" = "PARTIAL_NO_MORE_WORK" ]; then
    echo "fog research worker stop; terminal_state=$RESEARCH_STATE no_more_work=$NO_MORE_WORK after batch=$BATCH" | tee -a "$LOG_FILE"
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
