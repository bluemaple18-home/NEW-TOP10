# REVIEW-TSKG-SLC-01 Review Evidence

## Review lineage

- Initial verdict: `REVIEW_NO_GO`
- Original candidate: `7e8006be813be627317a1087744615dafb547a81`
- Initial review commit: `040f3806ecdcea9e7580f2586b9850312d48862a`
- Repair-card commit: `895f4275c4c49a45db7f27cbae0330074ff85303`
- Re-review round: `1`
- Reviewed successor: `fbd8fa09ce570971b2ecbf6b18a92c47c42a8f5b`
- Successor parent: `895f4275c4c49a45db7f27cbae0330074ff85303`
- Re-review verdict: `REVIEW_GO`

The immutable initial review details remain available at the initial review commit.
This successor artifact records the same F-01 through F-04 identities and their
Round 1 dispositions. The reviewer did not modify candidate/runtime files.

## Initial findings summary（historical）

| Finding | Initial severity | Initial category | Initial defect |
|---|---:|---|---|
| F-01 | P1 | correctness | Security resolution ignored `valid_time` and rejected all same-key reuse regardless of non-overlap. |
| F-02 | P2 | correctness | Fixture validation accepted schema drift, invalid market/code/type, missing evidence, and duplicate alias records. |
| F-03 | P2 | testing | Recursive prohibited-field scan missed compound semantic keys such as `prediction_score`. |
| F-04 | P3 | maintainability | Shared verification evidence retained a host-specific interpreter path. |

## Re-review Round 1

### Axis verdicts

- Spec axis: `GO`。F-01 temporal identity/selection/reuse contract is implemented
  and independently reproduced; no new P0/P1 correctness defect was found.
- Standards axis: `GO`。F-02/F-03/F-04 are repaired with closed-schema negative
  coverage, semantic compound-key coverage, and portable shared paths.

未發現阻塞問題，也未發現新的 P2/P3 finding。原
`uv --with-requirements` Python 3.14/lxml caveat remains a pre-existing environment
constraint; this review does not report that command as passing.

## Finding dispositions

### F-01 — RESOLVED

- severity: `P1 (historical)`
- category: `correctness`
- path: `app/tskg/identity.py`
- line: `79-99, 119-186`
- evidence: `resolve_security` now selects by code, optional market, and an explicit
  or injected UTC effective instant. The v1.1 KNOWN/UNKNOWN/UNBOUNDED endpoint
  shapes and inclusive boundaries are validated. Repository uniqueness rejects
  only provably overlapping same-key intervals (`app/tskg/repository.py:234-244`).
  The original reviewer probe with a Security ending in 2011 now returns
  `NOT_FOUND`; non-overlapping reuse resolves the correct historical/current ID,
  overlap is rejected, and uncertain multiple candidates remain sorted ambiguous.
- risk: The original wrong-current-issuer and code-reuse risks are no longer
  reproducible under the accepted SLC-01 temporal contract.
- suggested_fix: None for this finding; retain the temporal boundary, UNKNOWN,
  overlap, reuse, explicit `as_of`, and injected-clock tests as regression gates.
- validation_gap: Production persistence/system-time behavior remains outside
  SLC-01 and is not claimed by this repair.
- confidence: `high`
- status: `RESOLVED`

### F-02 — RESOLVED

- severity: `P2 (historical)`
- category: `correctness`
- path: `app/tskg/repository.py`
- line: `139-191, 193-283`
- evidence: Top-level, provenance, identity evidence, Organization, Security, and
  alias records now have exact closed shapes, controlled values, syntax checks,
  source/evidence references, and duplicate detection. The original malformed
  matrix cases (`market=None`, lowercase market, empty code, invalid security type,
  malformed interval, missing alias evidence, duplicate alias) all fail loud with
  `FixtureContractError`. The candidate suite covers 27 schema mutations and seven
  malformed temporal shapes.
- risk: The original silent fixture drift and invalid provenance risks are no
  longer reproducible within the synthetic fixture boundary.
- suggested_fix: None for this finding; preserve the table-driven negative fixture
  suite whenever the fixture schema changes.
- validation_gap: JSON duplicate object-key detection before `json.load` is not
  part of the accepted repair scope; array-record identity duplicates are covered.
- confidence: `high`
- status: `RESOLVED`

### F-03 — RESOLVED

- severity: `P2 (historical)`
- category: `testing`
- path: `tests/test_tskg_slc01.py`
- line: `58-82, 600-618`
- evidence: The scanner recursively collects nested keys, tokenizes snake_case,
  camelCase, and kebab-case boundaries, and compares semantic tokens against the
  prohibited set. Independent probes confirm detection of `prediction_score`,
  `target_price`, `buy_signal`, `stop_loss`, `targetPrice`, and `buy-signal`; the
  actual company response remains clean.
- risk: The original false-positive acceptance of compound model/trading keys is
  no longer reproducible for the required naming forms.
- suggested_fix: None for this finding; keep both compound-key negative fixtures
  and the actual-response positive scan.
- validation_gap: None within the F-03 repair contract.
- confidence: `high`
- status: `RESOLVED`

### F-04 — RESOLVED

- severity: `P3 (historical)`
- category: `maintainability`
- path: `docs/evidence/TSKG-SLC-01/verification.md`
- line: `57-63`
- evidence: Shared verification commands now use
  `<main-workspace>/.venv/bin/python`. A scoped host-specific absolute-path scan
  across the changed SLC-01/Repair shared documents returned no matches.
- risk: The original cross-machine path binding risk has been removed from the
  committed successor documents.
- suggested_fix: None for this finding; keep host-local resolution in ephemeral
  diagnostics and placeholders in shared artifacts.
- validation_gap: None within the F-04 repair contract.
- confidence: `high`
- status: `RESOLVED`

## Successor diff and allowlist

The parent-to-successor range contains exactly eight paths:

```text
app/tskg/identity.py
app/tskg/repository.py
app/tskg/router.py
app/tskg/service.py
docs/evidence/REPAIR-TSKG-SLC-01/repair.md
docs/evidence/TSKG-SLC-01/verification.md
docs/tasks/2026-07-18_REPAIR-TSKG-SLC-01.md
tests/test_tskg_slc01.py
```

This matches the Repair scope. `app/api/main.py`, `requirements.txt`, the JSON
fixture, and the original review artifacts were not modified by the successor.
The Repair card changed only its acceptance wording plus status/Result.

## Re-review verification

Shared command form; the dispatch supplied the host-local interpreter resolution:

```text
PYTHONDONTWRITEBYTECODE=1 <main-workspace>/.venv/bin/python -m unittest tests.test_tskg_slc01 -v
```

Result: `Ran 22 tests in 0.726s` / `OK`.

The 22 tests include the original 13 public behavior tests and all focused
temporal/schema/compound-key repair cases.

```text
PYTHONPYCACHEPREFIX=<temporary-path> <main-workspace>/.venv/bin/python -m py_compile app/tskg/*.py tests/test_tskg_slc01.py
```

Result: PASS (exit 0, no output).

```text
git diff --check 895f4275c4c49a45db7f27cbae0330074ff85303 fbd8fa09ce570971b2ecbf6b18a92c47c42a8f5b
git diff --check 7e8006be813be627317a1087744615dafb547a81 fbd8fa09ce570971b2ecbf6b18a92c47c42a8f5b
```

Result: both PASS (exit 0, no output).

Additional independent probes:

- seven malformed fixture cases rejected with `FixtureContractError`;
- expired Security returned `NOT_FOUND`;
- all six required compound prohibited-key variants were detected;
- host-specific absolute-path scan returned no matches;
- candidate worktree was clean before review-artifact writes.

No dependency installation, network, browser, external service, database,
production API composition, or candidate/runtime mutation was performed.

## Re-review Round 1 verdict

`GO`

- Resolved: F-01, F-02, F-03, F-04.
- Unresolved findings: none.
- Remaining caveat: original `uv --with-requirements` environment resolution is
  still not a recorded pass; direct existing Python 3.11 verification passed under
  the explicit local-only/no-install review instruction.
