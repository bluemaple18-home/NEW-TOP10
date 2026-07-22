# REPAIR-TSKG-MFO-THEME-01-01 Repair Evidence

## Status and boundary

- Status: `DELIVERED_CANDIDATE`
- Base: `1c719ffe61041c38ffc6c61b1ab74ad2983705e9`
- Scope: only the two P1 findings in `REVIEW-TSKG-MFO-THEME-01`.
- Exclusions: stale policy, graph/ranking/API/UI, TPEx, and Yuanta secure data.

## Repair

- Membership rows are canonicalized by security, theme, and effective interval
  before content hashing and storage, so reversed/permuted input is equivalent.
- Exact duplicate rows remain rejected. Any overlapping interval for the same
  `(security_id, theme_id)` is rejected during snapshot validation, preventing a
  duplicate active membership from entering the equal-split denominator.
- Public regressions cover reordered-input equivalence, overlap fail-closed, and
  aggregate source-net mass conservation.

## Verification receipts

```text
<repo-root>/.venv/bin/python -m pytest tests/test_tskg_theme_flow.py tests/test_tskg_flow_read_model.py tests/test_tskg_mfo01.py
23 passed

<repo-root>/.venv/bin/python scripts/verify_tskg_theme_flow.py
{"status": "OK", "canonical_hash": "b6b8f1f053ede8aa1c90f75da22fea1758d7e9edb2d2ca6eb02833e8536c830c"}

<repo-root>/.venv/bin/python -m py_compile app/tskg/theme_membership.py scripts/verify_tskg_theme_flow.py tests/test_tskg_theme_flow.py
PASS

git diff --check
PASS
```

All checks ran offline with `<repo-root>/.venv/bin/python` supplied by the task;
no dependency installation, network access, cache use, or external source access
was performed. The changed-file allowlist and privacy scan passed; no prohibited
downstream or Yuanta content was added.
