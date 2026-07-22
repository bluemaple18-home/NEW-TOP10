# TSKG-MFO-GRAPH-01 Verification

## Contract evidence

- Base: 4dece38211968ee3d4f68937d2968940520ce145 (Theme acceptance).
- Input is a synthetic offline snapshot; no external endpoint or sensitive
  NEXT_WAVE payload was accessed.
- GraphDiffusionSnapshot uses a closed schema and rejects dangling, future,
  stale, unavailable, or provenance-incomplete edges before diffusion.
- Seeds and edges are canonically ordered; visited-node paths bound cycles and
  max_hops is limited to 8.
- Each emitted value contains the seed source observation/evidence, edge path,
  edge weight/version, hop, decay, and coverage provenance.
- Residual mass is retained at terminals/cycle boundaries and checked against
  the configured tolerance.
- The artifact exposes baseline_no_diffusion and shadow_values separately.
- production_impact=NONE_SHADOW_ONLY; no production ranking or feature module
  is imported or changed.

## Reproducible commands

    <repo-root>/.venv/bin/python -m pytest tests/test_tskg_graph_diffusion.py tests/test_tskg_mfo01.py
    18 passed

    <repo-root>/.venv/bin/python scripts/verify_tskg_graph_diffusion.py
    {"status": "OK", "canonical_hash": "82e734cb7779808ae25afa64bbbcdd5b60bff3caa00c48fa543c324585f510d9", "rejected_future_stale_missing": 3, "max_hop": 2}

    git diff --check
    PASS

The build script writes the reproducible runtime artifact to
artifacts/tskg/graph_diffusion_2026-07-17.json; runtime artifacts remain
ignored by repository policy.
