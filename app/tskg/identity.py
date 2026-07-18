"""TSKG deterministic identity normalization 與 exact resolver。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Protocol


_RFC3339_UTC_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)


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

    def __init__(
        self,
        repository: IdentityRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

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
        effective_at: datetime | str | None = None,
    ) -> ResolutionResult:
        instant = (
            parse_utc_instant(effective_at)
            if effective_at is not None
            else self._clock()
        )
        instant = _require_aware_utc(instant)
        candidate_ids = sorted(
            record["entity_id"]
            for record in self._repository.security_records()
            if record["code"] == code
            and (market is None or record["market"] == market)
            and interval_may_contain(record["valid_time"], instant)
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


def parse_utc_instant(value: datetime | str) -> datetime:
    """解析 RFC 3339 UTC instant；拒絕 naive 或非 UTC 值。"""

    if isinstance(value, datetime):
        return _require_aware_utc(value)
    if not isinstance(value, str) or not _RFC3339_UTC_PATTERN.fullmatch(value):
        raise ValueError("effective instant must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            "effective instant must be an RFC 3339 UTC timestamp"
        ) from error
    return _require_aware_utc(parsed)


def validate_business_interval(interval: Any) -> None:
    """驗證 v1.1 KNOWN／UNKNOWN／UNBOUNDED business interval wire shape。"""

    if not isinstance(interval, dict) or set(interval) != {"start", "end"}:
        raise ValueError("valid_time must contain exactly start and end")
    start = _validate_endpoint(interval["start"])
    end = _validate_endpoint(interval["end"])
    if start[0] == "KNOWN" and end[0] == "KNOWN":
        if start[1] > end[1]:
            raise ValueError("valid_time start must not be after end")
        if start[1] == end[1] and not (start[2] and end[2]):
            raise ValueError("equal valid_time endpoints must both be inclusive")


def interval_may_contain(interval: dict[str, Any], instant: datetime) -> bool:
    """判斷 instant 是否未被已知界線排除；UNKNOWN 保持可能有效。"""

    instant = _require_aware_utc(instant)
    start = interval["start"]
    end = interval["end"]
    if start["kind"] == "KNOWN":
        start_at = parse_utc_instant(start["timestamp"])
        if instant < start_at or (instant == start_at and not start["inclusive"]):
            return False
    if end["kind"] == "KNOWN":
        end_at = parse_utc_instant(end["timestamp"])
        if instant > end_at or (instant == end_at and not end["inclusive"]):
            return False
    return True


def intervals_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """只在兩區間可證明重疊時回 True；UNKNOWN 不自行證明 overlap。"""

    endpoints = (
        left["start"],
        left["end"],
        right["start"],
        right["end"],
    )
    if any(endpoint["kind"] == "UNKNOWN" for endpoint in endpoints):
        return False

    latest_start = _latest_start(left["start"], right["start"])
    earliest_end = _earliest_end(left["end"], right["end"])
    if latest_start is None or earliest_end is None:
        return True
    start_at, start_inclusive = latest_start
    end_at, end_inclusive = earliest_end
    if start_at < end_at:
        return True
    return start_at == end_at and start_inclusive and end_inclusive


def _validate_endpoint(endpoint: Any) -> tuple[str, datetime | None, bool | None]:
    if not isinstance(endpoint, dict):
        raise ValueError("valid_time endpoint must be an object")
    kind = endpoint.get("kind")
    if kind == "KNOWN":
        if set(endpoint) != {"kind", "timestamp", "inclusive"}:
            raise ValueError("KNOWN endpoint has invalid shape")
        if type(endpoint["inclusive"]) is not bool:
            raise ValueError("KNOWN endpoint inclusive must be boolean")
        return kind, parse_utc_instant(endpoint["timestamp"]), endpoint["inclusive"]
    if kind in {"UNKNOWN", "UNBOUNDED"}:
        if set(endpoint) != {"kind"}:
            raise ValueError(f"{kind} endpoint cannot contain timestamp or inclusive")
        return kind, None, None
    raise ValueError("valid_time endpoint kind is unsupported")


def _latest_start(
    left: dict[str, Any], right: dict[str, Any]
) -> tuple[datetime, bool] | None:
    known = [endpoint for endpoint in (left, right) if endpoint["kind"] == "KNOWN"]
    if not known:
        return None
    latest_at = max(parse_utc_instant(endpoint["timestamp"]) for endpoint in known)
    inclusive = all(
        endpoint["inclusive"]
        for endpoint in known
        if parse_utc_instant(endpoint["timestamp"]) == latest_at
    )
    return latest_at, inclusive


def _earliest_end(
    left: dict[str, Any], right: dict[str, Any]
) -> tuple[datetime, bool] | None:
    known = [endpoint for endpoint in (left, right) if endpoint["kind"] == "KNOWN"]
    if not known:
        return None
    earliest_at = min(parse_utc_instant(endpoint["timestamp"]) for endpoint in known)
    inclusive = all(
        endpoint["inclusive"]
        for endpoint in known
        if parse_utc_instant(endpoint["timestamp"]) == earliest_at
    )
    return earliest_at, inclusive


def _require_aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("effective instant must be timezone-aware UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("effective instant must be UTC")
    return value.astimezone(UTC)
