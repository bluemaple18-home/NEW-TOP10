# WEEKEND-TRAINING-03｜Representative Replay Runner

## 目的

對 frontier queue 中的 `REPRESENTATIVE_REPLAY` 跑 replay。

這張卡才開始消耗算力；但只跑代表組，不跑等價重複組。

## Input

- `artifacts/weekend_training/weekend_frontier_queue_YYYY-MM-DD.json`
- `scripts/run_capital_aware_replay.py`
- 既有 ranking / features / market regime artifacts

## Output

- `scripts/run_weekend_representative_replay.py`
- `scripts/verify_weekend_representative_replay.py`
- `artifacts/weekend_training/weekend_representative_replay_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_representative_replay_YYYY-MM-DD.md`
- replay detail artifacts under `artifacts/weekend_training/replay_runs_YYYY-MM-DD/`

## Replay Metrics

每個 representative 至少記錄：

```text
total_return
max_drawdown
return_delta
drawdown_delta
turnover_delta
concentration_delta
trade_count
daily_count
skip_reason_counts
decision
failure_reasons
```

## Decision Policy

```text
NEXT_STAGE_CANDIDATE:
  return_delta >= 0.02
  drawdown_delta >= -0.005
  concentration_delta <= 0.03
  turnover_delta <= 0.05
  daily_count >= 80

MONITOR_ONLY:
  return_delta > 0
  but one or more risk gates fail

REJECTED:
  return_delta <= 0
  or drawdown/concentration materially worse

LOW_INFORMATION:
  daily_count < 80
  or trade_count too low
```

## Run History

完成的 representative 必須 append：

```text
artifacts/autonomous_research/run_history.jsonl
```

並包含：

```text
schema_version=research-map-run-history.v2
map_version=v2
source=weekend_representative_replay
combo_id
dimensions
decision
insight_level
artifact_path
finished_at
```

## Verification

```bash
.venv/bin/python scripts/run_weekend_representative_replay.py --date 2026-06-13 --batch-size <N> --append-run-history
.venv/bin/python scripts/verify_weekend_representative_replay.py --date 2026-06-13
bash scripts/refresh_research_map_from_history.sh
git diff --check
```
