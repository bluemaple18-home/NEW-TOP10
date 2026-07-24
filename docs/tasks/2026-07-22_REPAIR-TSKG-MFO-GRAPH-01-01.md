---
card_id: REPAIR-TSKG-MFO-GRAPH-01-01
chain_id: TOP10-NEXT-WAVE-20260722
status: REPAIR_COMPLETED
final_candidate: 6115a3c578e878682dbac79b7903c0f6e0a033d9
type: bounded-repair
repair_generation: 1
candidate_sha: 1c6a760a0d655f370e9056131d9fcba53851b97b
review_evidence_sha: b904a22
original_reviewer_thread: 019f895e-a8e2-7e92-9985-4ea4354625a2
reasoning: medium
thickness: strict
---

# REPAIR-TSKG-MFO-GRAPH-01-01

只修 `docs/evidence/REVIEW-TSKG-MFO-GRAPH-01/review.md` 的兩個 P1；不得擴張 Graph、ranking、feature 或 production scope。

## Fixed repairs

1. Numeric fail-closed：snapshot 拒絕 NaN、±Infinity、overflow-prone edge weights；所有 total/share/diffused values 在 hash/artifact 前必須 finite，契約錯誤統一為 `GraphDiffusionContractError`。
2. Resource bound：為 node、edge、out-degree、expanded path-state 與／或 provenance bytes 建立明確 deterministic budgets；高分支輸入在耗盡 CPU/RAM 前 fail-closed，錯誤可測且不輸出部分 artifact。

## Required RED → GREEN

- 原 Reviewer probes 先重現兩個 P1 RED。
- 新增 NaN、±Infinity、overflow sum、post-diffusion finite/mass 測試。
- 新增高分支 DAG budget rejection、boundary-at-limit success、deterministic error 測試。
- 保持 future/stale/missing rejection、cycle handling、bounded hop、mass conservation、determinism、provenance 與 no-diffusion baseline 無回歸。

## Allowlist

- `app/tskg/graph_diffusion.py`
- `tests/test_tskg_graph_diffusion.py`
- `scripts/verify_tskg_graph_diffusion.py`
- `docs/evidence/REPAIR-TSKG-MFO-GRAPH-01-01/**`
- `.work/REPAIR-TSKG-MFO-GRAPH-01-01/**`

不得修改既有 implementation/review evidence、fixture、ranking、feature、daily production 或 secure attachment。

## Verification

```bash
<repo-root>/.venv/bin/python -m pytest tests/test_tskg_graph_diffusion.py tests/test_tskg_mfo01.py
<repo-root>/.venv/bin/python scripts/verify_tskg_graph_diffusion.py
<repo-root>/.venv/bin/python -m py_compile app/tskg/graph_diffusion.py scripts/verify_tskg_graph_diffusion.py
git diff --check
```

完成後提交 repair candidate 並 push branch；回報完整 SHA、RED→GREEN、budgets 與 allowlist/privacy/non-production 證據。不得自行 Review 或 merge。
