"""市場資金雷達的 versioned read-only API。"""

from __future__ import annotations

from pathlib import Path
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.tskg.market_flow_radar import MarketFlowRadarResponse, build_market_flow_radar_response
from app.tskg.theme_membership import ThemeMembershipContractError

ERROR_SCHEMA_VERSION = "market-flow-radar-error-v1"


def _error_response(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "schema_version": ERROR_SCHEMA_VERSION,
            "error": {"code": code, "message": message},
        },
    )


def create_market_flow_router(project_root: Path) -> APIRouter:
    router = APIRouter(prefix="/api/v1/market-flow", tags=["market-flow"])

    @router.get("/radar", response_model=MarketFlowRadarResponse)
    def market_flow_radar(as_of_date: str = Query("2026-07-17")):
        try:
            date.fromisoformat(as_of_date)
        except ValueError:
            return _error_response("INVALID_AS_OF_DATE", "as_of_date 必須是有效的 YYYY-MM-DD 日期")
        try:
            return build_market_flow_radar_response(project_root, as_of_date=as_of_date)
        except ThemeMembershipContractError as error:
            return _error_response("DATE_OUT_OF_RANGE", str(error))

    return router
