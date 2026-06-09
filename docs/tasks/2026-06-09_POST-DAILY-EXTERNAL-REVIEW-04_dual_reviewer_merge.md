# POST-DAILY-EXTERNAL-REVIEW-04｜Dual Reviewer Merge

## Goal

Merge ChatGPT and Gemini external reviews into one daily summary that captures consensus, disagreement, likely misses, tomorrow watch items, and research hypotheses.

## Dependencies

- `POST-DAILY-EXTERNAL-REVIEW-02` completed or available as failed/skipped.
- `POST-DAILY-EXTERNAL-REVIEW-03` completed or available as failed/skipped.
- At least one valid `external-review.v1` response.

## Required Output

```text
artifacts/external_review/YYYY-MM-DD/external_review_summary_YYYY-MM-DD.json
artifacts/external_review/YYYY-MM-DD/external_review_summary_YYYY-MM-DD.md
```

## Required Summary Fields

- `schema_version`: `external-review-summary.v1`
- `review_date`
- `providers`
- `valid_provider_count`
- `consensus`
- `disagreements`
- `today_misses`
- `tomorrow_watch`
- `research_hypotheses`
- `safety`
- `promotion_boundary`

## Merge Rules

- Consensus requires at least two providers agreeing, or one valid provider with explicit `single_reviewer_only` flag.
- Disagreements must be preserved, not averaged away.
- Research hypotheses must remain hypotheses, not changes.
- If any reviewer violates algorithm boundary, summary must set `needs_human_review=true`.

## Out Of Scope

- Do not change ranking/model/report/publish artifacts.
- Do not mark `PROMOTION_READY`.
- Do not deduplicate away meaningful disagreement.

## Acceptance

```bash
.venv/bin/python scripts/build_external_review_summary.py --date 2026-06-08
.venv/bin/python scripts/verify_external_review_summary.py --summary artifacts/external_review/2026-06-08/external_review_summary_2026-06-08.json
.venv/bin/python -m py_compile scripts/build_external_review_summary.py scripts/verify_external_review_summary.py
git diff --check
```

## Evidence

- `artifacts/external_review/2026-06-08/external_review_summary_2026-06-08.json`
- `artifacts/external_review/2026-06-08/external_review_summary_2026-06-08.md`
