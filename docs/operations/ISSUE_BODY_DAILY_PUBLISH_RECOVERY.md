# INCIDENT-NEW-TOP10-DAILY-PUBLISH-RECOVERY-AND-HARDENING-V1

Priority: P0 operational recovery

Current operational authority and full scope are split across:

- `docs/operations/DAILY_PUBLISH_INCIDENT_20260827.md`
- `docs/operations/DAILY_PUBLISH_RECOVERY_READING_MAP.md`
- `docs/operations/DAILY_PUBLISH_RECOVERY_SLICES.md`
- `docs/operations/DAILY_PUBLISH_RECOVERY_ACCEPTANCE.md`

## Mission

Restore one reliable daily Top10 report to the configured Discord channel, identify the exact live failure boundary from Mac evidence, and harden the chain so a required report cannot silently disappear.

## Execution order

R0 live read-only forensics must complete before any repair. Then implement only the smallest proven R1 repair. R2–R5 require evidence-backed admission from R0/R1.

## Current repo findings

- Python runtime resolution differs between daily and publish wrapper.
- OpenClaw Node/entry/targets are hard-coded in tracked config and lack version/health compatibility checks.
- current New-clawd canonical CLI bin is `openclaw.mjs`, while Top10 config points at a personal `dist/index.js` path.
- optional analytics steps can block final report/payload even though report generation fundamentally reads ranking artifacts.
- trigger date and market/ranking/publish dates are not one explicit contract.
- publish-not-allowed can end as skipped/success instead of unexpected no-send failure.
- scheduler verifier misses legacy launchd labels.
- ops alert shares the same OpenClaw failure domain.

## Hard stops

- no ranking/model/backtest changes
- no channel/target mutation without live evidence
- no uncontrolled stale resend
- no duplicate scheduler or duplicate live message
- no Research Spine A1–A6 work during this incident

## Acceptance

Follow `docs/operations/DAILY_PUBLISH_RECOVERY_ACCEPTANCE.md`. Immediate recovery is not accepted until one controlled dry-run and one controlled live send pass with matching date, target, artifact lineage and launchd status.
