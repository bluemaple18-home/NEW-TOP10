# REVIEW-UI-MFR-01 Independent Review

## Verdict

`NO_GO`

The normal fixture radar path renders and the desktop/mobile browser path is now evidenced,
but the candidate fails the required invalid-date API boundary and does not publish a closed
response schema. No merge or deployment is approved.

## Findings

- `[P1]` Invalid calendar dates become an unhandled HTTP 500 - `app/api/routers/market_flow.py:15-17`, `app/tskg/theme_membership.py:33-39,116-120`
  - Trigger: `GET /api/v1/market-flow/radar?as_of_date=2026-99-99`.
  - Observed: HTTP 500, no JSON error envelope and no CORS header; server traceback exposes `ThemeMembershipContractError`.
  - Risk: a client-controlled date can turn a read-only API validation error into an unhandled server failure and a browser `requestfailed`; this violates the required invalid-date/error-envelope boundary.
  - Minimal fix: validate calendar dates at the router boundary or translate `ThemeMembershipContractError` to a stable 4xx JSON error response, and add invalid-calendar-date/CORS tests.

- `[P1]` Radar route has no closed response contract - `app/api/routers/market_flow.py:15-17`
  - Trigger: inspect the route/OpenAPI or return an accidentally extended/malformed dict from the builder.
  - Observed: the handler returns an untyped `dict` without `response_model`; the API has no runtime response validation or closed OpenAPI schema, while the card explicitly requires a closed response schema.
  - Risk: fixture evolution can silently leak fields or break the frontend contract; consumers cannot use the versioned endpoint as a reliably closed read model.
  - Minimal fix: define a strict Pydantic response model (`extra="forbid"`) covering the envelope/items and attach it as `response_model`; test unknown/missing/wrong-type fields.

- `[P2]` Research-only view still uses recommendation wording - `web/frontend/src/features/market-flow/MarketFlowRadar.tsx:82`
  - Trigger: read the boundary label in the radar page.
  - Observed: `Top10 recommendation` is displayed even though the surrounding copy says no buy advice and `ranking_impact=NONE`.
  - Risk: semantic ambiguity for a research screen and increased chance users interpret the radar as a recommendation surface.
  - Minimal fix: label the separated layer `既有 Top10 候補層（未受雷達影響）` or equivalent non-recommendation wording.

## Spec axis

`PARTIAL / NO_GO`: versioned deterministic fixture, provenance, freshness, coverage, research-only
boundary, Graph unavailable/research-only wording, state previews, read-only method boundary,
keyboard activation, responsive containment, and non-mutation evidence passed. Invalid-date
error handling and closed API response schema did not meet the spec.

## Standards axis

`NO_GO`: focused tests/build/compile/diff hygiene passed, but an unhandled domain exception at
the HTTP boundary and absent response model are blocking API quality issues. The frontend has
an inner table scroller and preserves the existing shell; no P1 visual overflow was found.

## Visual acceptance

`PASS WITH P2 WORDING`: screenshots show a dense analytical dashboard rather than a marketing
surface; desktop and mobile have no observed overlap or page overflow; status states are available
and captured. The table is intentionally wider than mobile and contained by `.radar-table-wrap`.
Reduced-motion review: no candidate radar animation or transition is used, so no motion path was
claimed; static state screenshots are the relevant evidence.

## Verification matrix

| Gate | Result | Evidence |
|---|---|---|
| 25 affected tests | PASS | `25 passed` (`tests/test_market_flow_radar.py`, `tests/test_tskg_theme_flow.py`, `tests/test_tskg_flow_read_model.py`, `tests/test_tskg_mfo01.py`) |
| Python compilation | PASS | API/router/TSKG/test files compiled with `/Users/mattkuo/TOP10new/.venv/bin/python` |
| Frontend build | PASS | `pnpm --dir web/frontend build`, Vite 7.3.3 |
| Candidate diff check | PASS | `git diff --check cdd4c42..a8d11a26` |
| API determinism/CORS/method | PASS | `api-probe.txt`; except invalid calendar date finding |
| Browser desktop/mobile | PASS | `browser-evidence.txt` and screenshots |
| Keyboard activation | PASS | native Enter switched to 市場雷達 |
| Console/pageerror/requestfailed | PASS for radar; baseline separated | `browser-evidence.txt` |
| Privacy/ranking/production mutation | PASS | no secret, writer, ranking mutation, or external I/O in candidate radar slice observed |

## Candidate allowlist / scope

The candidate range changed only the implementation-card paths plus candidate UI-MFR evidence;
the independent additions in this review are confined to `docs/evidence/REVIEW-UI-MFR-01/**`
and `.work/REVIEW-UI-MFR-01/**`. No candidate file was edited by this review.

## Evidence files

- `api-probe.txt`
- `browser-evidence.txt`
- `screenshots/desktop-weekly.png`
- `screenshots/desktop-radar-live.png`
- `screenshots/desktop-loading.png`
- `screenshots/desktop-empty.png`
- `screenshots/desktop-error.png`
- `screenshots/desktop-stale.png`
- `screenshots/desktop-partial.png`
- `screenshots/mobile-radar-live.png`

## Root question snapshot

```text
root question: Can the read-only fixture radar be safely surfaced for research?
blocker: invalid calendar date produces unhandled HTTP 500; response schema is not closed.
fork: radar browser path is usable and baseline weekly failure is pre-existing, but API boundary is not merge-safe.
current state: NO_GO; candidate unchanged; no deploy/merge.
next step: repair API error translation + strict response model, add negative contract tests, then re-review.
limits: no production mutation or external live source was exercised by design.
```
