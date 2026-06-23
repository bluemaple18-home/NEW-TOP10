# WEEKEND-TRAINING-08｜Unsupported Reason Breakdown

## Root Question

Weekend rollup 顯示：

```text
unsupported_count: 574,695
```

這個數字太大。若不拆原因，使用者會合理懷疑：

```text
是不是你把大部分宇宙丟掉？
是不是資料或 runner 沒接好？
```

## 任務目的

把 unsupported 拆成可理解、可驗證、可後續處理的原因。

## Input

- `artifacts/weekend_training/weekend_universe_inventory_YYYY-MM-DD.json`
- `scripts/build_weekend_universe_inventory.py`
- `scripts/verify_weekend_universe_inventory.py`

## Output

- 更新 `scripts/build_weekend_universe_inventory.py`
- 更新 `scripts/verify_weekend_universe_inventory.py`
- 更新 `artifacts/weekend_training/weekend_universe_inventory_YYYY-MM-DD.json`
- 更新 `artifacts/weekend_training/weekend_universe_inventory_YYYY-MM-DD.md`

## Required Breakdown

至少拆：

```text
UNSUPPORTED_RANKING_DIR_MISSING
UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE
UNSUPPORTED_TOPIC_NO_CANDIDATE_DIR
UNSUPPORTED_REGIME_SLICE_NO_DATA
UNSUPPORTED_RUNNER_CONTRACT
UNSUPPORTED_OTHER
```

每個 unsupported record 必須有：

```text
unsupported_reason
unsupported_category
can_be_unblocked
unblock_requirement
```

## 驗收

- `unsupported_count` 必須等於各 category 加總。
- Markdown 必須列出 top unsupported categories。
- 可解除的 unsupported 要列 next action。
- 不可解除的 unsupported 要有 deterministic reason。
- verifier 能擋 missing reason / missing category。

## Verification

```bash
.venv/bin/python scripts/build_weekend_universe_inventory.py --date 2026-06-13
.venv/bin/python scripts/verify_weekend_universe_inventory.py --date 2026-06-13
.venv/bin/python scripts/build_weekend_training_rollup.py --date 2026-06-13
.venv/bin/python scripts/verify_weekend_training_rollup.py --date 2026-06-13
git diff --check
```

## Production Impact

`NO_PRODUCTION_CHANGE`
