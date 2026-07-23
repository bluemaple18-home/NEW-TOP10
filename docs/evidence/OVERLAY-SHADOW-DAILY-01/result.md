# OVERLAY-SHADOW-DAILY-01 Evidence

status: GO（daily research monitor wiring）／WAITING（D+10 mature data）

## Data contract

- source and grain：`data/clean/features.parquet`，`stock_id × trade_date`。
- regime history：append-only；既有日期使用 base label，新日期才可追加。
- shadow ledgers：ranking date 唯一；warning key 為 `record + reason_code + stage`。
- current source end：`2026-07-23`。
- current mature end：`2026-07-08`。
- confirmed waiting reason：`2026-07-09` 後只有 9 個交易日，尚未完成 D+10。

## Runtime receipt

- combined status：`OK`
- regime history：281 days，end `2026-07-23`
- Chip：`WAITING_FOR_NEW_OOS_DATES`，`0/60`，本次 appended `0`
- Event：`WAITING_FOR_NEW_OOS_DATES`，`0/60`，本次 appended `0`
- promotion allowed：`false`
- changes production ranking：`false`

## Idempotence

連續執行兩次，兩 ledger 的：

- observations 完全相同。
- warnings and exclusions 完全相同。
- `observations_appended=0`。
- `warnings_appended=0`。

## Verification

```bash
.venv/bin/python -m py_compile \
  scripts/run_overlay_shadow_daily_monitor.py \
  scripts/verify_overlay_shadow_daily_monitor.py \
  scripts/run_automation.py \
  app/automation/daily_orchestrator.py
.venv/bin/python scripts/run_overlay_shadow_daily_monitor.py
.venv/bin/python scripts/verify_overlay_shadow_daily_monitor.py
.venv/bin/python scripts/verify_chip_overlay_append_only_shadow.py
.venv/bin/python -m pytest \
  tests/test_daily_automation_orchestrator.py \
  tests/test_overlay_shadow_daily_automation.py -q
git diff --check
```

## Failure isolation

- daily config 已明確啟用 `overlay_append_only_shadow_enabled=true`。
- automation 以 `allow_failure=true` 執行。
- synthetic research failure 只記錄 `WARN` artifact step，不向 production daily 拋例外。

## Remaining risk

- 尚無 seal 後成熟 outcome，因此沒有新的績效證據。
- 本卡只確保新資料成熟時會自動追加，不能提前完成 60 日 acceptance。
