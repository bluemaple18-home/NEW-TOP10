#!/usr/bin/env python3
"""建立離線、可重算的 TSKG Theme flow read model。"""

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
    result = aggregate_theme_institutional_flow(snapshot, flow, as_of_date=snapshot.as_dict()["as_of_date"])
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
