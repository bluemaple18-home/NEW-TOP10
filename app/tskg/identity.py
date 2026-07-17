"""TSKG deterministic identity normalization 與 exact resolver。"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class IdentityRepository(Protocol):
    """Resolver 所需的唯讀 repository 邊界。"""

    def alias_records(self) -> tuple[dict[str, Any], ...]: ...

    def security_records(self) -> tuple[dict[str, Any], ...]: ...

    def get_entity(self, entity_id: str) -> dict[str, Any] | None: ...


class ResolutionStatus(str, Enum):
    """Exact identity resolution 的三種穩定結果。"""

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class ResolutionResult:
    """不以例外隱藏歧義或查無結果的 resolver 回傳值。"""

    status: ResolutionStatus
    entity: dict[str, Any] | None = None
    candidate_ids: tuple[str, ...] = ()


def normalize_alias(raw_alias: str) -> str:
    """以 NFKC、空白收斂與 casefold 產生 deterministic exact-match key。"""

    if not isinstance(raw_alias, str):
        raise TypeError("alias must be a string")
    normalized = unicodedata.normalize("NFKC", raw_alias)
    return " ".join(normalized.split()).casefold()


class IdentityResolver:
    """只執行 exact deterministic match，不做 fuzzy merge。"""

    def __init__(self, repository: IdentityRepository) -> None:
        self._repository = repository

    def resolve_alias(self, raw_alias: str) -> ResolutionResult:
        normalized = normalize_alias(raw_alias)
        if not normalized:
            return ResolutionResult(ResolutionStatus.NOT_FOUND)
        candidate_ids = sorted(
            {
                record["entity_id"]
                for record in self._repository.alias_records()
                if record["normalized_alias"] == normalized
            }
        )
        return self._result_for_candidates(candidate_ids)

    def resolve_security(
        self,
        code: str,
        *,
        market: str | None = None,
    ) -> ResolutionResult:
        candidate_ids = sorted(
            record["entity_id"]
            for record in self._repository.security_records()
            if record["code"] == code
            and (market is None or record["market"] == market)
        )
        return self._result_for_candidates(candidate_ids)

    def _result_for_candidates(self, candidate_ids: list[str]) -> ResolutionResult:
        if not candidate_ids:
            return ResolutionResult(ResolutionStatus.NOT_FOUND)
        if len(candidate_ids) > 1:
            return ResolutionResult(
                ResolutionStatus.AMBIGUOUS,
                candidate_ids=tuple(candidate_ids),
            )
        entity = self._repository.get_entity(candidate_ids[0])
        if entity is None:  # pragma: no cover - repository validation guards this path
            raise RuntimeError("repository returned an unknown candidate entity")
        return ResolutionResult(
            ResolutionStatus.RESOLVED,
            entity=entity,
            candidate_ids=(candidate_ids[0],),
        )
