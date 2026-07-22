# REVIEW-TSKG-MFO-THEME-01

- reviewed candidate SHA: `04f1380d7390609bea854afd354f7f0859f1d3e0`
- review HEAD: `ee16ea56b0a87a595cf34c3cc326502470e7f9d5`
- review HEAD parent: `04f1380d7390609bea854afd354f7f0859f1d3e0`
- worktree preflight: clean; detached review worktree
- TPEx decision: `KEEP_BLOCKED`

## Verdict

`REVIEW_NO_GO`

## Findings

### [P1] Overlapping active membership rows silently break mass conservation

`app/tskg/theme_membership.py:80-92,124-140`

Trigger: provide two non-identical, overlapping effective-interval rows for the same `(security_id, theme_id)` and request a date inside both intervals. The closed-schema validator rejects only an exact four-field duplicate. The aggregator deduplicates the security in the theme output, but counts both rows in `by_security[security_id]`; the same `ALL_INSTITUTIONAL` flow is therefore divided by 3 for a security active in two themes plus the overlapping duplicate, and the allocated theme total is only `-113,666,666.666...` versus the source total `-69,000,000` for `security-3017-xtai` (delta `-44,666,666.666...`). This is silent under-allocation and violates `EQUAL_SPLIT_ACROSS_ACTIVE_THEMES` mass conservation; the current test only covers exact duplicate rows and does not cover overlapping intervals. Reject overlapping active `(security_id, theme_id)` rows or canonicalize them before computing the distinct active-theme denominator, and add a conservation assertion.

### [P1] Membership content hash is not canonical with respect to input order

`app/tskg/theme_membership.py:93-98`

Trigger: reverse the existing `memberships` list without changing any membership content. `ThemeMembershipSnapshot` fails closed with `content_hash does not match snapshot content`, because the hash input preserves list order. The contract explicitly requires deterministic canonical output/hash independent of input order; semantically identical snapshots can therefore not be loaded or rerun after harmless source ordering changes. Canonicalize membership rows before hashing (and keep duplicate detection) and add a reordered-input equivalence test.

## Required boundary checks

- Membership closed schema, required provenance fields, date intervals, duplicate exact keys, and content-hash mutation: covered by implementation/tests; the overlapping-interval gap above remains.
- Effective interval and stale requested date: requested dates outside the snapshot interval fail closed; exact target-date observation filtering prevents cross-date leakage.
- `ALL_INSTITUTIONAL`: aggregation selects only the explicit `ALL_INSTITUTIONAL` row, so component investor rows are not double-counted in the normal fixture.
- Buy/sell/net: positive and negative net values are split into non-negative buy/sell values and net; no additional investor rows enter the theme aggregate.
- Coverage/missing/zero/stale: zero and missing coverage are represented; stale values are counted and surfaced as `STALE`. The implementation still counts stale rows as observed coverage, which is a remaining policy risk because no acceptance test defines whether stale observations should be excluded from usable coverage.
- TWSE-only / TPEx blocked: output and snapshot require `TWSE=AVAILABLE, TPEX=BLOCKED`; no TPEx adapter or endpoint call was introduced.
- Scope isolation: no price, return, prediction, recommendation, rank, score, ranking, graph, API, or model mutation was found in the candidate diff. No Yuanta secure attachment, credential, token, or secret was found.

## Verification receipts

Commands were run with the existing project interpreter; no dependency installation, network access, cache use, or external source access occurred.

```text
<repo-root>/.venv/bin/python -m pytest tests/test_tskg_theme_flow.py tests/test_tskg_flow_read_model.py tests/test_tskg_mfo01.py
20 passed

<repo-root>/.venv/bin/python scripts/verify_tskg_theme_flow.py
{"status": "OK", "canonical_hash": "b6b8f1f053ede8aa1c90f75da22fea1758d7e9edb2d2ca6eb02833e8536c830c"}

<repo-root>/.venv/bin/python -m py_compile app/tskg/theme_membership.py scripts/build_tskg_theme_flow.py scripts/verify_tskg_theme_flow.py tests/test_tskg_theme_flow.py
PASS

git diff --check
PASS
```

Reviewer-owned synthetic probes are recorded in `.work/REVIEW-TSKG-MFO-THEME-01/probes.json`. They do not modify candidate files or tests.

## Axis verdict

- Spec/correctness: `NO_GO` — both explicit determinism and equal-split conservation boundaries fail under valid synthetic inputs.
- Boundary/privacy/scope: `GO` within the checked candidate diff; TPEx remains blocked and no prohibited downstream mutation was found.
- Overall: `REVIEW_NO_GO` until both P1 findings are repaired and independently re-reviewed.
