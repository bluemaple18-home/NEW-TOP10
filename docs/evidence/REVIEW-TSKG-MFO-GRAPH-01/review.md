# REVIEW-TSKG-MFO-GRAPH-01

## Scope and integrity

- `HEAD=67fab5f`; `HEAD^=1c6a760a0d655f370e9056131d9fcba53851b97b`.
- Reviewed range: `4dece38211968ee3d4f68937d2968940520ce145..1c6a760a0d655f370e9056131d9fcba53851b97b`.
- Review worktree was clean before evidence additions.
- No candidate, RankingPolicy, `risk_adjusted_score`, production feature contract, or daily production path was modified/imported by the reviewed change.
- No secure attachment was accessed. Diff scan found no secret or local absolute path.

## Findings

- [P1] Numeric contract is not fail-closed for non-finite edge weights - `app/tskg/graph_diffusion.py:125`
  Trigger: set an edge `weight` to `NaN` or `+Infinity` (or use an overflow-prone value such as `1e308`). `GraphDiffusionSnapshot` accepts all three because only `weight <= 0` is checked. The later diffusion/hash path can emit non-finite values or fail with a generic JSON `ValueError`, rather than rejecting the snapshot with `GraphDiffusionContractError`. This violates the Review Card's numeric/NaN/overflow and fail-closed gates and can invalidate mass/provenance artifacts. Minimal fix: require finite numeric weights and reject values whose normalized arithmetic cannot be represented; add finite checks for totals/shares and contract-level errors.
  Verification gap: reviewer probes in `.work/REVIEW-TSKG-MFO-GRAPH-01/probes.json` reproduce acceptance; add NaN, ±Infinity, overflow-sum, and post-diffusion finite/mass assertions.

- [P1] Branching path expansion has no resource bound - `app/tskg/graph_diffusion.py:184-208`
  Trigger: provide a valid, high-branching acyclic snapshot and request the allowed `max_hops=8`. The implementation materializes one state and full provenance tuple per simple path, with no cap on nodes, edges, outgoing degree, total states, or path bytes. A 9-node complete DAG already produced 12,870 output values in the reviewer probe; larger valid inputs grow exponentially and can exhaust memory/CPU before the mass check. `max_hops` bounds depth only, not path explosion. Minimal fix: enforce schema-level node/edge/degree/path-state/provenance-byte budgets and fail closed before or during expansion, with an explicit bounded-work error and tested limits.
  Verification gap: add a high-branching adversarial fixture and assert deterministic bounded rejection/runtime under the declared budgets.

## Spec axis

NO_GO. As-of future/stale/missing rejection, bounded hop, cycle termination, deterministic ordering, baseline separation, mass conservation on the fixture, and per-value provenance passed. The two P1 findings leave numeric validity and bounded execution unproven/violated.

## Standards axis

NO_GO. Closed field sets and production isolation are present, but numeric parsing is not fail-closed and the algorithm lacks a branching/resource bound required by the Review Card's numeric and performance gates.

## Reviewer-owned probe summary

Duplicate same-endpoint edges and self-loops are accepted; self-loops are excluded by visited-node traversal. Ambiguous datetime-form `as_of_date` is rejected. These outcomes are recorded as probes; they are not separately promoted to findings because the current card does not define duplicate-edge or self-loop rejection semantics.

## Required verification and recomputation

- `<repo-root>/.venv/bin/python -m pytest tests/test_tskg_graph_diffusion.py tests/test_tskg_mfo01.py`: 18 passed.
- `<repo-root>/.venv/bin/python scripts/verify_tskg_graph_diffusion.py`: `OK`; rejected future/stale/missing = 3; max hop = 2.
- `git diff --check`: PASS.
- Recomputed artifact hash: `82e734cb7779808ae25afa64bbbcdd5b60bff3caa00c48fa543c324585f510d9`.
- Recomputed seed mass: `1.0`; shadow values: `security-a=0.0625`, `security-b=0.25`, `security-c=0.6875`, `security-d=0.0`.

## Verdict

`NO_GO` — return to formal Repair for both P1 findings. This is a single independent review evidence set; no repair or merge was performed.
