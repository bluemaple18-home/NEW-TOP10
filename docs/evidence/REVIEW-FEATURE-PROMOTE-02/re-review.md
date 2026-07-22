# REVIEW-FEATURE-PROMOTE-02 Re-review

## Verdict

NO_GO

Fixed candidate:
0079370cf4e6d46fe718579de4a78fb3c5c3ac73

Repair parent:
1499b0eaeebc9ca997feee627fa0dc85df35a21f

Original NO_GO evidence:
86ec0e2

## Closed findings

The original two P1 verifier findings are closed:

- Fixed base/candidate SHA binding rejects wrong identity.
- Closed top-level/row/file schema rejects duplicate, unknown, missing and
  wrong types.
- Evidence kind, GO/PASS verdict, data/candidate/base identity,
  universe/date/cost identity, freshness, source hash, pattern and manifest
  tampering are rejected.
- Absolute, traversal, out-of-repo and symlink paths are rejected.
- Original adversarial_probes.py returned all_pass: true.

## New finding

- [P1] Builder accepts future freshness as promotion evidence -
  scripts/build_feature_promotion_decision.py:69-96.
  Reviewer-owned fresh probe changed a valid evidence document's
  freshness.as_of to 2999-01-01; build_payload() returned GO.
  The verifier rejects the same document, but the builder itself violates the
  repair contract that builder/verifier must fail closed. Add the same
  freshness date, future-date, age, and date-range validation to
  is_versioned_evidence().

## Spec axis

NO_GO: the repaired verifier satisfies the original bypass requirements,
but the builder can still emit GO from invalid freshness evidence.

## Standards axis

NO_GO: the new P1 is a correctness and promotion-integrity failure.
The reviewed repair diff contains no RankingPolicy, weight, production
runtime, daily path, deploy, or privacy mutation.

## Verification

- Original reviewer probe: all cases passed (all_pass: true).
- Fresh probes: all verifier schema, identity, semantic, freshness, path,
  pattern, source-hash, decision, missing-list, and manifest cases passed.
- Synthetic complete GO positive control: accepted only in a temporary root.
- Actual repository: NO_GO, 12 missing rows, Graph RISK, TPEx
  KEEP_BLOCKED, verifier OK.
- Affected tests: 23 passed; repair evidence records 4 subtests passed.
- Builder/verifier/help commands: passed.
- py_compile and git diff --check: passed.
- Allowlist/privacy/non-mutation: only this re-review evidence and fresh probe
  were added; candidate and repair evidence were not modified.

Detailed fresh probe implementation is in re-review-fresh-probes.py.
