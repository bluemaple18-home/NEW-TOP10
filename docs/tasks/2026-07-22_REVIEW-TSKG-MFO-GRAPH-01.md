---
card_id: REVIEW-TSKG-MFO-GRAPH-01
chain_id: TOP10-NEXT-WAVE-20260722
status: READY_FOR_INDEPENDENT_REVIEW
type: independent-code-review
reviewed_candidate: 1c6a760a0d655f370e9056131d9fcba53851b97b
base_sha: 4dece38211968ee3d4f68937d2968940520ce145
reviewer: independent Mini
reasoning: medium
thickness: strict
---

# REVIEW-TSKG-MFO-GRAPH-01

角色：獨立 Reviewer，只審不修。不得修改 candidate、不得 merge main、不得自行建立 Repair。

## Fixed scope

- reviewed range: `4dece38211968ee3d4f68937d2968940520ce145..1c6a760a0d655f370e9056131d9fcba53851b97b`
- implementation card: `docs/tasks/2026-07-22_TSKG-MFO-GRAPH-01_shadow_graph_diffusion.md`
- evidence input: `docs/evidence/TSKG-MFO-GRAPH-01/verification.md`
- 只能新增 `docs/evidence/REVIEW-TSKG-MFO-GRAPH-01/**` 與 `.work/REVIEW-TSKG-MFO-GRAPH-01/**`

## Review gates

- Spec axis：as-of edge validity、future/stale/missing rejection、bounded hop、cycle handling、determinism、mass conservation、no-diffusion baseline、逐值 provenance。
- Standards axis：closed schema、fail-closed parsing、stable canonical serialization、numeric/NaN/negative/overflow boundaries、performance bounds、既有 TSKG regression。
- Reviewer-owned probes 必須至少覆蓋：cycle/repeated node、duplicate edge、self-loop、zero/negative/non-finite weight、out-of-range decay/hops/tolerance、ambiguous timestamps、path explosion、mass tolerance、artifact determinism。
- 沿 import/diff 證明沒有修改或接入 RankingPolicy、risk_adjusted_score、production feature contract 或 daily production path。
- privacy/secret/local-path scan；不得讀取或解密 NEXT_WAVE secure attachment。

## Required verification

```bash
<repo-root>/.venv/bin/python -m pytest tests/test_tskg_graph_diffusion.py tests/test_tskg_mfo01.py
<repo-root>/.venv/bin/python scripts/verify_tskg_graph_diffusion.py
git diff --check
```

Reviewer 必須重算 artifact/hash 與核心 invariants，不可只採信 implementation 文案。Findings 使用 P0–P3、`path:line`、觸發條件、風險、最小修正與驗證缺口。

## Verdict

- `GO`：無 P0/P1，契約與 reviewer-owned probes 通過。
- `NO_GO`：任一 correctness/leakage/mass/provenance/fail-closed P1，列出可重現 probe；交回正式 Repair。
- `BLOCKED`：只有客觀環境阻斷才能使用。

提交單一 review evidence commit，回報完整 SHA 與 Spec／Standards／Overall verdict。
