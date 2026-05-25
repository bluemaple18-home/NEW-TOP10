"""基本面只讀 API。"""

from __future__ import annotations

from fastapi import APIRouter

from app.contracts import StockFundamentalsResponse
from app.services.fundamental_service import FundamentalService


def create_fundamentals_router(fundamental_service: FundamentalService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["fundamentals"])

    @router.get("/stocks/{stock_id}/fundamentals")
    def stock_fundamentals(stock_id: str) -> StockFundamentalsResponse:
        return fundamental_service.stock_fundamentals(stock_id)

    @router.post("/fundamentals/cache/clear")
    def clear_cache() -> dict[str, bool]:
        fundamental_service.clear_cache()
        return {"ok": True}

    return router
