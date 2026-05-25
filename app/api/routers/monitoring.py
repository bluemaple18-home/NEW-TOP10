"""監控報告只讀 API。"""

from __future__ import annotations

from fastapi import APIRouter

from app.contracts import FactorMonitorResponse
from app.services.monitoring_service import MonitoringService


def create_monitoring_router(monitoring_service: MonitoringService) -> APIRouter:
    router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

    @router.get("/factors")
    def factor_report() -> FactorMonitorResponse:
        return monitoring_service.factor_report()

    @router.post("/cache/clear")
    def clear_cache() -> dict[str, bool]:
        monitoring_service.clear_cache()
        return {"ok": True}

    return router
