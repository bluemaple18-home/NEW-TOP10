---
card_id: TSKG-MFO-GRAPH-01
chain_id: TOP10-NEXT-WAVE-20260722
status: CARD_DRAFTED
type: shadow-research-implementation
owner: receiving Mini
model: receiving Mini
reasoning: medium
model_reason: 使用者指定 Mini；圖擴散限制為 shadow-only，並以 leakage/parity gates 防止進 production。
thickness: strict
depends_on: [TSKG-MFO-THEME-01]
worktree: receiving_host_must_provision
---

# TSKG-MFO-GRAPH-01 Shadow Graph Diffusion

任務ID：TSKG-MFO-GRAPH-01
卡片類型｜派工對象：Graph Shadow Research｜Mini
請讀：docs/specs/TSKG_v1.1.md、app/tskg/repository.py、app/tskg/flow_read_model.py、docs/tasks/2026-07-20_TSKG-OSS-ADR-01_reference_adoption_decision.md
任務目的：在 evidence-backed、time-valid graph 上建立可解釋的資金 diffusion shadow artifact，不影響 production ranking
證據路徑：docs/evidence/TSKG-MFO-GRAPH-01/、artifacts/tskg/graph_diffusion_*.json

## Contract

- 只使用 as-of 時點可見的 edge/membership；禁止 future edge、future return 或 model feedback leakage。
- 每個 diffusion value 可回溯 source observation、edge path、weight/version、hop、decay 與 coverage。
- 先支援 bounded hop、deterministic seed/order、cycle handling、mass-conservation/tolerance。
- 與 no-diffusion baseline 比較；輸出 research-only artifact。
- 不修改 RankingPolicy、risk_adjusted_score、production feature contract 或 daily production path。

## Likely allowlist

- app/tskg/graph_*.py
- scripts/build_tskg_graph_diffusion.py
- scripts/verify_tskg_graph_diffusion.py
- data/fixtures/tskg/graph_diffusion_*.json
- tests/test_tskg_graph_diffusion.py
- docs/tasks/、docs/evidence/、.work/ 本卡路徑

## Verification

```bash
uv run pytest tests/test_tskg_graph_diffusion.py tests/test_tskg_mfo01.py
uv run python scripts/verify_tskg_graph_diffusion.py
git diff --check
```

測試至少含 cycle、missing edge、stale edge、future edge rejection、determinism、bounded hop 與 provenance trace。
