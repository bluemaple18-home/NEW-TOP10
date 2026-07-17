"""TSKG 離線 identity-to-company 垂直切片。"""

from app.tskg.identity import IdentityResolver, ResolutionResult, ResolutionStatus
from app.tskg.repository import FixtureRepository
from app.tskg.router import create_tskg_router
from app.tskg.service import CompanyService

__all__ = [
    "CompanyService",
    "FixtureRepository",
    "IdentityResolver",
    "ResolutionResult",
    "ResolutionStatus",
    "create_tskg_router",
]
