#!/usr/bin/env python3
"""驗證 TSKG Theme membership 與 deterministic flow aggregation。"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.tskg.flow_observation import SecurityFlowObservationFixture
from app.tskg.theme_membership import (
    ThemeMembershipContractError,
    ThemeMembershipSnapshot,
    aggregate_theme_institutional_flow,
)


def _rehash(payload: dict) -> None:
    hash_input = {
        field: payload[field]
        for field in ("as_of_date", "effective_interval", "memberships", "source", "version")
    }
    payload["content_hash"] = hashlib.sha256(
        json.dumps(hash_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def main() -> int:
    snapshot = ThemeMembershipSnapshot(json.loads((ROOT / "data/fixtures/tskg/theme_membership_v1.json").read_text()))
    flow = SecurityFlowObservationFixture.from_file(ROOT / "data/fixtures/tskg/security_flow_observations_v1.json")
    first = aggregate_theme_institutional_flow(snapshot, flow, as_of_date="2026-07-17")
    second = aggregate_theme_institutional_flow(snapshot, flow, as_of_date="2026-07-17")
    reordered_payload = json.loads((ROOT / "data/fixtures/tskg/theme_membership_v1.json").read_text())
    reordered_payload["memberships"].reverse()
    reordered = ThemeMembershipSnapshot(reordered_payload)
    source_total = sum(
        row["net_buy_value_1d"]
        for row in flow.observations()
        if row["trade_date"] == "2026-07-17" and row["investor_type"] == "ALL_INSTITUTIONAL"
    )
    allocated_total = sum(item["institutional_net_value"] for item in first["items"])
    overlap_payload = json.loads((ROOT / "data/fixtures/tskg/theme_membership_v1.json").read_text())
    overlap_payload["memberships"].append({
        "security_id": "security-3017-xtai",
        "theme_id": "theme-ai",
        "effective_from": "2026-07-10",
        "effective_to": "2026-07-20",
    })
    _rehash(overlap_payload)
    try:
        ThemeMembershipSnapshot(overlap_payload)
    except ThemeMembershipContractError:
        overlap_rejected = True
    else:
        overlap_rejected = False
    if (
        first != second
        or first != aggregate_theme_institutional_flow(reordered, flow, as_of_date="2026-07-17")
        or first["venue_coverage"]["TPEX"] != "BLOCKED"
        or allocated_total != source_total
        or not overlap_rejected
    ):
        print(json.dumps({"status": "FAILED"}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "OK", "canonical_hash": first["canonical_hash"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
