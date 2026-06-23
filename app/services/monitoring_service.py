"""監控 service。

API 只讀 artifact，不同步執行監控計算。
"""

from __future__ import annotations

from app.contracts import FactorMetricContract, FactorMonitorResponse, Top10HarnessAgentStatusContract, Top10HarnessStatusResponse
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

    def top10_harness_status(self, run_date: str | None = None, run_id: str | None = None) -> Top10HarnessStatusResponse:
        payload = self.repository.load_top10_harness_rollup(run_date=run_date, run_id=run_id)
        if payload is None:
            return Top10HarnessStatusResponse(
                available=False,
                run_date=run_date,
                run_id=run_id,
                notes="尚無 TOP10 harness rollup artifact，請先執行 daily 或 status recorder",
            )

        return Top10HarnessStatusResponse(
            available=True,
            status=payload.get("status"),
            generated_at=payload.get("generated_at"),
            run_date=payload.get("run_date"),
            run_id=payload.get("run_id"),
            summary=payload.get("summary") or {},
            agents=[Top10HarnessAgentStatusContract(**item) for item in payload.get("agents", [])],
            channels=payload.get("channels") or [],
            flows=payload.get("flows") or [],
            validation_errors=payload.get("validation_errors") or {},
            artifact_path=payload.get("_artifact_path"),
        )

    def clear_cache(self) -> None:
        self.repository.clear_cache()
