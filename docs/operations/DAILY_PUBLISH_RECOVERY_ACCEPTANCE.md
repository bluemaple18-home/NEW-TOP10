# Daily Publish Recovery Acceptance

## Immediate recovery

- exactly one active daily scheduler owner
- installed job points to current repo `scripts/run_daily_publish.sh`
- active Python / Node / OpenClaw paths and versions recorded
- current OpenClaw `message send` dry-run passes
- one controlled live publish succeeds with correct date/channel/target
- latest automation, report, payload, message, send-status and launchd exit evidence agree

## Hardening

- publish wrapper uses the same resolved Python runtime contract as daily
- no tracked absolute personal checkout path is required for OpenClaw
- canonical OpenClaw CLI entry/version is preflighted
- trigger date, expected market session date, ranking date and publish date are explicit
- unexpected no-send on a required trading session exits non-zero
- optional analytics/research enrichments cannot suppress a valid ranking report without an explicit policy reason
- legacy launchd labels and cron ownership are detected
- local health artifact records last successful daily and last successful live send
- transport failure remains visible even when OpenClaw itself is unavailable
- tests cover success, daily failure, stale market data, payload failure, CLI missing, send failure, duplicate scheduler and orphan/no-terminal-send states

## Non-regression

- ranking math unchanged
- model files unchanged
- backtest logic unchanged
- Discord target not changed without owner evidence
- no duplicate live message during recovery
