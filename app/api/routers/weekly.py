"""本週動能候選 API。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.contracts import InvestmentSettingsContract, WeeklyCandidatesResponse
from app.services.weekly_decision_service import WeeklyDecisionService


def create_weekly_router(weekly_decision_service: WeeklyDecisionService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["weekly"])

    @router.get("/weekly-candidates")
    def weekly_candidates(
        risk_style: str = Query("balanced", pattern="^(conservative|balanced|aggressive)$"),
        target_type: str = Query("stocks", pattern="^(stocks|etfs|both)$"),
        holding_period: str = Query("swing", pattern="^(swing|midterm|longterm)$"),
        entry_preference: str = Query("mixed", pattern="^(breakout|pullback|continuation|mixed)$"),
        risk_limit: str = Query("excludeThemes", pattern="^(lowVolatility|excludeThemes|acceptHighVolatility)$"),
        limit: int = Query(10, ge=1, le=30),
    ) -> WeeklyCandidatesResponse:
        settings = InvestmentSettingsContract(
            risk_style=risk_style,
            target_type=target_type,
            holding_period=holding_period,
            entry_preference=entry_preference,
            risk_limit=risk_limit,
        )
        return weekly_decision_service.weekly_candidates(settings=settings, limit=limit)

    return router
