"""市場資金雷達的 versioned read-only API。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from app.tskg.market_flow_radar import build_market_flow_radar_response


def create_market_flow_router(project_root: Path) -> APIRouter:
    router = APIRouter(prefix="/api/v1/market-flow", tags=["market-flow"])

    @router.get("/radar")
    def market_flow_radar(as_of_date: str = Query("2026-07-17", pattern=r"^\d{4}-\d{2}-\d{2}$")):
        return build_market_flow_radar_response(project_root, as_of_date=as_of_date)

    return router
