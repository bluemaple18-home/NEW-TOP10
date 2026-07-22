# REVIEW-TSKG-MFO-THEME-01 Repair 1 Re-review

- verdict: `REVIEW_GO`
- reviewed candidate SHA: `71c02aa8a4f9106364e97da97ffefb887db0833e`
- candidate branch: `codex/tskg-mfo-theme-01-repair-1`
- candidate parent / Repair card: `1c719ffe61041c38ffc6c61b1ab74ad2983705e9`
- original NO_GO commit: `69282b53763b61c7f44e6685ec25ac6845b7d524`
- original candidate: `04f1380d7390609bea854afd354f7f0859f1d3e0`
- worktree: clean before review and candidate checkout confirmed

## Finding closure

1. **Overlapping active membership / mass conservation — CLOSED.**
   `ThemeMembershipSnapshot` rejects any overlapping inclusive effective interval
   for the same `(security_id, theme_id)`. The original overlap probe now fails
   closed with `overlapping membership interval`; the normal fixture allocates
   source net `-69,000,000` exactly to theme output total `-69,000,000`.
2. **Input-order canonical hash — CLOSED.**
   Membership rows are sorted by semantic key before hash validation/storage.
   Reversing the fixture rows produces an equivalent snapshot and identical
   aggregate output/canonical hash.

## Boundary and scope review

- `ALL_INSTITUTIONAL` remains the sole selected investor row; component investor
  rows are not aggregated into the Theme flow.
- TWSE-only coverage remains explicit and TPEx remains `BLOCKED`.
- Exact duplicate membership, stale/missing/zero/cross-date behavior remains
  covered by the inherited tests; stale policy was intentionally not changed by
  this repair and remains a documented residual policy decision.
- No price, return, prediction, recommendation, ranking, score, graph, API/UI,
  model, TPEx adapter, Yuanta secure payload, credential, token, or secret
  mutation was introduced.
- Candidate diff from the Repair card parent contains only the declared repair
  allowlist paths.

## Verification receipts

```text
<repo-root>/.venv/bin/python -m pytest tests/test_tskg_theme_flow.py tests/test_tskg_flow_read_model.py tests/test_tskg_mfo01.py
23 passed

<repo-root>/.venv/bin/python scripts/verify_tskg_theme_flow.py
{"status": "OK", "canonical_hash": "b6b8f1f053ede8aa1c90f75da22fea1758d7e9edb2d2ca6eb02833e8536c830c"}

<repo-root>/.venv/bin/python -m py_compile app/tskg/theme_membership.py scripts/build_tskg_theme_flow.py scripts/verify_tskg_theme_flow.py tests/test_tskg_theme_flow.py
PASS

git diff --check 1c719ffe61041c38ffc6c61b1ab74ad2983705e9 HEAD
PASS
```

Reviewer-owned probe results: reordered snapshot equivalent; overlapping
interval rejected; source-net mass conserved; TPEx blocked. No network,
dependency installation, cache use, external endpoint, or secure attachment
access occurred.

## Axis verdict

- Spec/correctness: `GO`; both original P1 findings are closed.
- Standards/boundary: `GO`; allowlist, privacy, and downstream isolation pass.
- Overall: `REVIEW_GO` for reviewed SHA `71c02aa8a4f9106364e97da97ffefb887db0833e`.
