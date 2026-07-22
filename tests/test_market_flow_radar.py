"""UI-MFR-01 read-only radar API contract tests。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.market_flow import create_market_flow_router
from app.tskg.market_flow_radar import RADAR_SCHEMA_VERSION, build_market_flow_radar_response


ROOT = Path(__file__).resolve().parents[1]


def test_radar_response_is_versioned_deterministic_and_research_only() -> None:
    first = build_market_flow_radar_response(ROOT)
    second = build_market_flow_radar_response(ROOT)

    assert first == second
    assert first["schema_version"] == RADAR_SCHEMA_VERSION
    assert first["view_version"].startswith("ui-mfr-01-")
    assert first["as_of_date"] == "2026-07-17"
    assert first["coverage_status"] == "COMPLETE"
    assert first["freshness"] == "STALE"
    assert first["venue_coverage"] == {"TWSE": "AVAILABLE", "TPEX": "BLOCKED"}
    assert all(item["research_only"] for item in first["items"])
    assert first["research_boundary"]["ranking_impact"] == "NONE"
    assert [item["theme_id"] for item in first["items"]] == ["theme-ai", "theme-semiconductor"]


def test_radar_api_is_get_only_and_exposes_provenance() -> None:
    app = FastAPI()
    app.include_router(create_market_flow_router(ROOT))
    client = TestClient(app)

    response = client.get("/api/v1/market-flow/radar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["source_type"] == "SYNTHETIC_FIXTURE"
    assert payload["evidence"] == [
        "fixture://tskg/theme-membership-v1",
        "fixture://tskg/security-flow-observations-v1",
    ]
    assert all(route.methods == {"GET"} for route in app.routes if getattr(route, "path", "").endswith("/radar"))
