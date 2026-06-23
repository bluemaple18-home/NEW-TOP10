# WEEKEND-TRAINING-05｜Weekend Rollup and Map Progress

## 目的

把假日訓練結果收斂成 PM 可讀的總結，並更新星圖。

這張卡負責回答：

```text
60 萬格消耗了多少？
哪些是真的 replay？
哪些是等價繼承？
哪些被剪枝？
剩下還有什麼不是技術問題，而是資料或規格問題？
下週該研究什麼？
```

## Input

- `artifacts/weekend_training/weekend_universe_inventory_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_frontier_queue_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_representative_replay_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_survivor_deep_replay_YYYY-MM-DD.json`
- `artifacts/research_map/research_fog_map_latest.json`

## Output

- `scripts/build_weekend_training_rollup.py`
- `scripts/verify_weekend_training_rollup.py`
- `artifacts/weekend_training/weekend_training_rollup_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_training_rollup_YYYY-MM-DD.md`
- refreshed `artifacts/research_map/research_fog_map_latest.json`
- refreshed `artifacts/research_map/index.html`

## Rollup 必須包含

```text
full_universe_total
processed_before
processed_after
executed_replay_count
equivalence_inherited_count
rule_pruned_count
unsupported_count
low_information_count
next_stage_count
rejected_count
top_survivors
top_failure_reasons
next_week_research_queue
production_impact
```

## 驗收

- rollup counts 必須加總對上 full universe。
- map progress 不能手灌，必須由 artifacts / run_history / queue artifact 推導。
- 不得包含 `PROMOTION_READY`。
- `production_impact == NO_PRODUCTION_CHANGE`。
- browser QA 若要聲稱通過，必須有實際頁面層證據；否則標明未跑。

## Verification

```bash
.venv/bin/python scripts/build_weekend_training_rollup.py --date 2026-06-13
.venv/bin/python scripts/verify_weekend_training_rollup.py --date 2026-06-13
bash scripts/refresh_research_map_from_history.sh
.venv/bin/python scripts/verify_research_map_v2_schema.py
.venv/bin/python scripts/verify_research_fog_map.py --date 2026-06-13
git diff --check
```
