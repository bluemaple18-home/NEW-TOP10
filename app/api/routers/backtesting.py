"""回測績效只讀 API。

此 router 僅暴露既有回測 artifact 摘要，不同步觸發回測計算。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.contracts import BacktestSummaryResponse
from app.services.backtest_service import BacktestService


def create_backtesting_router(backtest_service: BacktestService) -> APIRouter:
    router = APIRouter(prefix="/api/backtests", tags=["backtesting"])

    @router.get("/summary")
    def summary() -> BacktestSummaryResponse:
        return backtest_service.summary()

    @router.post("/cache/clear")
    def clear_cache() -> dict[str, bool]:
        backtest_service.clear_cache()
        return {"ok": True}

    return router
