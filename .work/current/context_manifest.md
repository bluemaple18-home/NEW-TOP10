---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-CONTEXT
status: READY_FOR_DISPATCH
type: handoff
---

# Context Manifest

## Read first

- `docs/tasks/2026-07-28_FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01_handoff.md`
- `docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_I5_live_acceptance.md`
- `docs/tasks/2026-07-28_FOG-DAILY-SOURCE-LINEAGE-01.md`
- `docs/evidence/FOG-DAILY-SOURCE-LINEAGE-01/verification.md`

## Code only when needed

- `scripts/run_autonomous_research.py`：
  topic generation、eligibility與index／fallback／queue selection。
- `scripts/run_backtest_strategy_matrix.py`：
  只讀 exact-regime second-line guard；本卡禁止修改。
- `tests/test_regime_research_autonomy.py`：
  既有 ineligible selection regression。

## Local-only runtime evidence

- `artifacts/autonomous_research/run_2026-07-28_115728`

此 artifact預設不進 Git，只用於重現已確認的 blocker。新對話不得重跑 live
worker來替代 deterministic fixture。

## Boundary

- 只處理 exact-regime topic eligibility。
- 不處理 canary mode、production promotion或 I5 live acceptance。
- 不載入舊產業／元大／Fundamental handoff；與本 root question無關。
