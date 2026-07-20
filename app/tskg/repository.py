"""Versioned synthetic identity fixture repository。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from app.tskg.identity import (
    IdentityResolver,
    intervals_overlap,
    normalize_alias,
    validate_business_interval,
)


_TOP_LEVEL_FIELDS = {
    "fixture_version",
    "schema_version",
    "normalizer_version",
    "provenance",
    "identity_evidence",
    "entities",
    "aliases",
    "relationship_claims",
}
_PROVENANCE_FIELDS = {"source_id", "source_type", "description"}
_EVIDENCE_FIELDS = {"evidence_id", "source_id", "locator", "evidence_type"}
_ORGANIZATION_FIELDS = {
    "entity_id",
    "entity_type",
    "canonical_name",
    "organization_kind",
    "jurisdiction",
    "status",
}
_SECURITY_FIELDS = {
    "entity_id",
    "entity_type",
    "security_type",
    "market",
    "code",
    "issuer_id",
    "valid_time",
}
_ALIAS_FIELDS = {
    "entity_id",
    "raw_alias",
    "normalized_alias",
    "language",
    "script",
    "source_id",
    "evidence_id",
}
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")
_MARKET_PATTERN = re.compile(r"^[A-Z0-9]{2,12}$")


class FixtureContractError(ValueError):
    """Fixture 違反 SLC-01 deterministic identity contract。"""


class FixtureRepository:
    """由呼叫端注入 fixture；module import 不讀檔也不建立 singleton。"""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        canonical = self._validate_and_canonicalize(deepcopy(dict(fixture)))
        self._fixture = canonical
        self._entities_by_id = {
            entity["entity_id"]: entity for entity in canonical["entities"]
        }

    @classmethod
    def from_file(cls, path: Path) -> "FixtureRepository":
        with path.open("r", encoding="utf-8") as fixture_file:
            return cls(json.load(fixture_file))

    @classmethod
    def from_mapping(cls, fixture: Mapping[str, Any]) -> "FixtureRepository":
        return cls(fixture)

    def create_resolver(
        self, *, clock: Callable[[], datetime] | None = None
    ) -> IdentityResolver:
        return IdentityResolver(self, clock=clock)

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        entity = self._entities_by_id.get(entity_id)
        return deepcopy(entity) if entity is not None else None

    def alias_records(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._fixture["aliases"]))

    def security_records(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            deepcopy(entity)
            for entity in self._fixture["entities"]
            if entity["entity_type"] == "Security"
        )

    def metadata(self) -> dict[str, Any]:
        return {
            key: deepcopy(self._fixture[key])
            for key in (
                "fixture_version",
                "schema_version",
                "normalizer_version",
                "provenance",
            )
        }

    def summary(self) -> dict[str, Any]:
        entities = self._fixture["entities"]
        alias_targets: dict[str, set[str]] = {}
        for alias in self._fixture["aliases"]:
            alias_targets.setdefault(alias["normalized_alias"], set()).add(
                alias["entity_id"]
            )
        return {
            "fixture_version": self._fixture["fixture_version"],
            "schema_version": self._fixture["schema_version"],
            "normalizer_version": self._fixture["normalizer_version"],
            "entity_count": len(entities),
            "organization_count": sum(
                entity["entity_type"] == "Organization" for entity in entities
            ),
            "security_count": sum(
                entity["entity_type"] == "Security" for entity in entities
            ),
            "alias_count": len(self._fixture["aliases"]),
            "alias_collision_count": sum(
                len(entity_ids) > 1 for entity_ids in alias_targets.values()
            ),
        }

    @staticmethod
    def _validate_and_canonicalize(fixture: dict[str, Any]) -> dict[str, Any]:
        _require_closed_shape(fixture, _TOP_LEVEL_FIELDS, "fixture")
        expected_versions = {
            "fixture_version": "identity-v1",
            "schema_version": "tskg-identity-fixture-v1",
            "normalizer_version": "nfkc-casefold-v1",
        }
        for field, expected in expected_versions.items():
            if fixture.get(field) != expected:
                raise FixtureContractError(f"{field} must equal {expected}")

        entities = fixture.get("entities")
        aliases = fixture.get("aliases")
        if not isinstance(entities, list) or len(entities) < 12:
            raise FixtureContractError("fixture must contain at least 12 entities")
        if not isinstance(aliases, list):
            raise FixtureContractError("aliases must be a list")
        if fixture.get("relationship_claims") != []:
            raise FixtureContractError(
                "SLC-01 fixture cannot contain relationship claims"
            )

        provenance = fixture["provenance"]
        _require_closed_shape(provenance, _PROVENANCE_FIELDS, "provenance")
        if (
            not _is_non_empty_string(provenance["source_id"])
            or provenance["source_type"] != "SYNTHETIC_FIXTURE"
            or not _is_non_empty_string(provenance["description"])
        ):
            raise FixtureContractError("invalid synthetic fixture provenance")

        evidence_records = fixture["identity_evidence"]
        if not isinstance(evidence_records, list) or not evidence_records:
            raise FixtureContractError("identity_evidence must be a non-empty list")
        evidence_ids: set[str] = set()
        for evidence in evidence_records:
            _require_closed_shape(evidence, _EVIDENCE_FIELDS, "identity evidence")
            if not all(
                _is_non_empty_string(evidence[field]) for field in _EVIDENCE_FIELDS
            ):
                raise FixtureContractError(
                    "identity evidence fields must be non-empty strings"
                )
            if evidence["source_id"] != provenance["source_id"]:
                raise FixtureContractError(
                    "identity evidence references an unknown source"
                )
            if evidence["evidence_type"] != "SYNTHETIC_IDENTITY_FIXTURE":
                raise FixtureContractError("unsupported identity evidence type")
            if evidence["evidence_id"] in evidence_ids:
                raise FixtureContractError("duplicate identity evidence record")
            evidence_ids.add(evidence["evidence_id"])

        entity_ids: set[str] = set()
        organization_ids: set[str] = set()
        securities_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for entity in entities:
            if not isinstance(entity, dict):
                raise FixtureContractError("each entity must be an object")
            entity_id = entity.get("entity_id")
            entity_type = entity.get("entity_type")
            if not _is_non_empty_string(entity_id):
                raise FixtureContractError("each entity needs an opaque entity_id")
            if entity_id in entity_ids:
                raise FixtureContractError(f"duplicate entity_id: {entity_id}")
            entity_ids.add(entity_id)
            if entity_type == "Organization":
                _require_closed_shape(entity, _ORGANIZATION_FIELDS, "Organization")
                organization_ids.add(entity_id)
                if not all(
                    _is_non_empty_string(entity[field])
                    for field in ("canonical_name", "jurisdiction")
                ):
                    raise FixtureContractError(f"invalid Organization: {entity_id}")
                if entity["organization_kind"] != "COMPANY":
                    raise FixtureContractError("unsupported organization_kind")
                if entity["status"] != "ACTIVE":
                    raise FixtureContractError("unsupported Organization status")
            elif entity_type == "Security":
                _require_closed_shape(entity, _SECURITY_FIELDS, "Security")
                if entity["security_type"] not in {"EQUITY", "ETF"}:
                    raise FixtureContractError("unsupported security_type")
                if not isinstance(
                    entity["market"], str
                ) or not _MARKET_PATTERN.fullmatch(entity["market"]):
                    raise FixtureContractError(
                        "Security market must use uppercase syntax"
                    )
                if not isinstance(entity["code"], str) or not _CODE_PATTERN.fullmatch(
                    entity["code"]
                ):
                    raise FixtureContractError("Security code has invalid syntax")
                if not _is_non_empty_string(entity["issuer_id"]):
                    raise FixtureContractError("Security issuer_id must be non-empty")
                try:
                    validate_business_interval(entity["valid_time"])
                except ValueError as error:
                    raise FixtureContractError(str(error)) from error
                security_key = (entity["market"], entity["code"])
                for existing in securities_by_key.setdefault(security_key, []):
                    if intervals_overlap(existing["valid_time"], entity["valid_time"]):
                        raise FixtureContractError(
                            f"overlapping Security interval for key: {security_key}"
                        )
                securities_by_key[security_key].append(entity)
            else:
                raise FixtureContractError(f"unsupported entity_type: {entity_type}")

        for entity in entities:
            if (
                entity["entity_type"] == "Security"
                and entity.get("issuer_id") not in organization_ids
            ):
                raise FixtureContractError(
                    f"Security issuer_id is not an Organization: {entity['entity_id']}"
                )

        alias_keys: set[tuple[Any, ...]] = set()
        for alias in aliases:
            _require_closed_shape(alias, _ALIAS_FIELDS, "alias")
            if alias.get("entity_id") not in entity_ids:
                raise FixtureContractError("alias references an unknown entity")
            raw_alias = alias.get("raw_alias")
            if not _is_non_empty_string(raw_alias):
                raise FixtureContractError("alias needs raw_alias")
            if not _is_non_empty_string(alias.get("normalized_alias")) or alias.get(
                "normalized_alias"
            ) != normalize_alias(raw_alias):
                raise FixtureContractError(
                    f"alias normalized value is not reproducible: {raw_alias}"
                )
            if not all(
                _is_non_empty_string(alias[field])
                for field in ("language", "script", "source_id", "evidence_id")
            ):
                raise FixtureContractError("alias fields must be non-empty strings")
            if alias["source_id"] != provenance["source_id"]:
                raise FixtureContractError("alias references an unknown source")
            if alias["evidence_id"] not in evidence_ids:
                raise FixtureContractError("alias references unknown identity evidence")
            alias_key = tuple(alias[field] for field in sorted(_ALIAS_FIELDS))
            if alias_key in alias_keys:
                raise FixtureContractError("duplicate alias record")
            alias_keys.add(alias_key)

        fixture["entities"] = sorted(entities, key=lambda item: item["entity_id"])
        fixture["aliases"] = sorted(
            aliases,
            key=lambda item: (
                item["normalized_alias"],
                item["entity_id"],
                item["raw_alias"],
            ),
        )
        return fixture


def _require_closed_shape(
    value: Any, expected_fields: set[str], record_name: str
) -> None:
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise FixtureContractError(
            f"{record_name} must contain exactly {sorted(expected_fields)}"
        )


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
