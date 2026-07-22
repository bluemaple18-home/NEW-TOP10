# REVIEW-UI-MFR-01 Independent Re-review

## Verdict

`NO_GO`

The two original P1 findings and the original P2 wording finding are closed, and the
normal radar/browser path is GREEN. A new P1 remains: the repair validates with
`date.fromisoformat()` but does not enforce the declared `YYYY-MM-DD` shape. Compact and
ISO-week forms return HTTP 200 instead of the required stable 4xx error envelope.

## Findings

- `[P1]` Non-`YYYY-MM-DD` date forms still enter the valid API path - `app/api/routers/market_flow.py:25-29`
  - Trigger: `GET /api/v1/market-flow/radar?as_of_date=20260717` and
    `GET /api/v1/market-flow/radar?as_of_date=2026-W29-5`.
  - Observed: both return HTTP 200 and echo the non-contract date string in `as_of_date`.
    Python `date.fromisoformat()` accepts both forms, so the repair's validation is broader
    than the versioned `YYYY-MM-DD` API contract.
  - Risk: clients can receive a response with an invalid date representation and may cache,
    compare, or render it as a normal radar date; the required format-error boundary is not
    fail-closed.
  - Minimal fix: require an exact `^\d{4}-\d{2}-\d{2}$` shape before `date.fromisoformat()`
    (or use a strict date parser), return `INVALID_AS_OF_DATE` 422 with CORS, and add both
    regression cases to the API tests and 51-case matrix.

## Original findings closure

- Original P1 invalid calendar date 500: **CLOSED**. `2026-99-99` now returns versioned 422
  with allowed-origin CORS and no traceback response.
- Original P1 absent closed response model: **CLOSED**. The route declares nested strict
  `MarketFlowRadarResponse`; OpenAPI and runtime reject unknown/missing/type drift.
- Original P2 recommendation wording: **CLOSED**. UI now says `既有 Top10 決策層（隔離）`
  and explicitly states the radar does not read or rewrite it.

## Spec axis

`NO_GO`: read-only deterministic fixture, provenance, freshness/coverage/source/evidence,
research/Top10 separation, Graph research-only boundary, five UI states, strict response
model, valid API, POST rejection, CORS, and browser path pass. The required strict date-shape
error boundary fails for two accepted alternate ISO forms.

## Standards axis

`NO_GO`: implementation quality improved materially and all original findings are repaired,
but a client-input boundary remains fail-open. The 30-test suite passes while its negative
coverage misses compact and ISO-week date forms; the bounded matrix exposed this gap.

## Visual acceptance

`PASS`: fresh desktop/mobile screenshots show the existing dense analytical shell, no observed
overlap or page overflow, contained mobile table, keyboard focus/activation, and corrected
non-recommendation decision-layer wording. Loading, empty, error, stale, and partial state
screenshots are present. Reduced motion is supported by existing CSS and the radar adds no
animation path.

## Verification matrix

| Gate | Result | Evidence |
|---|---|---|
| Focused affected tests | PASS | 30 passed |
| Requested 51-case matrix | FAIL | strict-format gap at compact/ISO-week forms; documented in `re-review-01-api-probes.txt` |
| Python compilation | PASS | fixed API/TSKG/test files |
| Frontend build | PASS | `pnpm --dir web/frontend build` |
| Candidate diff check | PASS | `git diff --check HEAD^..HEAD` |
| API valid/error/CORS/OpenAPI/runtime | PARTIAL | all required cases pass except strict date shape |
| Browser desktop/mobile/keyboard/states | PASS | fresh CDP evidence and screenshots |
| Console/pageerror/network | PASS for radar | weekly missing-features baseline separately identified |
| Privacy/ranking/production mutation | PASS | no prohibited mutation or external live I/O observed |

## Ancestry and allowlist

Fixed candidate: `5de19a8725b2c03775abf00d756c7a3cf75d33d3`.
Parent/repair card commit: `25c3d58b37b01113cb21fae3ae4dfd15193d81c7`.
Original review evidence `97ae5b74676dfc479fa3b7b8572bd14457dc9ec1` is an ancestor.
Repair diff paths match the Repair card allowlist. This re-review adds only the
`REVIEW-UI-MFR-01` re-review evidence and screenshots; no candidate path was edited.

## Root question snapshot

```text
root question: Can the fixed read-only fixture radar be safely surfaced for research?
blocker: strict YYYY-MM-DD input still accepts 20260717 and 2026-W29-5 as 200 responses.
fork: original P1/P2 repairs are green; weekly features.parquet 500 remains an independent baseline.
current state: NO_GO; fixed candidate unchanged; no merge/deploy.
next step: enforce exact date shape, add the two negative cases, rerun 30/51/browser gates.
limits: no production mutation or external live source exercised by design.
```
