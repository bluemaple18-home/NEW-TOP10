# SHADOW-ROLLOUT-01｜Candidate Trail10 Daily Monitor

## Root Question

長區間驗證後，如何把 `candidate ranking + trail10` 放進每日後台觀測，而不是直接改正式推播。

## Scope

- 每日可產一份 candidate ranking shadow。
- 比較 production Top10 與 candidate Top10。
- 對 candidate Top7 產生 trail10 shadow trade plan。
- 納入 daily shadow status 總覽。
- automation 接入但預設關閉。

## Non-Goals

- 不改 production ranking。
- 不改 `risk_adjusted_score`。
- 不改 daily report / Clawd 推播。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不宣稱 promotion ready。

## Artifacts

- `artifacts/model_experiments/candidate_trail10_daily_shadow_monitor_YYYY-MM-DD.json`
- `artifacts/model_experiments/candidate_trail10_daily_shadow_monitor_YYYY-MM-DD.md`
- `artifacts/model_experiments/candidate_trail10_daily_shadow_monitor_verification_latest.json`
- `artifacts/model_experiments/daily_shadow_status_YYYY-MM-DD.json`

## Contract

```text
operational_shadow_only = true
changes_production_top10_membership = false
changes_risk_adjusted_score = false
changes_production_ranking = false
changes_clawd_message = false
changes_model = false
production_switch_ready = false
promotion_ready = false
```

## Policy

```text
candidate source: current_baseline_candidate_2026-06-08
candidate Top10: shadow ranking comparison
actionable list: Top7
initial cash: 300000
max gross exposure: 0.75
max position weight: 0.12
hard stop: -12%
trail stop: high-water -10%
trail activation: after 5 trading days
max holding: 40 trading days
```

## Result

Smoke date: `2026-06-09`

```text
candidate_trail10_daily_shadow_monitor: OK
verifier: OK
daily_shadow_status includes candidate_trail10_shadow
automation dry-run includes candidate_trail10.shadow_monitor SKIPPED by config
```

## Decision

```text
READY_FOR_DAILY_SHADOW_MONITOR
```

This is still not a production switch. The next review should compare daily shadow outputs before changing user-facing ranking or messages.
