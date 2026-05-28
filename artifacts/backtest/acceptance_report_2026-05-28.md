# Backtest Acceptance Report

- status：OK
- portfolio final_equity：0.994463
- portfolio total_return：-0.55%
- portfolio max_drawdown：-2.59%
- portfolio max_gross_exposure：54.44%
- portfolio max_group_exposure：18.59%
- persistence trades：43
- persistence streak buckets：3

## Checks

### portfolio
- schema_ok: OK
- overlap_contract: OK
- model_feature_false: OK
- trade_count_positive: OK
- gross_exposure_capped: OK
- group_exposure_capped: OK
- group_policy_declared: OK
- event_exit_policy_declared: OK
- event_exit_fields_present: OK

### persistence
- schema_ok: OK
- model_feature_false: OK
- no_future_rankings: OK
- trade_count_positive: OK
- streak_summary_exists: OK
