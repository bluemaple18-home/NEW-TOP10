"""交易決策輔助 API。"""

from __future__ import annotations

from fastapi import APIRouter

from app.contracts import MarketRegimeContract
from app.services.market_service import MarketService


def create_trading_router(market_service: MarketService) -> APIRouter:
    router = APIRouter(prefix="/api/trading", tags=["trading"])

    @router.get("/regime")
    def market_regime() -> MarketRegimeContract:
        regime = market_service.market_regime()
        return MarketRegimeContract(**regime.__dict__)

    return router
