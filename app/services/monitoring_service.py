"""監控 service。

API 只讀 artifact，不同步執行監控計算。
"""

from __future__ import annotations

from app.contracts import FactorMetricContract, FactorMonitorResponse
from app.data.monitoring_repository import MonitoringRepository


class MonitoringService:
    def __init__(self, repository: MonitoringRepository):
        self.repository = repository

    def factor_report(self) -> FactorMonitorResponse:
        payload = self.repository.load_factor_report()
        if payload is None:
            return FactorMonitorResponse(available=False, notes="尚無 factor monitor artifact，請先執行 scripts/monitor_factors.py")

        return FactorMonitorResponse(
            available=True,
            status=payload.get("status"),
            generated_at=payload.get("generated_at"),
            horizon_days=payload.get("horizon_days"),
            summary=payload.get("summary") or {},
            factors=[FactorMetricContract(**item) for item in payload.get("factors", [])],
        )

    def clear_cache(self) -> None:
        self.repository.clear_cache()
