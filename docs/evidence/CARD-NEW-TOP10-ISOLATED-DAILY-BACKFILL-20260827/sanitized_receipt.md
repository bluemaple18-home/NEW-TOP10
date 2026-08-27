# Isolated daily backfill sanitized receipt

- schema_version: top10-isolated-daily-backfill.v1
- status: DELIVERED_CANDIDATE
- date_range: 2026-08-03..2026-08-26
- completed_count: 18
- skipped_count: 6
- capacity_status: PASS
- formal_baseline_status: PASS
- output_scope: artifacts/isolated_daily_backfill/2026-08-03_2026-08-26
- runtime_artifacts_tracked: false
- production_write_allowed: false
- scheduler_change_allowed: false
- rollback_guidance: remove only the isolated output root after verifying it resolves under the isolated backfill root; no destructive command is serialized.
