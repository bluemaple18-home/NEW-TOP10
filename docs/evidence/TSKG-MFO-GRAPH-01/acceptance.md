# TSKG-MFO-GRAPH-01 Mainline Acceptance

Status: `ACCEPTED_SHADOW_ONLY`

## Fixed lineage

- base: `4dece38211968ee3d4f68937d2968940520ce145`
- original candidate: `1c6a760a0d655f370e9056131d9fcba53851b97b`
- initial independent Review: `NO_GO` at `b904a22a97de91096733d2c089a0d6889a0862fe`
- Repair 1 candidate: `6115a3c578e878682dbac79b7903c0f6e0a033d9`
- original Reviewer re-review: `GO` at `17b2400`

Repair 1 closes the two P1 findings by rejecting non-finite and overflow-prone
numeric inputs/results and enforcing deterministic node, edge, out-degree and
1,024 path-state budgets. The Reviewer independently verified exact-limit
success, over-limit rejection, a 9-node complete-DAG rejection, mass
conservation, determinism and provenance.

## Acceptance boundary

This acceptance covers only the deterministic offline shadow artifact. It does
not approve production feature promotion, ranking mutation, deployment, live
sources or trading. The known P2 that `tolerance > 1` can suppress diffusion is
recorded as a promotion risk and must not be silently treated as production
ready.

Mainline acceptance reruns 25 targeted tests, the Graph verifier, Python
compilation and `git diff --check` before push.
