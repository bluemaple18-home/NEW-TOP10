"""可獨立掛載、但不自動整合 production API 的 TSKG router。"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.tskg.service import (
    AmbiguousEntityError,
    CompanyQueryError,
    CompanyService,
    EntityNotFoundError,
    InvalidArgumentError,
)


_STATUS_BY_ERROR = {
    InvalidArgumentError: 400,
    EntityNotFoundError: 404,
    AmbiguousEntityError: 409,
}


def create_tskg_router(
    company_service: CompanyService,
    *,
    request_id_factory: Callable[[], str] | None = None,
) -> APIRouter:
    """建立只依賴注入 service 的 standalone router。"""

    make_request_id = request_id_factory or (lambda: str(uuid4()))
    router = APIRouter(prefix="/v1", tags=["tskg"])

    @router.get("/company/{stock_id}")
    def get_company(
        stock_id: str,
        market: str | None = Query(default=None),
        as_of: str | None = Query(default=None),
    ):
        request_id = make_request_id()
        try:
            return company_service.get_company(
                stock_id,
                market=market,
                as_of=as_of,
                request_id=request_id,
            )
        except CompanyQueryError as error:
            status_code = next(
                status
                for error_type, status in _STATUS_BY_ERROR.items()
                if isinstance(error, error_type)
            )
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "request_id": request_id,
                        "details": error.details,
                        "retryable": False,
                    }
                },
            )

    return router
