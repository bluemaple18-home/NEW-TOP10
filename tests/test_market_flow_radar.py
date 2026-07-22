"""UI-MFR-01 read-only radar API contract tests。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routers.market_flow import create_market_flow_router
from app.api.main import app as main_app
from app.tskg.market_flow_radar import (
    RADAR_SCHEMA_VERSION,
    MarketFlowRadarResponse,
    build_market_flow_radar_response,
)


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


def test_radar_api_returns_versioned_envelope_for_invalid_calendar_date() -> None:
    app = FastAPI()
    app.include_router(create_market_flow_router(ROOT))
    response = TestClient(app).get("/api/v1/market-flow/radar?as_of_date=2026-99-99")

    assert response.status_code == 422
    assert response.json() == {
        "schema_version": "market-flow-radar-error-v1",
        "error": {"code": "INVALID_AS_OF_DATE", "message": "as_of_date 必須是有效的 YYYY-MM-DD 日期"},
    }


@pytest.mark.parametrize("as_of_date", ["20260717", "2026-W29-5"])
def test_radar_api_rejects_alternate_iso_date_forms(as_of_date: str) -> None:
    app = FastAPI()
    app.include_router(create_market_flow_router(ROOT))

    response = TestClient(app).get("/api/v1/market-flow/radar", params={"as_of_date": as_of_date})

    assert response.status_code == 422
    assert response.json() == {
        "schema_version": "market-flow-radar-error-v1",
        "error": {"code": "INVALID_AS_OF_DATE", "message": "as_of_date 必須是有效的 YYYY-MM-DD 日期"},
    }


def test_radar_error_envelope_keeps_allowed_origin_cors_header() -> None:
    response = TestClient(main_app).get(
        "/api/v1/market-flow/radar?as_of_date=2026-99-99",
        headers={"Origin": "http://127.0.0.1:5173"},
    )

    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_radar_api_returns_versioned_envelope_for_date_outside_fixture() -> None:
    app = FastAPI()
    app.include_router(create_market_flow_router(ROOT))
    response = TestClient(app).get("/api/v1/market-flow/radar?as_of_date=2026-01-01")

    assert response.status_code == 422
    assert response.json()["schema_version"] == "market-flow-radar-error-v1"
    assert response.json()["error"]["code"] == "DATE_OUT_OF_RANGE"


def test_radar_response_model_is_closed_and_matches_runtime_payload() -> None:
    payload = build_market_flow_radar_response(ROOT)
    parsed = MarketFlowRadarResponse.model_validate(payload)

    assert parsed.schema_version == RADAR_SCHEMA_VERSION
    assert MarketFlowRadarResponse.model_json_schema()["additionalProperties"] is False
    assert MarketFlowRadarResponse.model_json_schema()["$defs"]["RadarItemResponse"]["additionalProperties"] is False
    with_extra = {**payload, "unexpected": True}
    try:
        MarketFlowRadarResponse.model_validate(with_extra)
    except ValueError:
        pass
    else:
        raise AssertionError("closed response model accepted an unknown field")


def test_radar_openapi_declares_closed_response_model() -> None:
    app = FastAPI()
    app.include_router(create_market_flow_router(ROOT))
    schema = TestClient(app).get("/openapi.json").json()
    response_schema = schema["paths"]["/api/v1/market-flow/radar"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert response_schema["$ref"] == "#/components/schemas/MarketFlowRadarResponse"
    assert schema["components"]["schemas"]["MarketFlowRadarResponse"]["additionalProperties"] is False
