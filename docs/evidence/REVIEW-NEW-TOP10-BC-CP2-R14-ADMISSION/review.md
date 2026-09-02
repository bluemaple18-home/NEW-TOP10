# R14 admission independent review

👉 [假設與目標確認] 目標是審查固定 candidate `ea65528` 的 R14 admission NO-GO 是否由 authority、數學下界與本機 metadata 支撐；邊界是只審不修、不執行 capture/replay/capacity/outcome、不准入任何 downstream；驗收是 P0-P3 findings、Spec/Standards axes、commands 與 `REVIEW_GO/REVIEW_NO_GO`。

## Verdict

`REVIEW_GO`

Candidate `ea65528` 可接受。R14 裁決沒有把 R13 committed-bundle registration 升格成 Entry-Regime feasibility、split、preregistration 或 production authority；`NO_GO_R14_INSUFFICIENT_DECISION_VALUE` 有足夠證據支撐。核心理由不是「今天沒有新資料」，而是單日/連續 daily capture 在 h20 closed overlap component grain 下不會線性增加 independent capacity；若維持三角色、h20、雙邊界 purge/embargo 與 `n_min`，最佳情形也需要多年跨度，沒有近期 decision value。

## Review target

- Task card: `docs/tasks/2026-09-02_REVIEW-NEW-TOP10-BC-CP2-R14-ADMISSION.md`
- Candidate: `ea65528af33cb592bee63991eff1046dd3566e98`
- Parent: `0e39b550a3b1df502bef350447521037a54254af`
- Candidate changed files:
  - `docs/tasks/2026-09-02_DECIDE-NEW-TOP10-BC-CP2-R14-ADMISSION.md`
  - `docs/evidence/BC-CP2-R14-ADMISSION/01-admission-decision.md`

## Findings

- P0: none.
- P1: none.
- P2: none.
- P3 `R14-REVIEW-P3-001`: `docs/evidence/BC-CP2-R14-ADMISSION/01-admission-decision.md` says the worker changed-file allowlist was only the admission evidence file. At the commit level, `ea65528` also includes the Mainline decision task card. This is non-blocking because `docs/tasks/2026-09-02_DECIDE-NEW-TOP10-BC-CP2-R14-ADMISSION.md` explicitly treats the task card as pre-created Mainline control metadata, and the independent review card's fixed scope expects both task/evidence files. Future summaries should phrase this as "worker evidence allowlist" rather than "candidate commit allowlist."

## Recomputed gates

### R13 boundary

R13 verifier returns `REGISTERED_FORWARD_BUNDLE_VERIFIED`, four bundle files `MATCHED`, `errors=[]`, and `downstream_authority=NONE`. This proves only one committed R13-R2 forward bundle identity. It does not prove cohort eligibility, h20 calendar/path completion, global split capacity, historical corpus admission, preregistration, B0 Phase 2, B1, C1, production, push or deploy authority.

### n_min and role lower bound

The architecture contract fixes:

- `horizon_trade_bars = 20`
- roles = `development`, `validation`, `sealed`
- `minimum_embargo_trade_days = 20`
- `n_min = max(20, ceil(log2(M / 0.05)))`

For the R14-friendly lower bound `M=10`, `ceil(log2(10/0.05)) = ceil(log2(200)) = 8`, so `n_min=20`. Three roles therefore require at least `3 * 20 = 60` independent components for one predeclared cohort.

### h20 closed overlap and trading-day span

With ranking trade index `t_i`, entry is `t_i+1` and the h20 closed holding interval exits at `t_i+20`. A later component must satisfy:

```text
t_(i+1) + 1 > t_i + 20
t_(i+1) - t_i >= 20
```

Therefore:

- Single-role 20-component span: `(20 - 1) * 20 = 380` trading-day advances.
- No-boundary 60-component ranking-date span: `(60 - 1) * 20 = 1,180`.
- Contract-only loose floor with two 20-day boundary embargos and final h20 completion: `1,180 + 2 * 20 + 20 = 1,240`.
- Existing `entry-cohort-calendar-split.v1` uses fail-closed dual-side boundary rules, adding `40` extra advances per boundary versus a normal adjacent component gap: `1,180 + 2 * 40 = 1,260`.
- Last ranking date still needs h20 completion: `1,260 + 20 = 1,280` trading-day advances, or `1,281` inclusive trade-date positions.

These are lower bounds under favorable assumptions: one cohort, no missing dates, no transition exclusions, no provenance failures, no higher power-analysis requirement.

### Daily capture capacity

Daily capture does not create daily independent n. Adjacent h20 windows overlap, and overlap is transitive, so a consecutive run of captures collapses into the same overlap component until ranking dates are spaced by at least 20 trade-day indices. Post-hoc thinning would be a new selection rule and is not authorized by R14.

### Date/status metadata

The candidate's metadata claim is reproducible without reading outcome columns:

- `data/clean/features.parquet`: 516,169 rows, date type `timestamp[ns]`, max date `2026-09-01`.
- `data/clean/events.parquet`: 516,169 rows, date type `timestamp[ns]`, max date `2026-09-01`.
- `data/clean/universe.parquet`: 274,016 rows, date type `timestamp[ns]`, max date `2026-09-01`.
- `artifacts/automation_status_2026-09-01.json`: `schema_version=daily-run-status.v1`, `status=OK`, `mode=daily`, `run_date=2026-09-01`.
- `artifacts/automation_status.json`: same daily status and run date.

This supports the statement that no later completed-date authority is present, while also correctly refusing to make that the only R14 blocker.

## Spec axis

`PASS`

The decision answers the required root question, separates confirmed facts from derived lower bounds and assumptions, and selects a candidate-fork verdict. It keeps R13 registration narrow, rejects single-next-date capture and bounded accumulation for lack of decision value, rejects pure defer because date freshness is not the only blocker, and does not sneak-admit Entry-Regime feasibility or another downstream line.

## Standards axis

`PASS`

The review found no blocking evidence, scope, math, or authority defect. The candidate is read-only, outcome-free, local-only, and leaves production/runtime untouched. The suggested next move to leave BC-CP2 active frontier is a Mainline/backlog recommendation, not authorization for B0/C0/Forecast or any other line.

## Commands and exits

- CodeGraph context for R14/R13/Entry-Regime feasibility: exit 0.
- `git diff --name-status 0e39b55..ea65528`: exit 0; only R14 decision task/evidence added.
- `git diff --check 0e39b55..ea65528`: exit 0.
- `.venv/bin/python -m app.research.r13_forward_receipt_authority --verify`: exit 0; `REGISTERED_FORWARD_BUNDLE_VERIFIED`, `downstream_authority=NONE`.
- Independent math/date metadata probe: exit 0; values listed above.

## Remaining assumptions and risks

- `1,280` is a lower bound, not a proposed schedule or future admission.
- The lower bound assumes `n_min=20`; a final family definition or power analysis could increase it.
- The R13 bundle may only become one prospective component after h20 calendar/path completion and eligibility checks; it is not counted as completed feasibility evidence today.
- This review does not validate outcome quality, ranking performance, or production readiness.

## Final status

`REVIEW_GO`

No repair card is required. R14 remains `NO_GO / NOT_ADMITTED`; no waiting task, R15, recurring capture, scheduler, registry, replay, preregistration, B0 Phase 2, B1, C1, production, push or deploy is authorized by this review.
