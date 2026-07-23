# RESEARCH-EVENT-CONSTRAINED-OVERLAY-01 Evidence

status: GO（shadow design）／NO-GO（production）

## Frozen design

- event weight：10%
- baseline Top10 retained：前 7 名
- candidate pool：baseline Top30
- fill count：3
- entry／exit：D+1 open／D+10 close
- costs：手續費、交易稅、滑價

## Evidence

- parent walk-forward：`artifacts/model_experiments/event_incremental_walkforward_2026-07-23.json`
- replay：`artifacts/model_experiments/event_constrained_portfolio_replay_2026-07-23.json`
- verifier：`.venv/bin/python scripts/verify_chip_point_in_time_portfolio_replay.py`

## Result

- attempted days：56
- replay days：55
- verified market-gap exclusions：1
- baseline average net return：`0.015499`
- overlay average net return：`0.021318`
- return delta：`0.005819`
- positive folds：`3/5`
- baseline turnover：`0.222222`
- overlay turnover：`0.290741`
- turnover delta：`0.068519`
- average max industry exposure delta：`-0.005454`

## Acceptance mapping

- average return delta > 0：PASS。
- positive folds >= 3：PASS。
- turnover delta <= 0.10：PASS。
- industry exposure不惡化：PASS。
- complete buckets：PASS。
- production promotion：不允許。

## Interpretation

保留 baseline 前 7 名能保留大部分 event alpha，並把換手增幅由 unconstrained 的 `0.129630` 降到 `0.068519`。此設計可凍結進前瞻 shadow。

## Limits

本研究重用 parent OOS，不能視為獨立確認。後續只能使用 seal date 之後的新成熟日期，且不得再調整 10%／7 retained／Top30 pool。
