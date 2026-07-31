---
id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01-context
status: running
type: context_manifest
---

# Strict fact gate

- Base SHA：`6c5faff42569d6bb3b345b5253bcb00a62f9f37b`
- Affected production files：`app/research/fog_map_domain.py`、`scripts/verify_research_fog_map.py`
- Public seams：`build_burn_down_progress()`、`build_payload()`
- Call path：`scripts/build_research_fog_map.py` → `app.research.fog_map_domain.build_payload()` → `build_burn_down_progress()`；`scripts/verify_research_fog_map.py::main()` → `build_payload()`
- Data contract：current `expanded_universe_total=2,921,184`；historical rollup scope／classified subset `2,866,752`；expected `classified_pending=54,432`
- Required invariants：current total is canonical；source scope must be explicit；category sum equals classified total；`0 <= classified_total <= full_universe_total`；pending equals their difference
- Forbidden boundary：不碰 topic supply、dimension multiplier、queue／retry、ranking／model／promotion／closed registry；不執行 live Fog 或 circuit／LaunchAgent／deploy 操作
- RED command：`.venv/bin/python -m pytest -q tests/test_research_fog_map_burn_down.py`

## CodeGraph 與原始碼 seam

CodeGraph 指向 `app/research/fog_map_domain.py::build_burn_down_progress()` 與
`scripts/verify_research_fog_map.py::build_payload()`。原始碼確認 producer 直接沿用歷史
rollup 的 `full_universe_total`，verifier 又要求 `classified_total` 等於 current expanded
universe，形成 scope authority 不一致。
