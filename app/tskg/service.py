"""TSKG SLC-01 可注入的 company query service。"""

from __future__ import annotations

import re
from typing import Any, Protocol

from app.tskg.identity import ResolutionStatus


RELATION_SECTIONS = (
    "products",
    "themes",
    "customers",
    "suppliers",
    "competitors",
    "upstream",
    "downstream",
    "etfs",
)
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")
_MARKET_PATTERN = re.compile(r"^[A-Z0-9]{2,12}$")


class CompanyRepository(Protocol):
    """Company service 所需的 fixture repository 邊界。"""

    def create_resolver(self): ...

    def get_entity(self, entity_id: str) -> dict[str, Any] | None: ...

    def metadata(self) -> dict[str, Any]: ...


class CompanyQueryError(Exception):
    """可映射至一致 API error envelope 的領域錯誤。"""

    code = "COMPANY_QUERY_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidArgumentError(CompanyQueryError):
    code = "INVALID_ARGUMENT"


class EntityNotFoundError(CompanyQueryError):
    code = "ENTITY_NOT_FOUND"


class AmbiguousEntityError(CompanyQueryError):
    code = "AMBIGUOUS_ENTITY"


class CompanyService:
    """由 Security.issuer_id 導向 Organization，不依名稱猜測 issuer。"""

    def __init__(self, repository: CompanyRepository) -> None:
        self._repository = repository
        self._resolver = repository.create_resolver()

    def get_company(
        self,
        stock_id: str,
        *,
        request_id: str,
        market: str | None = None,
    ) -> dict[str, Any]:
        normalized_stock_id = self._validate_stock_id(stock_id)
        normalized_market = self._validate_market(market)
        resolved = self._resolver.resolve_security(
            normalized_stock_id,
            market=normalized_market,
        )
        if resolved.status == ResolutionStatus.NOT_FOUND:
            raise EntityNotFoundError(
                "Security was not found",
                details={"stock_id": normalized_stock_id, "market": normalized_market},
            )
        if resolved.status == ResolutionStatus.AMBIGUOUS:
            raise AmbiguousEntityError(
                "Query resolves to multiple entities",
                details={"candidate_ids": list(resolved.candidate_ids)},
            )

        security = resolved.entity
        if security is None:  # pragma: no cover - ResolutionResult invariant
            raise RuntimeError("resolved Security is missing")
        organization = self._repository.get_entity(security["issuer_id"])
        if organization is None or organization.get("entity_type") != "Organization":
            raise RuntimeError("Security issuer_id does not resolve to an Organization")

        metadata = self._repository.metadata()
        data: dict[str, Any] = {
            "company": {
                "entity_id": organization["entity_id"],
                "entity_type": organization["entity_type"],
                "canonical_name": organization["canonical_name"],
                "organization_kind": organization["organization_kind"],
                "jurisdiction": organization["jurisdiction"],
                "status": organization["status"],
                "security": {
                    "entity_id": security["entity_id"],
                    "entity_type": security["entity_type"],
                    "security_type": security["security_type"],
                    "market": security["market"],
                    "code": security["code"],
                    "valid_time": security["valid_time"],
                },
                "provenance": {
                    "source_id": metadata["provenance"]["source_id"],
                    "fixture_version": metadata["fixture_version"],
                    "synthetic_fixture": True,
                },
            },
        }
        for section in RELATION_SECTIONS:
            data[section] = {"items": [], "next_cursor": None}

        return {
            "request_id": request_id,
            "data": data,
            "freshness": {
                "authority_watermark": f"fixture:{metadata['fixture_version']}",
                "last_successful_ingestion_at": None,
                "source_observed_through": None,
                "projection_lag_seconds": 0,
                "is_stale": False,
            },
            "provenance_summary": {
                "synthetic_fixture": True,
                "fixture_version": metadata["fixture_version"],
                "schema_version": metadata["schema_version"],
                "normalizer_version": metadata["normalizer_version"],
                "source_ids": [metadata["provenance"]["source_id"]],
                "relationship_claim_count": 0,
            },
            "warnings": [
                "Synthetic offline identity fixture; empty relation sections do not assert real-world absence."
            ],
        }

    @staticmethod
    def _validate_stock_id(stock_id: str) -> str:
        if not isinstance(stock_id, str) or not _CODE_PATTERN.fullmatch(stock_id):
            raise InvalidArgumentError(
                "stock_id must contain only ASCII letters and digits",
                details={"argument": "stock_id"},
            )
        return stock_id

    @staticmethod
    def _validate_market(market: str | None) -> str | None:
        if market is None:
            return None
        normalized = market.strip().upper()
        if not _MARKET_PATTERN.fullmatch(normalized):
            raise InvalidArgumentError(
                "market must contain only ASCII uppercase letters and digits",
                details={"argument": "market"},
            )
        return normalized
