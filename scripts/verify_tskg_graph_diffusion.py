#!/usr/bin/env python3
"""驗證 graph diffusion 的 freshness、determinism、bounded hop 與 mass contract。"""

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.tskg.graph_diffusion import GraphDiffusionContractError, GraphDiffusionSnapshot, build_graph_diffusion_shadow


def main() -> int:
    payload = json.loads((ROOT / "data/fixtures/tskg/graph_diffusion_v1.json").read_text(encoding="utf-8"))
    snapshot = GraphDiffusionSnapshot(payload)
    first = build_graph_diffusion_shadow(snapshot, ["security-a"], max_hops=2, decay=0.75)
    second = build_graph_diffusion_shadow(snapshot, ["security-a"], max_hops=2, decay=0.75)
    reordered = deepcopy(payload)
    reordered["nodes"].reverse()
    reordered["edges"].reverse()
    third = build_graph_diffusion_shadow(GraphDiffusionSnapshot(reordered), ["security-a"], max_hops=2, decay=0.75)
    missing = deepcopy(payload)
    missing["edges"][0]["target_id"] = "security-missing"
    stale = deepcopy(payload)
    stale["edges"][0]["valid_to"] = "2026-07-16"
    future = deepcopy(payload)
    future["edges"][0]["valid_from"] = "2026-07-18"
    rejected = 0
    for mutated in (missing, stale, future):
        try:
            GraphDiffusionSnapshot(mutated)
        except GraphDiffusionContractError:
            rejected += 1
    total = sum(row["output_mass"] for row in first["mass_conservation"])
    values = first["values"]
    passed = (
        first == second == third
        and rejected == 3
        and all(row["hop"] <= 2 for row in values)
        and all(row["within_tolerance"] for row in first["mass_conservation"])
        and total == 1.0
        and first["production_impact"] == "NONE_SHADOW_ONLY"
        and any(row["edge_path"] for row in values)
        and first["baseline_no_diffusion"]["security-a"] == 1.0
    )
    print(json.dumps({"status": "OK" if passed else "FAILED", "canonical_hash": first["canonical_hash"], "rejected_future_stale_missing": rejected, "max_hop": max(row["hop"] for row in values)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
