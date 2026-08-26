# Daily Publish Recovery Implementation Slices

## R0 — Live read-only forensics

Collect:

- `launchctl print gui/$UID/com.new-top10.daily`
- installed plist content and mtime
- legacy labels: `com.clawd.newtop10`, `com.clawd.discord-notify`, `com.clawd.daily-brief`
- `crontab -l`
- current-day `launchd_daily.*`, `daily_*`, `daily_publish_*` logs
- `automation_status.json` and dated status snapshot
- ranking/report/payload/message/send-status artifacts
- resolved `.venv`, `uv`, Node and OpenClaw entry/version
- OpenClaw status/health/doctor and message dry-run evidence

Classify boundary as exactly one primary failure plus contributing factors:

- scheduler not triggered
- daily core failed
- final report/payload failed
- publish gate blocked
- OpenClaw adapter/preflight failed
- OpenClaw transport/send failed
- duplicate/legacy owner conflict

## R1 — Runtime and OpenClaw adapter repair

- one reusable Python resolver shared by daily and publish wrapper
- host-local OpenClaw command configuration; no hard-coded personal checkout in tracked config
- prefer canonical `openclaw` executable or `openclaw.mjs`, preserving supported local-checkout mode
- Node/OpenClaw version and `message send --dry-run` preflight
- explicit adapter cwd rather than deriving it from `dist/index.js` depth

## R2 — Publish availability contract

- define publish-critical steps versus optional enrichments
- generate minimal daily report/payload immediately after valid ranking and required risk gates
- optional recommendation performance/review/market enrichments use explicit degraded/allow-failure policy where they are not required for the message
- report records missing enrichments instead of silently suppressing a valid ranking

## R3 — Date/session contract

First-class fields:

- `trigger_date`
- `expected_market_session_date`
- `data_session_date`
- `ranking_date`
- `publish_date`

Replace `max_data_lag_days=7` as a publish eligibility rule with market-session-aware validation and bounded retry/wait. A non-trading session may skip cleanly; an expected trading session with stale data must fail-loud and retry, not look successful.

## R4 — Scheduler ownership and verifier repair

- current canonical schedule is repo authority: 17:30 Asia/Taipei after close
- inspect/remove legacy launchd labels only after evidence
- verifier uses one launchd inspection method and validates installed ProgramArguments/schedule
- detect legacy launchd owners in addition to cron
- add non-interactive reinstall/repair mode for launchd setup

## R5 — Health and alert independence

- `daily_publish_health_latest.json`
- last trigger / daily success / report success / live-send success timestamps
- exact terminal reason and artifact references
- independent local fallback signal when OpenClaw transport is unavailable
- watchdog after expected completion window; no duplicate live sends
