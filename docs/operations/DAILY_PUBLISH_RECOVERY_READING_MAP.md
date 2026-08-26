# Daily Publish Recovery Reading Map

## Read first — NEW-TOP10

- `scripts/com.new-top10.daily.plist`
- `scripts/setup_launchd.sh`
- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`
- `scripts/run_automation.py`
- `app/automation/daily_orchestrator.py`
- `scripts/send_clawd_publish_message.py`
- `scripts/send_top10_ops_report.py`
- `scripts/verify_daily_publish_workflow.py`
- `scripts/verify_scheduler_ownership.py`
- `config/automation.yaml`
- `docs/AUTOMATION.md`

## Read first — New-clawd

- `package.json`
- `openclaw.mjs`
- `docs/cli/message.md`
- `docs/cli/status.md`
- `docs/cli/health.md`
- `docs/cli/doctor.md`

## Do not read by default

- ranking / model / backtest internals
- Research Spine A1–A6 implementation areas
- unrelated external-review / fog-map internals
- old Clawd forks unless live evidence shows the active checkout is the old fork

## Stop reading when

The live failure is classified into one exact boundary and there is enough evidence to produce a bounded repair plus a regression test.
