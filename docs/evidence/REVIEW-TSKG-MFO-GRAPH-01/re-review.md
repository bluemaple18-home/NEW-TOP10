# REVIEW-TSKG-MFO-GRAPH-01 Re-review

## Scope and ancestry

- Fixed repair candidate: `6115a3c578e878682dbac79b7903c0f6e0a033d9`.
- Detached Reviewer worktree was clean at candidate checkout.
- Ancestry includes original candidate `1c6a760a0d655f370e9056131d9fcba53851b97b`, Repair card `b2412f8a5275bb4e921480aa11bba5bf37d47872`, and original formal branch review evidence `b904a22a97de91096733d2c089a0d6889a0862fe` (the amended local evidence commit was `501afe1`).
- No candidate or Repair evidence was modified. No secure attachment was accessed.

## Original P1 re-review

Both original P1 probes are GREEN:

- `app/tskg/graph_diffusion.py:76-86,162-164` rejects `NaN`, `+Infinity`, `-Infinity`, and `1e308` edge weights with `GraphDiffusionContractError`.
- `app/tskg/graph_diffusion.py:249-267,280-307` rejects non-finite weight totals, propagated mass, shares, totals, and artifact values before hash/output; a post-validation overflow-sum probe also fails closed with `GraphDiffusionContractError`.
- `app/tskg/graph_diffusion.py:39-44,129-132,179-186,243-277` enforces deterministic node, edge, out-degree, and path-state budgets.

## Fresh probes

- Node budget: exactly 256 accepted; 257 rejected.
- Edge budget: exactly 2,048 accepted; 2,049 rejected.
- Out-degree budget: exactly 32 accepted; 33 rejected.
- Path-state budget: exact 1,024-state boundary succeeds; over-limit fails before unbounded expansion.
- A true 9-node complete DAG with `max_hops=8`, `decay=0.75` rejects twice with the identical `path-state budget exceeded: maximum is 1024` error.
- Maximum permitted edge weight produces JSON with `allow_nan=False`; mass remains conserved.
- Non-finite tolerance values reject as contract errors.
- Existing cycle handling, max-hop bound, mass conservation, provenance trace, no-diffusion baseline, and order-independent canonical artifact determinism all pass.

## Verification

- `<repo-root>/.venv/bin/python -m pytest tests/test_tskg_graph_diffusion.py tests/test_tskg_mfo01.py`: `25 passed`.
- `<repo-root>/.venv/bin/python scripts/verify_tskg_graph_diffusion.py`: `OK`; canonical hash `82e734cb7779808ae25afa64bbbcdd5b60bff3caa00c48fa543c324585f510d9`, rejected future/stale/missing `3`, max hop `2`.
- `<repo-root>/.venv/bin/python -m py_compile app/tskg/graph_diffusion.py scripts/verify_tskg_graph_diffusion.py`: PASS.
- `git diff --check`: PASS.
- Repair commit changed implementation/tests/repair evidence only relative to its parent; no ranking, feature contract, daily production, dependency, secret, local-path, or secure-attachment change was found.

## Residual nonblocking risk

`tolerance > 1` is still accepted. For example, `tolerance=2.0` causes initial mass `1.0` to be retained immediately and suppresses diffusion (`security-b=0.0`). This is a P2 parameter-contract hardening item, not a new P1 under the fixed Repair scope; it does not alter the verdict.

## Verdict

`GO` — both original P1s are closed, no new P1 was found, and Spec／Standards／Overall all pass. This re-review is complete pending the single evidence commit.
