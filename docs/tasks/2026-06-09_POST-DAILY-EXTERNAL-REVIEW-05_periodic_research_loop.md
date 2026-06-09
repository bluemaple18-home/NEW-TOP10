# POST-DAILY-EXTERNAL-REVIEW-05｜Periodic Research Loop

## Goal

Turn daily external review summaries into weekly pattern summaries and 20-trading-day research hypotheses without changing production behavior.

## Dependencies

- `POST-DAILY-EXTERNAL-REVIEW-04` available for multiple dates.

## Required Output

Weekly:

```text
artifacts/external_review/weekly/external_review_weekly_YYYY-MM-DD.json
artifacts/external_review/weekly/external_review_weekly_YYYY-MM-DD.md
```

Every 20 trading days:

```text
artifacts/external_review/research_hypotheses/external_review_hypotheses_YYYY-MM-DD.json
artifacts/external_review/research_hypotheses/external_review_hypotheses_YYYY-MM-DD.md
```

## Required Behavior

- Aggregate repeated misses and repeated strengths.
- Count recurring themes, risk patterns, timing problems, and overextension comments.
- Produce research hypotheses only when a pattern repeats across multiple dates.
- Each hypothesis must include validation plan: what replay/shadow test would prove or disprove it.
- If sample size is too small, output `INSUFFICIENT_DAILY_REVIEWS`.

## Out Of Scope

- Do not change model or ranking behavior.
- Do not create promotion evidence directly.
- Do not auto-open model training jobs.
- Do not send weekly output to Clawd unless a separate publish task exists.

## Acceptance

```bash
.venv/bin/python scripts/build_external_review_periodic_summary.py --weekly --end-date 2026-06-08
.venv/bin/python scripts/build_external_review_periodic_summary.py --research-window 20 --end-date 2026-06-08
.venv/bin/python scripts/verify_external_review_periodic_summary.py
.venv/bin/python -m py_compile scripts/build_external_review_periodic_summary.py scripts/verify_external_review_periodic_summary.py
git diff --check
```

## Evidence

- `artifacts/external_review/weekly/external_review_weekly_YYYY-MM-DD.json`
- `artifacts/external_review/weekly/external_review_weekly_YYYY-MM-DD.md`
- `artifacts/external_review/research_hypotheses/external_review_hypotheses_YYYY-MM-DD.json`
- `artifacts/external_review/research_hypotheses/external_review_hypotheses_YYYY-MM-DD.md`
