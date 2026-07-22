#!/usr/bin/env python3
"""驗證 TSKG Theme membership 與 deterministic flow aggregation。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.tskg.flow_observation import SecurityFlowObservationFixture
from app.tskg.theme_membership import ThemeMembershipSnapshot, aggregate_theme_institutional_flow

def main() -> int:
    snapshot = ThemeMembershipSnapshot(json.loads((ROOT / "data/fixtures/tskg/theme_membership_v1.json").read_text()))
    flow = SecurityFlowObservationFixture.from_file(ROOT / "data/fixtures/tskg/security_flow_observations_v1.json")
    first = aggregate_theme_institutional_flow(snapshot, flow, as_of_date="2026-07-17")
    second = aggregate_theme_institutional_flow(snapshot, flow, as_of_date="2026-07-17")
    if first != second or first["venue_coverage"]["TPEX"] != "BLOCKED":
        print(json.dumps({"status": "FAILED"}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "OK", "canonical_hash": first["canonical_hash"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
