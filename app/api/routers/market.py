"""即時看盤資料 API。

此 router 只處理市場排行與 K 線資料，不執行回測。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.contracts import ApiHealth, LatestRankingResponse, StockOhlcvResponse
from app.services.market_service import MarketService


def create_market_router(market_service: MarketService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["market"])

    @router.get("/health")
    def health() -> ApiHealth:
        return market_service.health()

    @router.get("/rankings/latest")
    def latest_ranking(limit: int = Query(10, ge=1, le=100)) -> LatestRankingResponse:
        return market_service.latest_ranking(limit=limit)

    @router.get("/stocks/{stock_id}/ohlcv")
    def stock_ohlcv(stock_id: str, limit: int = Query(1200, ge=30, le=1200)) -> StockOhlcvResponse:
        response = market_service.stock_ohlcv(stock_id=stock_id, limit=limit)
        if response is None:
            raise HTTPException(status_code=404, detail=f"找不到股票資料：{stock_id}")
        return response

    @router.post("/cache/clear")
    def clear_cache() -> dict[str, bool]:
        market_service.clear_cache()
        return {"ok": True}

    return router
