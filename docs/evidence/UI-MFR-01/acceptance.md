# UI-MFR-01 Acceptance

Status: `ACCEPTED`

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

## Independent review result

- Fixed candidate: `88d6125f82193d35328a4d34352020a4e21b839f`.
- Final review evidence: `8b324275ba5a1544486c6d11b1a387d85a75c872`.
- Verdict: `GO`; P1/P2 findings: 0; Repair 2/2 complete; Repair 3 prohibited and unnecessary.
- Fresh gates: 32 affected tests, 51/51 date boundary matrix, strict nested schema/runtime checks, CORS/versioned 422, POST 405/read-only, determinism/non-mutation, Python compilation and frontend build all passed.
- Browser: desktop/mobile/keyboard/live/five-state acceptance passed; radar network clean. The weekly `features.parquet` 500 is an independent pre-existing baseline and is separated from the radar route.

## Known limits

- TPEx venue coverage remains blocked by the accepted source decision.
- Theme/Graph inputs remain research/shadow-only and have no ranking impact.
- The existing weekly route still needs its local `data/clean/features.parquet`; this is not a radar regression.

## Mainline acceptance rerun

- 32 affected Python tests: PASS.
- Python compilation: PASS.
- Frontend production build: PASS.
- `git diff --check`: PASS.
- Browser evidence is the independent final re-review evidence for the identical fixed-candidate tree.
- Accepted mainline commit: `e3b00e0`.
