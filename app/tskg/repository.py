"""Versioned synthetic identity fixture repository。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from app.tskg.identity import IdentityResolver, normalize_alias


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

    def create_resolver(self) -> IdentityResolver:
        return IdentityResolver(self)

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
            raise FixtureContractError("SLC-01 fixture cannot contain relationship claims")

        entity_ids: set[str] = set()
        organization_ids: set[str] = set()
        security_keys: set[tuple[str, str]] = set()
        for entity in entities:
            entity_id = entity.get("entity_id")
            entity_type = entity.get("entity_type")
            if not isinstance(entity_id, str) or not entity_id:
                raise FixtureContractError("each entity needs an opaque entity_id")
            if entity_id in entity_ids:
                raise FixtureContractError(f"duplicate entity_id: {entity_id}")
            entity_ids.add(entity_id)
            if entity_type == "Organization":
                organization_ids.add(entity_id)
                required = (
                    "canonical_name",
                    "organization_kind",
                    "jurisdiction",
                    "status",
                )
                if any(not entity.get(field) for field in required):
                    raise FixtureContractError(f"invalid Organization: {entity_id}")
            elif entity_type == "Security":
                if not isinstance(entity.get("code"), str):
                    raise FixtureContractError("Security code must remain a string")
                security_key = (entity.get("market"), entity["code"])
                if security_key in security_keys:
                    raise FixtureContractError(
                        f"duplicate active Security key: {security_key}"
                    )
                security_keys.add(security_key)
                if not isinstance(entity.get("valid_time"), dict):
                    raise FixtureContractError("Security needs a valid_time interval")
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

        for alias in aliases:
            if alias.get("entity_id") not in entity_ids:
                raise FixtureContractError("alias references an unknown entity")
            raw_alias = alias.get("raw_alias")
            if not isinstance(raw_alias, str) or not raw_alias:
                raise FixtureContractError("alias needs raw_alias")
            if alias.get("normalized_alias") != normalize_alias(raw_alias):
                raise FixtureContractError(
                    f"alias normalized value is not reproducible: {raw_alias}"
                )

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
