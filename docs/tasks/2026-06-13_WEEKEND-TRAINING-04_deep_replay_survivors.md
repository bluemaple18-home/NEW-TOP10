# WEEKEND-TRAINING-04｜Deep Replay for Survivors

## 目的

只針對 `NEXT_STAGE_CANDIDATE` 做深度驗證。

這張卡不是為了增加星圖完成度，而是防止假訊號進入下週研究主線。

## Input

- `artifacts/weekend_training/weekend_representative_replay_YYYY-MM-DD.json`
- `artifacts/research_reviews/liquidity_replay_v2_stage2_YYYY-MM-DD.json`
- 既有 long-window ranking / historical features

## Output

- `scripts/run_weekend_survivor_deep_replay.py`
- `scripts/verify_weekend_survivor_deep_replay.py`
- `artifacts/weekend_training/weekend_survivor_deep_replay_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_survivor_deep_replay_YYYY-MM-DD.md`

## Deep Replay Checks

至少包含：

```text
recent_100
recent_6m
available_long_window
BIG_BULL slice
HIGH_CHOPPY_CONTEXT slice
RISK_OFF/PANIC slice
same-exit ranking isolation if applicable
```

## Decision

```text
KEEP_FOR_NEXT_RESEARCH:
  多窗口不只單一窗口贏
  risk metrics 沒惡化
  不依賴單一 regime

MONITOR_ONLY:
  有 alpha 但依賴特定 regime 或 risk gate

REJECT:
  長窗失效或風險不可接受
```

## Verification

```bash
.venv/bin/python scripts/run_weekend_survivor_deep_replay.py --date 2026-06-13
.venv/bin/python scripts/verify_weekend_survivor_deep_replay.py --date 2026-06-13
git diff --check
```
