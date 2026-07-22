"""把已接受的 Theme / Security flow fixture 投影成研究用雷達 response。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.tskg.flow_observation import SecurityFlowObservationFixture
from app.tskg.theme_membership import ThemeMembershipSnapshot, aggregate_theme_institutional_flow

RADAR_SCHEMA_VERSION = "market-flow-radar-read-model-v1"
RADAR_VIEW_VERSION = "ui-mfr-01-fixture-2026-07-17-v1"
THEME_LABELS = {
    "theme-ai": "AI 應用",
    "theme-semiconductor": "半導體",
}


def build_market_flow_radar_response(project_root: Path, *, as_of_date: str = "2026-07-17") -> dict[str, Any]:
    """回傳無策略欄位、可重算且具 provenance 的 Theme flow 雷達資料。"""

    fixture_root = project_root / "data" / "fixtures" / "tskg"
    membership = ThemeMembershipSnapshot.from_file(fixture_root / "theme_membership_v1.json")
    observations = SecurityFlowObservationFixture.from_file(fixture_root / "security_flow_observations_v1.json")
    aggregate = aggregate_theme_institutional_flow(membership, observations, as_of_date=as_of_date)
    items = []
    for rank, item in enumerate(aggregate["items"], start=1):
        net = item["institutional_net_value"]
        items.append({
            **item,
            "rank": rank,
            "theme_name": THEME_LABELS.get(item["theme_id"], item["theme_id"]),
            "institutional_buy_value": item["institutional_buy_value"],
            "institutional_sell_value": item["institutional_sell_value"],
            "flow_direction": "INFLOW" if net > 0 else "OUTFLOW" if net < 0 else "FLAT",
            "research_only": True,
        })
    total = sum(item["security_count"] for item in items)
    observed = sum(item["observed_security_count"] for item in items)
    stale = sum(item["stale_observation_count"] for item in items)
    return {
        "schema_version": RADAR_SCHEMA_VERSION,
        "view_version": RADAR_VIEW_VERSION,
        "as_of_date": as_of_date,
        "freshness": "STALE" if stale else "FRESH",
        "coverage": observed / total if total else 0.0,
        "coverage_status": "PARTIAL" if observed < total else "COMPLETE",
        "source": {
            "source_id": "source-synthetic-security-flow-v1",
            "source_type": "SYNTHETIC_FIXTURE",
            "description": "核准離線 fixture；不代表即時市場資料。",
        },
        "evidence": [
            "fixture://tskg/theme-membership-v1",
            "fixture://tskg/security-flow-observations-v1",
        ],
        "venue_coverage": aggregate["venue_coverage"],
        "allocation_policy": aggregate["allocation_policy"],
        "membership_snapshot": aggregate["membership_snapshot"],
        "research_boundary": {
            "graph_status": "ACCEPTED_SHADOW_ONLY",
            "graph_drilldown": "RESEARCH_ONLY",
            "ranking_impact": "NONE",
            "message": "Theme flow 與關聯圖僅供研究，不會改寫 Top10 recommendation。",
        },
        "items": items,
    }


def load_radar_fixture(project_root: Path) -> dict[str, Any]:
    """驗證 fixture 可讀；保留小型 helper 供 contract test 使用。"""
    path = project_root / "data" / "fixtures" / "tskg" / "theme_membership_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))
