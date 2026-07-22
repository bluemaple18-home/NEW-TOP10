# UI-MFR-01 Verification

## API contract

`GET /api/v1/market-flow/radar` is read-only and versioned. It deterministically loads:

- `data/fixtures/tskg/theme_membership_v1.json`
- `data/fixtures/tskg/security_flow_observations_v1.json`

The response exposes `schema_version`, `view_version`, `as_of_date`, `freshness`, `coverage`, `coverage_status`, source, evidence locators, venue coverage, allocation policy, membership snapshot hash, Theme rows, and the research boundary. No endpoint accepts a write method.

The frontend adds a Market Radar tab within the existing shell. State preview controls expose loading, empty, error, stale, and partial coverage states without mutating the API or ranking data. Graph drilldown is labeled `RESEARCH_ONLY`; the response explicitly carries `ranking_impact=NONE`.

## Tests and gates

```text
25 passed: tests/test_market_flow_radar.py
           tests/test_tskg_theme_flow.py
           tests/test_tskg_flow_read_model.py
           tests/test_tskg_mfo01.py
git diff --check: PASS
pnpm --dir web/frontend build: BLOCKED (node_modules absent; tsc not found)
```

## Browser acceptance snapshot

```text
root question: Can the read-only fixture radar be safely surfaced for research?
blocker: frontend browser runtime unavailable without Chromium and project node_modules.
fork: server/API contract verified; browser visual acceptance remains pending.
current state: candidate implementation, no deploy/merge.
next step: run pnpm build and Playwright desktop/mobile acceptance on a host with preinstalled dependencies/browser.
limits: no screenshot-only or inferred visual pass claim.
```
