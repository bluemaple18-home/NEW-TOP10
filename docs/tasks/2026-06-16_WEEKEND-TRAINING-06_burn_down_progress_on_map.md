# WEEKEND-TRAINING-06｜Burn-Down Progress on Research Map

## Root Question

目前星圖只清楚顯示 executed / run_history 進度：

```text
expanded_processed: 7,305 / 662,256
```

但 weekend rollup 已經把 full universe 全部分類：

```text
executed_replay_count
equivalence_inherited_count
rule_pruned_count
unsupported_count
low_information_count
next_stage_count
rejected_count
representative_replay_pending_count
deferred_low_priority_count
```

使用者需要一眼看懂：

```text
60 萬格到底還剩什麼沒處理？
哪些是真的 replay？
哪些是繼承 / 剪枝 / 不支援？
哪些還要跑？
```

## 任務目的

把 weekend burn-down 分類進度接進 research map。

不是改 replay 結果，不是改模型，而是把「消耗完」的定義可視化。

## Input

- `artifacts/weekend_training/weekend_training_rollup_YYYY-MM-DD.json`
- `artifacts/research_map/research_fog_map_latest.json`
- `scripts/build_research_fog_map.py`
- `scripts/verify_research_fog_map.py`

## Output

- 更新 `scripts/build_research_fog_map.py`
- 更新 `scripts/verify_research_fog_map.py`
- 更新 `artifacts/research_map/research_fog_map_latest.json`
- 更新 `artifacts/research_map/index.html`

## Map Contract

新增：

```json
"burn_down_progress": {
  "schema_version": "research-map-burn-down.v1",
  "source": "artifacts/weekend_training/weekend_training_rollup_YYYY-MM-DD.json",
  "full_universe_total": 662256,
  "executed_replay_count": 1484,
  "equivalence_inherited_count": 33198,
  "rule_pruned_count": 33216,
  "unsupported_count": 574695,
  "low_information_count": 1220,
  "next_stage_count": 52,
  "rejected_count": 4549,
  "representative_replay_pending_count": 144,
  "deferred_low_priority_count": 13698,
  "classified_total": 662256
}
```

## UI 要求

星圖上至少要同時顯示兩種進度：

```text
Executed Progress:
  真的 replay / run_history 完成多少

Burn-Down Progress:
  66 萬格已被分類多少
```

不可把 `unsupported / rule_pruned / inherited` 假裝成真的 replay。

建議顯示：

- Full universe burn-down 條。
- 分類堆疊條：
  - replay
  - inherited
  - pruned
  - unsupported
  - pending representative
  - deferred
- 右側 inspector 或底部面板顯示各分類 count。

## 禁止事項

- 不准改 production ranking。
- 不准改模型。
- 不准改 Clawd live push。
- 不准把 `unsupported` 顯示成成功。
- 不准讓 burn-down progress 取代 executed progress。
- 不准手灌數字，必須讀 rollup artifact。

## 驗收

- `research_fog_map_latest.json` 有 `burn_down_progress`。
- `burn_down_progress.classified_total == full_universe_total`。
- HTML 同時顯示 executed progress 與 burn-down progress。
- verifier 能擋：
  - 缺 rollup source
  - classified_total 不等於 full_universe_total
  - 把 burn-down 當 executed progress
- `git diff --check` OK。

## Verification

```bash
.venv/bin/python scripts/build_research_fog_map.py --date 2026-06-16
.venv/bin/python scripts/verify_research_fog_map.py --date 2026-06-16
.venv/bin/python scripts/verify_research_map_v2_schema.py
git diff --check
```

## Production Impact

`NO_PRODUCTION_CHANGE`
