# REPAIR-TSKG-SLC-01 Repair Evidence

## Status and boundary

- Status: `DELIVERED_CANDIDATE`
- Base candidate: `7e8006be813be627317a1087744615dafb547a81`
- Review evidence commit: `040f3806ecdcea9e7580f2586b9850312d48862a`
- Repair-card parent: `895f4275c4c49a45db7f27cbae0330074ff85303`
- Scope: only F-01 through F-04 from `REVIEW-TSKG-SLC-01`
- Explicit exclusions: review evidence mutation, production API composition,
  dependencies, network, external services, database, and SLC-02+

## TDD evidence

Tests were added before the repair implementation and run offline with the existing
approved Python 3.11 environment:

```text
PYTHONDONTWRITEBYTECODE=1 <main-workspace>/.venv/bin/python -m unittest tests.test_tskg_slc01 -v
```

Meaningful RED result: `Ran 20 tests`; 21 malformed-schema/temporal assertions
failed and five temporal interface/duplicate-key cases errored. Representative
causes were accepted unknown fields, accepted malformed endpoints,
`create_resolver(clock=...)` not existing, and non-overlapping code reuse being
rejected. The review evidence independently preserves the compound-key scanner
false negative; that review artifact was not edited.

GREEN result after implementation:

```text
Ran 22 tests in 0.616s
OK
```

The original 13 public behavior tests remain present and pass. Nine repair test
methods add 27 closed-schema mutation subcases, seven malformed temporal shapes,
expired/future/current/historical/boundary/unknown/reuse cases, explicit API
`as_of`, and six nested compound prohibited-key variants.

## F-01 temporal and reuse mapping

- v1.1 `KNOWN`, `UNKNOWN`, and `UNBOUNDED` endpoint shapes are validated with
  closed fields, UTC RFC 3339 timestamps, boolean inclusion, and non-empty interval
  rules.
- Resolver selection evaluates an explicit effective instant or an injected UTC
  clock. Known expired and future records return `NOT_FOUND`; the reviewer-style
  expired `3017` probe no longer resolves.
- `UNKNOWN` is retained as possibly valid rather than classified expired.
- Same `(market, code)` records are rejected only when their intervals are
  provably overlapping. Non-overlapping reuse is accepted; exact inclusive and
  exclusive boundary behavior is covered.
- Multiple temporally possible records return sorted `AMBIGUOUS` candidates; input
  order is not used as a tie-breaker.
- Standalone `/v1/company/{stock_id}` supports optional `as_of`; current lookup
  uses the service's injectable clock. Invalid `as_of` maps to the existing 400
  `INVALID_ARGUMENT` envelope.

## F-02 schema mapping

- Fixture, provenance, identity evidence, Organization, Security, and alias records
  use exact closed shapes.
- Required non-empty strings, controlled entity/security/organization/status enums,
  uppercase market syntax, string code syntax, and v1 version values fail loud.
- Issuer, source, and evidence references are checked.
- Duplicate entity IDs, evidence records, and alias records are rejected.
- The malformed matrix passes all 27 mutation subcases.

## F-03 prohibited-key mapping

- Recursive scanning still traverses nested dict/list values.
- Each key is split into semantic tokens across snake_case, camelCase, and
  kebab-case boundaries before comparing prohibited terms.
- Nested `prediction_score`, `target_price`, `buy_signal`, and `stop_loss` negative
  cases pass, together with camel/kebab variants.
- The actual candidate company response still passes the same scanner.

## F-04 portability mapping

- Shared SLC-01 evidence now records only
  `<main-workspace>/.venv/bin/python`.
- Scoped host-specific absolute-path scan across the changed SLC-01/Repair shared
  documents returns no matches.

## Verification

```text
PYTHONPYCACHEPREFIX=<temporary-path> <main-workspace>/.venv/bin/python -m py_compile app/tskg/*.py tests/test_tskg_slc01.py
```

Result: PASS (exit 0, no output).

Final verification also requires and records at delivery:

- `git diff --check`: PASS.
- changed-file allowlist: only `app/tskg/**`, SLC-01 tests/evidence, this repair
  card, and this repair evidence.
- review evidence diff: empty.
- post-commit worktree/index: clean.

## Remaining risk and blockers

- Blockers: none within F-01 through F-04.
- The original `uv --with-requirements` Python 3.14/lxml caveat remains pre-existing
  and unchanged; this repair used the explicitly supplied existing Python 3.11
  interpreter offline.
- No production API, real data, relationship claim, external service, database,
  or SLC-02+ behavior is claimed or tested.
