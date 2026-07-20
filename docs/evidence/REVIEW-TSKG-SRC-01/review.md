# REVIEW-TSKG-SRC-01 Review Evidence

## Verdict and lineage

- Initial verdict: `REVIEW_NO_GO`
- Base: `4f0470e133b763d5d5c5a232acddf3ab2bc94de8`
- Original reviewed candidate: `bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`
- Review-card instruction commit: `b21c16b73070baca32b2d37cd36581ba1fc767d6`
- Initial review commit: `31715802f794f411986abdebb6f368ce31b35834`
- Repair parent: `717e1c6dffedf254661a12ab41b1092bfae948d9`
- Re-review round: `1`
- Reviewed successor: `2d81414185446e83a34df28c37f54989515d7f76`
- Re-review verdict: `REVIEW_GO`
- Re-review Spec axis: `GO`
- Re-review Standards axis: `GO`

The reviewer read the complete six-file candidate diff, the implementation card,
TSKG v1.1, AGENTS.md, and the review card. The reviewer did not modify candidate
code, fixtures, tests, implementation evidence, dependencies, or production
runtime. No network, browser, external service, install, merge, push, or worktree
cleanup was performed.

## Findings

### F-01 — Public approval can be manufactured through the public mapping API

- severity: `P1`
- category: `security / correctness`
- path: `app/tskg/source_policy.py:310`
- evidence: `SourcePolicyRegistry.from_mapping` accepts a mutation of the committed
  synthetic approved policy where only `source_class`, `source_id`, and `policy_id`
  are changed to a new `PUBLIC` policy. The resulting summary reports
  `approved_public_count=1`; `preflight_source` returns `ok=true` and calls the
  reader once. No source/compliance-owner artifact or explicit post-OQ approval
  boundary is required. This contradicts the current OQ-SRC-01/SLC-02 blocker
  preserved by the card, fixture, and implementation evidence.
- risk: A caller can convert the offline synthetic gate into a public-source
  approval using arbitrary in-memory strings. This is the review card's explicit
  public-source false-approval condition and can invoke a reader before the
  unresolved governance decision exists.
- suggested_fix: While OQ-SRC-01 remains unresolved, reject
  `source_class=PUBLIC` with `decision_status=APPROVED` in the current registry
  contract. A later source-approval card should introduce a distinct, explicit
  owner-approved immutable decision artifact/constructor and negative tests that
  prove fixture mutation and the generic mapping path cannot grant approval.
- validation_gap: No real source adapter exists in this candidate, and external
  access was forbidden; the proof stops at the observable reader invocation.
- confidence: `high`

### F-02 — Duplicate JSON members are silently collapsed before closed-schema validation

- severity: `P1`
- category: `security / correctness`
- path: `app/tskg/source_policy.py:92`
- evidence: `from_file` uses default `json.load`, whose last-wins object parsing
  removes duplicate member evidence before `_require_closed_shape` runs. A copy
  of the fixture containing both `"source_class":"SYNTHETIC"` and a later
  `"source_class":"PUBLIC"` is accepted; the effective policy is `PUBLIC`,
  remains `APPROVED`, the registry reports one approved public source, and the
  matching preflight returns `ok=true` with reader invocation `1`.
- risk: Human review, checksum evidence, and runtime can disagree about which
  governance decision is authoritative. A duplicate `decision_status`,
  `source_class`, method/path, or evidence member can produce a public false
  approval while the canonical checksum hides the ambiguity.
- suggested_fix: Parse policy JSON with a recursive duplicate-member rejecting
  `object_pairs_hook` before constructing any mapping. Add public-interface tests
  for duplicate members at both registry and policy levels, including conflicting
  approval and source-class values.
- validation_gap: `from_mapping` receives an already-collapsed mapping and cannot
  recover duplicate-key provenance; raw JSON must pass through the strict loader.
- confidence: `high`

### F-03 — Unicode compatibility characters bypass the traversal gate

- severity: `P1`
- category: `security`
- path: `app/tskg/source_policy.py:390`
- evidence: The request path
  `/synthetic/v1/records/．．／secret` passes `_is_safe_request_path`, matches the
  approved wildcard, returns `ok=true`, and invokes the reader once. Unicode NFKC
  normalizes that exact string to `/synthetic/v1/records/../secret`.
- risk: A downstream URL/client/server normalization step can reinterpret an
  approved-looking path as traversal after the gate has already permitted the
  read. This is a path-allowlist fail-open at the security boundary.
- suggested_fix: Define one canonical path representation before matching and use
  the same representation for the validated request/receipt/reader boundary.
  Conservatively reject control characters, non-ASCII compatibility separators,
  and any path changed by NFKC (or use an equally strict documented grammar), then
  add fullwidth-dot/fullwidth-slash regression tests.
- validation_gap: The candidate intentionally has no HTTP adapter, so downstream
  normalization was not executed; the accepted path and its NFKC traversal form
  are independently reproducible.
- confidence: `high`

## Mandatory probe results

| # | Probe | Result | Evidence |
|---:|---|---|---|
| 1 | `PUBLIC + APPROVED` fixture mutation/custom registry | **FAIL** | F-01: accepted, reader `1` |
| 2 | decision state, review/expiry, timezone, naive/equality | PASS | 9/9 focused cases; review equality allowed, expiry equality blocked, naive/non-UTC rejected |
| 3 | closed/duplicate/type/numeric edge cases | **FAIL** | 12/12 mapping cases pass, but raw duplicate JSON member is accepted (F-02) |
| 4 | traversal/prefix/encoding/Unicode/backslash/absolute URL | **FAIL** | 8/9 matrix cases block; fullwidth traversal calls reader (F-03) |
| 5 | method/media case, parameters, wildcard, empty/duplicate | PASS | 8/8 focused cases fail closed conservatively |
| 6 | robots versus terms/legal basis | PASS | 3/3 cases return `GOVERNANCE_INCOMPLETE`, reader `0` |
| 7 | blocked/expired/unknown/invalid and reader exception | PASS | 7/7 cases; denied paths reader `0`; reader exception propagates after one approved invocation and no success receipt is returned |
| 8 | checksum canonicalization and receipt binding | **FAIL** | all 27 policy fields affect checksum, order is ignored, receipt binding passes; duplicate JSON ambiguity is hidden before checksum (F-02) |
| 9 | committed fixture isolation/content | PASS | approved public count `0`; only synthetic approved; no URL/source bytes/claim/relationship/trading/model payload |
| 10 | exports and production/dependency isolation | PASS | export test passes; `app/api/main.py` diff empty; dependency/lockfile allowlist scan empty |
| 11 | RED/GREEN/regression/compile/diff/scan evidence | PASS | RED reproduced; 14 SRC + 22 SLC tests pass; compile/diff/allowlist/prohibited/host-path scans pass |
| 12 | OQ-SRC-01 and SLC-02 blocker consistency | **FAIL** | card/fixture/evidence retain blocker, but executable mapping path can grant public approval (F-01) |

The extended in-memory matrix ran 51 cases: 50 met the expected conservative
behavior and one failed (`unicode_fullwidth_traversal`, `ok=true`, reader `1`).
Separate exploit probes reproduced the custom public approval and duplicate-JSON
acceptance. These probes used only in-memory payloads or temporary files outside
the candidate tree.

## Verification

Shared command forms below use placeholders; the dispatch-provided existing
main-workspace interpreter was used without installing dependencies.

```text
PYTHONPYCACHEPREFIX=<temporary-path> <main-workspace>/.venv/bin/python \
  -m unittest tests.test_tskg_src01 tests.test_tskg_slc01 -v
```

Result: `Ran 36 tests in 1.876s` / `OK` (`14` SRC + `22` SLC).

```text
PYTHONPYCACHEPREFIX=<temporary-path> <main-workspace>/.venv/bin/python \
  -m py_compile app/tskg/source_policy.py tests/test_tskg_src01.py
```

Result: PASS, exit `0`, no output.

RED was independently reconstructed in a temporary tree from base `app/` plus
candidate test/fixture artifacts:

```text
<main-workspace>/.venv/bin/python -m unittest tests.test_tskg_src01 -v
```

Result: expected exit `1`, `ModuleNotFoundError: app.tskg.source_policy`,
`Ran 1 test`, reader invocation unavailable/`0`.

```text
git diff --check 4f0470e133b763d5d5c5a232acddf3ab2bc94de8 \
  bcbf773f8dbee51e84488b1ea3c11fabbad7a28a
```

Result: PASS, exit `0`, no output.

Candidate changed-file allowlist contains exactly:

```text
app/tskg/__init__.py
app/tskg/source_policy.py
data/fixtures/tskg/source_policy_v1.json
docs/evidence/TSKG-SRC-01/verification.md
docs/tasks/2026-07-18_TSKG-SRC-01_source_gate.md
tests/test_tskg_src01.py
```

Additional results:

- candidate parent equals the fixed base and the candidate commit is its direct child;
- the review-card commit changes only the Review card relative to the candidate;
- prohibited runtime/client/source-byte/trading/model scan: no matches;
- dependency/lockfile/`app/api/main.py` changed-path scan: no matches;
- host-specific absolute-path scan over the candidate diff: no matches;
- candidate worktree was clean before review-artifact writes;
- registry checksum independently reproduced as
  `0ea9bfca08d343f796aa093d162d4c9153b6a7fd8c94064d870a9d89b8a07b4d`.

## Axis verdicts and remaining risks

- Spec axis: `NO_GO`. AC-10's intended fail-closed source boundary is undermined
  by F-01 and F-03; F-02 also violates the review card's duplicate-field contract.
- Standards axis: `NO_GO`. The security boundary accepts an unapproved public
  policy and a normalization-confusable traversal, while the JSON loader hides
  ambiguous governance input.
- Remaining risks outside this candidate: OQ-SRC-01 remains unresolved; no public
  source is approved; SLC-02 remains blocked; reader-to-request binding and real
  adapter normalization still require a later integration review.

## Initial review result（historical）

`REVIEW_NO_GO`

Unresolved findings: `F-01`, `F-02`, `F-03` (all `P1`).

## Re-review Round 1

The same reviewer read the complete six-file parent-to-successor diff and the
complete Repair card/evidence, then independently reran the original finding
probes. Review scope remained limited to F-01, F-02, F-03 and the existing Spec
and Standards axes. No candidate/runtime/fixture/repair artifact was modified.

未發現新的阻塞問題。原 F-01、F-02、F-03 均已無法重現。

### Finding dispositions

#### F-01 — RESOLVED

- severity: `P1 (historical)`
- category: `security / correctness`
- path: `app/tskg/source_policy.py:331`
- evidence: `_validate_policy` now rejects every `PUBLIC + APPROVED` combination
  while OQ-SRC-01 remains unresolved. The original custom-mapping mutation raises
  `SourcePolicyContractError`; registry construction fails before a reader exists.
  The committed public-behavior regression is at `tests/test_tskg_src01.py:187`.
- risk: The original generic public false-approval path no longer reaches
  preflight or a callback.
- suggested_fix: None for this finding. A future public approval must remain a
  separate owner-approved immutable artifact/constructor card.
- validation_gap: No real public adapter exists and no external access was run.
- confidence: `high`
- status: `RESOLVED`

#### F-02 — RESOLVED

- severity: `P1 (historical)`
- category: `security / correctness`
- path: `app/tskg/source_policy.py:90`
- evidence: `from_file` uses recursive `object_pairs_hook` rejection implemented
  at `app/tskg/source_policy.py:440`. Independent raw-JSON probes for top-level
  and nested/policy duplicates both raise `SourcePolicyContractError`; the
  committed three-level regression is at `tests/test_tskg_src01.py:202`.
  `from_mapping` explicitly documents that already-collapsed raw duplicate
  provenance cannot be reconstructed.
- risk: Raw policy JSON can no longer hide conflicting governance members behind
  last-wins parsing before checksum/validation.
- suggested_fix: None for this finding. Keep raw JSON on the strict `from_file`
  path and retain recursive duplicate tests.
- validation_gap: Callers that independently parse ambiguous JSON into a mapping
  have already discarded evidence; that boundary is documented and cannot be
  repaired by a mapping constructor.
- confidence: `high`
- status: `RESOLVED`

#### F-03 — RESOLVED

- severity: `P1 (historical)`
- category: `security`
- path: `app/tskg/source_policy.py:406`
- evidence: `_canonical_request_path` rejects NFKC-changing input, Unicode control
  categories, percent/backslash/query/fragment/double-slash and empty/dot segments.
  Matching and receipt use the returned canonical path, and the callback receives
  that same path at `app/tskg/source_policy.py:298-310`. The original fullwidth
  traversal now returns `INVALID_REQUEST` with reader `0`; the committed matrix is
  at `tests/test_tskg_src01.py:371`.
- risk: The original compatibility-character traversal no longer crosses the
  allowlist or reader boundary.
- suggested_fix: None for this finding. Future adapters must derive their request
  target only from the supplied canonical path.
- validation_gap: The injected callback remains trusted code and can ignore its
  argument; a future external adapter needs its own integration review.
- confidence: `high`
- status: `RESOLVED`

### Reader callback contract

- Successor signature: `Callable[[str], Any]`; the accepted callback receives the
  canonical path exactly once, and the independently observed callback path equals
  the receipt path byte-for-byte.
- A legacy zero-argument callback raises `TypeError`. This is an intentional seam
  migration required by F-03, not an accepted-runtime regression: the original
  candidate was rejected and never integrated, and repo search finds no consumer
  outside this test module/export.
- The callback is still injected trusted code. It could ignore the argument or
  close over another target; this successor does not claim to secure a future
  network adapter. That later adapter must consume only the supplied canonical
  path and remain behind a separate review.

### Re-review verification

```text
PYTHONPYCACHEPREFIX=<temporary-path> <main-workspace>/.venv/bin/python \
  -m unittest tests.test_tskg_src01 tests.test_tskg_slc01 -v
```

Result: `Ran 39 tests in 1.565s` / `OK` (`17` SRC + `22` SLC).

```text
PYTHONPYCACHEPREFIX=<temporary-path> <main-workspace>/.venv/bin/python \
  -m py_compile app/tskg/source_policy.py tests/test_tskg_src01.py
```

Result: PASS, exit `0`, no output.

Independent original-review matrix:

```text
P2 9/9; P3 12/12; P4 9/9; P5 8/8; P6 3/3; P7 7/7; P8 3/3
TOTAL 51/51
F-01 public approval: BLOCKED
F-02 top-level duplicate: BLOCKED
F-02 nested/policy duplicate: BLOCKED
10 denied requests: reader calls 0
canonical callback path == receipt path: true
```

Verification gates:

- successor direct parent equals `717e1c6dffedf254661a12ab41b1092bfae948d9`;
- parent-to-successor allowlist contains exactly the six Repair-card paths;
- `git diff --check` PASS;
- Review card/evidence diff across the Repair commit is empty;
- dependency/lockfile/`app/api/main.py` and SLC-01 runtime diffs are empty;
- runtime/client/prohibited/host-path/debug scans have no matches;
- the test file contains one deliberate `https://example.invalid` negative input,
  but no network client or I/O path exists;
- worktree was clean before Review-artifact writes.

### Re-review axis verdicts and remaining risks

- Spec axis: `GO`. F-01/F-02/F-03 now satisfy the Repair contract and preserve
  AC-10's fail-closed boundary for the current synthetic-only stage.
- Standards axis: `GO`. Strict raw parsing, conservative path validation, callback
  path binding, regression coverage, and isolation gates are reproducible.
- Remaining risks: OQ-SRC-01 is unresolved; no public source is approved; SLC-02
  remains blocked; legacy zero-argument callbacks must migrate; future external
  adapters require a separate request-binding/integration review.

## Re-review Round 1 final result

`REVIEW_GO`

- Resolved: `F-01`, `F-02`, `F-03`.
- Unresolved findings: none.
