# WEEKEND-TRAINING-02｜Frontier Queue Builder

## 目的

把 full universe inventory 轉成可執行 queue。

> 2026-07-06 更新：summary-only 主線不再每次實體化 full frontier queue。若 inventory `contract.records_inline=false`，`run_controlled_grid_drain_host_runner.py` 會跳過 frontier queue 實體化，改由 inventory summary 產生 gates。完整 queue 只在 `--include-records` 或冷封存追溯場景使用。

這張卡要回答：

```text
剩下 656,199 格，到底哪些要真的 replay？
哪些可以繼承？
哪些應該直接剪枝？
```

## Input

- `artifacts/weekend_training/weekend_universe_inventory_YYYY-MM-DD.json`
- `artifacts/research_reviews/liquidity_replay_v2_stage2_YYYY-MM-DD.json`
- `artifacts/research_map/research_fog_map_latest.json`

## Output

- `scripts/build_weekend_frontier_queue.py`
- `scripts/verify_weekend_frontier_queue.py`
- `artifacts/weekend_training/weekend_frontier_queue_YYYY-MM-DD.json`（完整 records 模式或追溯封存）
- `artifacts/weekend_training/weekend_frontier_queue_YYYY-MM-DD.md`

## Queue Policy

優先順序：

1. Stage2 candidates 的鄰近維度。
2. 同 topic 中尚未測過的 `entry_filter` 變化。
3. 同 topic 中尚未測過的 `regime_gate` 變化。
4. 低集中度 `group_exposure=none/0.35` 優先於 `0.55`。
5. 已證明 concentration 風險過高的類型不進第一批昂貴 replay。

## Queue 類型

```text
REPRESENTATIVE_REPLAY
EQUIVALENCE_INHERIT
RULE_PRUNE
UNSUPPORTED
DEFERRED_LOW_PRIORITY
```

## 驗收

- queue 加總必須等於 inventory count。
- `REPRESENTATIVE_REPLAY` 必須是 bounded batch，不可一次塞滿 65 萬。
- 每個 `EQUIVALENCE_INHERIT` 必須指向代表 combo。
- 每個 `RULE_PRUNE` 必須有 rule id。
- 不得把未跑 combo 標成 `EXECUTED_REPLAY`。

## Verification

```bash
.venv/bin/python scripts/build_weekend_frontier_queue.py --date 2026-06-13
.venv/bin/python scripts/verify_weekend_frontier_queue.py --date 2026-06-13
git diff --check
```
