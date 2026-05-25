"""個股詳情聚合 API。

此 router 只讀既有資料與 artifact，不執行回測或外部資料抓取。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.contracts import StockDetailResponse, StockReferenceResponse
from app.services.stock_detail_service import StockDetailService


def create_stock_detail_router(stock_detail_service: StockDetailService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["stock-detail"])

    @router.get("/stocks/{stock_id}/detail")
    def stock_detail(stock_id: str, limit: int = Query(1200, ge=30, le=1200)) -> StockDetailResponse:
        try:
            return stock_detail_service.stock_detail(stock_id=stock_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/stocks/{stock_id}/reference")
    def stock_reference(stock_id: str) -> StockReferenceResponse:
        try:
            return stock_detail_service.market_service.reference_repository.stock_reference(stock_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
