# CP-NEXT-WAVE-A Verification

Status: `PASS`

Base: `e5a46d4`

## TSKG regression matrix

The combined TSKG suite covered flow read models, Graph diffusion, MFO,
research adoption/evidence, SLC-01, source contracts, T86 automation, Theme
aggregation and TWSE T86 parsing.

```text
96 passed, 1 upstream Starlette deprecation warning
```

## Verifiers

- Research evidence envelope: `OK` with zero failed checks, using the first
  versioned envelope in `docs/evidence/TSKG-RSCH-03/pilot.json`.
- Theme flow: `OK`, canonical hash
  `b6b8f1f053ede8aa1c90f75da22fea1758d7e9edb2d2ca6eb02833e8536c830c`.
- Graph diffusion: `OK`, canonical hash
  `82e734cb7779808ae25afa64bbbcdd5b60bff3caa00c48fa543c324585f510d9`;
  three future/stale/missing edges rejected and max hop observed as 2.

The initial research verifier invocation without `--artifact`, and a later
invocation against the pilot wrapper rather than an individual envelope, were
CLI/input selection errors. The corrected invocation validated the versioned
envelope and is the checkpoint result.

This checkpoint does not approve feature promotion or ranking mutation. It
only unlocks `FEATURE-PROMOTE-02` to make a fail-closed evidence decision.
