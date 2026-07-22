# REPAIR-TSKG-MFO-GRAPH-01-01 Evidence

## Lineage and scope

- Parent: `b2412f8a5275bb4e921480aa11bba5bf37d47872`
- Reviewed candidate ancestor: `1c6a760a0d655f370e9056131d9fcba53851b97b`
- Repair scope: numeric fail-closed and deterministic graph diffusion resource budgets only.
- Changed paths are limited to the repair allowlist: `app/tskg/graph_diffusion.py`, `tests/test_tskg_graph_diffusion.py`, and this evidence file.

## RED -> GREEN

Before the repair, the original reviewer probe showed:

- `NaN` and `+Infinity` weights were accepted by `GraphDiffusionSnapshot` and later leaked a generic JSON `ValueError`.
- `1e308` was accepted.
- A valid 9-node complete DAG with `max_hops=8` produced `12,870` values.

After the repair, the same probe showed:

- `NaN`, `+Infinity`, and `1e308` all reject as `GraphDiffusionContractError`.
- The same DAG rejects as `GraphDiffusionContractError: path-state budget exceeded: maximum is 1024`.
- The existing verifier remains `OK`, with canonical hash `82e734cb7779808ae25afa64bbbcdd5b60bff3caa00c48fa543c324585f510d9`.

## Contract budgets

- `MAX_NODES = 256`
- `MAX_EDGES = 2048`
- `MAX_OUT_DEGREE = 32`
- `MAX_PATH_STATES = 1024` per seed/hop materialized state list
- `MAX_EDGE_WEIGHT = 1e300`

The path-state boundary test materializes exactly `1,024` values and succeeds; the next branching level fails deterministically before unbounded expansion.

## Verification

Using `<repo-root>/.venv/bin/python` without environment creation or downloads:

- `pytest tests/test_tskg_graph_diffusion.py tests/test_tskg_mfo01.py`: `25 passed`
- `scripts/verify_tskg_graph_diffusion.py`: `OK`; existing canonical hash, mass, freshness/stale/missing rejection and max-hop checks preserved.
- `py_compile` for implementation and verifier: pass.
- `git diff --check`: pass.
- Exact changed-file allowlist: pass.
- Privacy scan: no `/Users/`, `/private/`, `file://`, credential, token, or secret additions.
- Non-production scan: no ranking, feature, production entrypoint, dependency, or secure-attachment changes.
