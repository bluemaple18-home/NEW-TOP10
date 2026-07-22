# UI-MFR-01 Acceptance

Status: `CANDIDATE / BROWSER-NO-GO`

## Scope

- Versioned read-only Theme flow API and existing-shell radar view.
- Approved deterministic Theme membership and Security flow fixtures only.
- Theme flow, date, freshness, coverage, source/evidence, buy/sell/net, missing/stale states.
- Research relation layer separated from existing Top10 recommendation layer.

## Non-goals

- No production ranking mutation, recommendation, graph promotion, login, payment, push, watchlist write, or deployment.
- No TPEx source access; no live market source access.

## Visual Route Contract

```text
visual_route: dense analytical dashboard
product_type: 台股研究/交易 dashboard
audience: 需要快速掃描資金流、freshness與coverage的研究者
primary_layout_move: 既有 shell 下的工具列 + 高密度 Theme ranking/table + single detail rail
information_density: high but breathable
type_scale: existing design tokens, compact headings/metadata
palette_strategy: neutral surfaces + semantic status/accent, no gradient
asset_strategy: real fixture/API states and browser screenshots
anti_patterns_to_avoid: marketing hero、紫藍漸層、card-in-card、recommendation語氣、過多 pills
```

## Verification facts

- API contract tests: 2 passed.
- Existing TSKG affected tests: 23 passed.
- Python command: `/Users/mattkuo/TOP10new/.venv/bin/python -m pytest tests/test_market_flow_radar.py tests/test_tskg_theme_flow.py tests/test_tskg_flow_read_model.py tests/test_tskg_mfo01.py`
- API endpoint: `GET /api/v1/market-flow/radar?as_of_date=2026-07-17`
- Response: `market-flow-radar-read-model-v1`, `ui-mfr-01-fixture-2026-07-17-v1`, TWSE available / TPEx blocked, Graph `ACCEPTED_SHADOW_ONLY`, ranking impact `NONE`.
- `git diff --check`: pass.

## Browser evidence

`NO-GO`: local API started successfully, but Playwright could not start because its Chromium executable is absent. Installing browsers/dependencies was explicitly out of scope. Therefore no desktop/mobile screenshot or runtime UI console claim is made.

Listeners were registered before the attempted navigation in the browser script; navigation did not execute because browser launch failed.

## Known limits

- `pnpm --dir web/frontend build` is blocked by missing `web/frontend/node_modules` (`tsc: command not found`); no dependency download was performed.
- Desktop/mobile layout, keyboard path, loading/empty/error/stale/partial screenshots, and browser console/network clean state remain pending a machine with existing frontend dependencies and Chromium.
