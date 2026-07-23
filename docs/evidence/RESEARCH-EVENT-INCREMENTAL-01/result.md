# RESEARCH-EVENT-INCREMENTAL-01 Evidence

status: NO-GO（unconstrained overlay）

## Evidence

- walk-forward：`artifacts/model_experiments/event_incremental_walkforward_2026-07-23.json`
- portfolio replay：`artifacts/model_experiments/event_point_in_time_portfolio_replay_2026-07-23.json`
- verifier：
  - `.venv/bin/python scripts/verify_feature_group_regime_walkforward.py`
  - `.venv/bin/python scripts/verify_chip_point_in_time_portfolio_replay.py`

## Data facts

- event features：13 欄。
- mature window：252 日、`2025-06-26`～`2026-07-08`。
- 所有 event 欄位整體與逐日 coverage 均為 100%。
- `2026-01-16` features 有 TWSE 1,065 檔、TPEX 0 檔；受影響的 `2026-01-02` cohort 已對所有 variants 成對排除。

## Incremental result

- OOS days：56
- weighted partial IC：`0.015619`
- stable buckets：4
- positive bucket rate：`1.0`
- decision：`INCREMENTAL_WALKFORWARD_CANDIDATE`

## Cost-aware replay

| Variant | Return delta | Positive folds | Turnover delta | Industry exposure delta | Decision |
|---|---:|---:|---:|---:|---|
| event 10% | 0.007478 | 4/5 | 0.129630 | -0.005454 | REJECTED |
| event 20% | 0.008784 | 4/5 | 0.214815 | 0.001819 | REJECTED |

## Acceptance mapping

- incremental IC gate：PASS。
- return delta > 0：PASS。
- positive folds >= 3：PASS。
- turnover delta <= 0.10：FAIL（10%、20%）。
- industry exposure不惡化：10% PASS；20% FAIL。
- production unchanged：PASS。

## Interpretation

Event 訊號具有獨立 alpha，但直接 rerank 會製造過多換手。不能直接加分；下一個合理假說是保留部分 baseline 名單的 constrained overlay，重新預註冊後檢驗。

## Limits

下一輪 constrained replay 仍會共用本輪 OOS，只能作設計診斷。即使通過，也必須進新日期 append-only shadow，不能直接 promotion。
