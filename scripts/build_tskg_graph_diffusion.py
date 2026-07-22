#!/usr/bin/env python3
"""建立離線、research-only 的 TSKG graph diffusion artifact。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.tskg.graph_diffusion import GraphDiffusionSnapshot, build_graph_diffusion_shadow


def main() -> int:
    fixture = json.loads((ROOT / "data/fixtures/tskg/graph_diffusion_v1.json").read_text(encoding="utf-8"))
    snapshot = GraphDiffusionSnapshot(fixture)
    artifact = build_graph_diffusion_shadow(snapshot, ["security-a"], max_hops=2, decay=0.75)
    output = ROOT / "artifacts/tskg/graph_diffusion_2026-07-17.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "artifact": str(output.relative_to(ROOT)), "canonical_hash": artifact["canonical_hash"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
