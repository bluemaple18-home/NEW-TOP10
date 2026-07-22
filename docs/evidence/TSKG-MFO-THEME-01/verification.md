# TSKG-MFO-THEME-01 Verification

- candidate base: "b79fed679df53d498945b352e69e611a27679513"
- TPEx source decision: "KEEP_BLOCKED"
- membership fixture: "data/fixtures/tskg/theme_membership_v1.json"
- membership version: "theme-membership-fixture-2026-07-17-v1"
- membership content hash: "9cbce741c7ad811dbfa07b9f9d3781a0026744af245d5183b9d72d79265dd3f5"
- evidence locator: "fixture://tskg/theme-membership-v1"
- venue coverage: "TWSE=AVAILABLE, TPEX=BLOCKED"
- allocation policy: "EQUAL_SPLIT_ACROSS_ACTIVE_THEMES"

## Commands

    <repo-root>/.venv/bin/python -m pytest tests/test_tskg_theme_flow.py tests/test_tskg_flow_read_model.py tests/test_tskg_mfo01.py
    20 passed
    <repo-root>/.venv/bin/python scripts/verify_tskg_theme_flow.py
    {"status": "OK", "canonical_hash": "b6b8f1f053ede8aa1c90f75da22fea1758d7e9edb2d2ca6eb02833e8536c830c"}
    <repo-root>/.venv/bin/python -m py_compile app/tskg/theme_membership.py scripts/build_tskg_theme_flow.py scripts/verify_tskg_theme_flow.py tests/test_tskg_theme_flow.py
    git diff --check

## Acceptance cases

- stale snapshot: requested date outside effective interval fails closed.
- missing membership evidence: content hash mutation fails closed.
- duplicate membership: duplicate key fails closed.
- zero coverage: deterministic "ZERO_COVERAGE", zero-filled metrics are not treated as observed.
- cross-date: target date selects exact observations; other dates do not leak.
- deterministic rerun: identical canonical hash and output on repeated aggregation.
- raw observation, Theme read model, and graph truth remain separate; no graph fields are emitted.
