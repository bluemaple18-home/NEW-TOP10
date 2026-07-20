"""TSKG synthetic SecurityFlowObservation closed-schema contract。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from app.tskg.identity import parse_utc_instant


_TOP_LEVEL_FIELDS = {
    "fixture_version",
    "schema_version",
    "formula_version",
    "provenance",
    "evidence",
    "observations",
}
_PROVENANCE_FIELDS = {"source_id", "source_type", "description"}
_EVIDENCE_FIELDS = {"evidence_id", "source_id", "locator", "evidence_type"}
_OBSERVATION_FIELDS = {
    "observation_id",
    "security_id",
    "trade_date",
    "investor_type",
    "currency",
    "net_buy_value_1d",
    "source_id",
    "evidence_id",
    "observed_at",
    "retrieved_at",
    "freshness",
    "is_stale",
}
_INVESTOR_TYPES = {
    "FOREIGN",
    "INVESTMENT_TRUST",
    "DEALER",
    "ALL_INSTITUTIONAL",
}
_FRESHNESS_STATES = {"FRESH", "STALE"}
_PROHIBITED_FIELDS = {
    "net_buy_value_5d",
    "net_buy_value_20d",
    "price_change_5d",
    "flow_acceleration",
    "flow_force_ratio",
    "anomaly_type",
    "score",
    "rank",
    "prediction",
    "recommendation",
    "buy_signal",
    "sell_signal",
    "target_price",
    "stop_loss",
    "expected_return",
    "upside",
    "weight",
}
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FlowObservationContractError(ValueError):
    """Synthetic flow fixture 違反 MFO-01 contract。"""


class SecurityFlowObservationFixture:
    """驗證並提供 deterministic、唯讀的 raw security-flow records。"""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        if not isinstance(fixture, Mapping):
            raise FlowObservationContractError("fixture must be an object")
        canonical = self._validate_and_canonicalize(deepcopy(dict(fixture)))
        self._fixture = canonical
        self._by_semantic_key = {
            self._semantic_key(record): record
            for record in canonical["observations"]
        }

    @classmethod
    def from_file(cls, path: Path) -> "SecurityFlowObservationFixture":
        with path.open("r", encoding="utf-8") as fixture_file:
            return cls(json.load(fixture_file))

    @classmethod
    def from_mapping(
        cls, fixture: Mapping[str, Any]
    ) -> "SecurityFlowObservationFixture":
        return cls(fixture)

    def observations(self) -> tuple[dict[str, Any], ...]:
        """依日期、證券、法人別排序回傳 defensive copies。"""

        return tuple(deepcopy(self._fixture["observations"]))

    def get(
        self,
        *,
        security_id: str,
        trade_date: str,
        investor_type: str,
    ) -> dict[str, Any] | None:
        """以 MFO-01 semantic key 執行 exact lookup。"""

        record = self._by_semantic_key.get(
            (security_id, trade_date, investor_type)
        )
        return deepcopy(record) if record is not None else None

    def summary(self) -> dict[str, Any]:
        observations = self._fixture["observations"]
        return {
            "fixture_version": self._fixture["fixture_version"],
            "schema_version": self._fixture["schema_version"],
            "formula_version": self._fixture["formula_version"],
            "observation_count": len(observations),
            "security_count": len(
                {observation["security_id"] for observation in observations}
            ),
            "stale_count": sum(
                observation["is_stale"] for observation in observations
            ),
            "investor_types": sorted(
                {observation["investor_type"] for observation in observations}
            ),
        }

    @classmethod
    def _validate_and_canonicalize(cls, fixture: dict[str, Any]) -> dict[str, Any]:
        cls._reject_prohibited_fields(fixture)
        _require_closed_shape(fixture, _TOP_LEVEL_FIELDS, "fixture")
        expected_versions = {
            "fixture_version": "security-flow-v1",
            "schema_version": "tskg-security-flow-observation-v1",
            "formula_version": "raw-only-v1",
        }
        for field, expected in expected_versions.items():
            if fixture.get(field) != expected:
                raise FlowObservationContractError(f"{field} must equal {expected}")

        provenance = fixture["provenance"]
        _require_closed_shape(provenance, _PROVENANCE_FIELDS, "provenance")
        if (
            not _is_non_empty_string(provenance["source_id"])
            or provenance["source_type"] != "SYNTHETIC_FIXTURE"
            or not _is_non_empty_string(provenance["description"])
        ):
            raise FlowObservationContractError("invalid synthetic provenance")

        evidence_records = fixture["evidence"]
        if not isinstance(evidence_records, list) or not evidence_records:
            raise FlowObservationContractError("evidence must be a non-empty list")
        evidence_ids: set[str] = set()
        for evidence in evidence_records:
            _require_closed_shape(evidence, _EVIDENCE_FIELDS, "evidence")
            if not all(
                _is_non_empty_string(evidence[field]) for field in _EVIDENCE_FIELDS
            ):
                raise FlowObservationContractError(
                    "evidence fields must be non-empty strings"
                )
            if evidence["source_id"] != provenance["source_id"]:
                raise FlowObservationContractError(
                    "evidence references an unknown source"
                )
            if evidence["evidence_type"] != "SYNTHETIC_SECURITY_FLOW_FIXTURE":
                raise FlowObservationContractError("unsupported evidence type")
            if not evidence["locator"].startswith("fixture://"):
                raise FlowObservationContractError(
                    "synthetic evidence locator must use fixture://"
                )
            if evidence["evidence_id"] in evidence_ids:
                raise FlowObservationContractError("duplicate evidence_id")
            evidence_ids.add(evidence["evidence_id"])

        observations = fixture["observations"]
        if not isinstance(observations, list) or not observations:
            raise FlowObservationContractError(
                "observations must be a non-empty list"
            )
        observation_ids: set[str] = set()
        semantic_keys: set[tuple[str, str, str]] = set()
        for observation in observations:
            _require_closed_shape(
                observation, _OBSERVATION_FIELDS, "SecurityFlowObservation"
            )
            cls._validate_observation(
                observation,
                source_id=provenance["source_id"],
                evidence_ids=evidence_ids,
            )
            observation_id = observation["observation_id"]
            if observation_id in observation_ids:
                raise FlowObservationContractError("duplicate observation_id")
            observation_ids.add(observation_id)
            semantic_key = cls._semantic_key(observation)
            if semantic_key in semantic_keys:
                raise FlowObservationContractError(
                    "duplicate SecurityFlowObservation semantic key"
                )
            semantic_keys.add(semantic_key)

        fixture["observations"] = sorted(
            observations,
            key=lambda row: (
                row["trade_date"],
                row["security_id"],
                row["investor_type"],
                row["observation_id"],
            ),
        )
        return fixture

    @staticmethod
    def _validate_observation(
        observation: dict[str, Any],
        *,
        source_id: str,
        evidence_ids: set[str],
    ) -> None:
        for field in ("observation_id", "security_id"):
            if not _is_non_empty_string(observation[field]):
                raise FlowObservationContractError(f"{field} must be non-empty")
        trade_date = observation["trade_date"]
        if not isinstance(trade_date, str) or not _DATE_PATTERN.fullmatch(trade_date):
            raise FlowObservationContractError("trade_date must use YYYY-MM-DD")
        try:
            date.fromisoformat(trade_date)
        except ValueError as error:
            raise FlowObservationContractError("trade_date is invalid") from error
        if (
            not isinstance(observation["investor_type"], str)
            or observation["investor_type"] not in _INVESTOR_TYPES
        ):
            raise FlowObservationContractError("investor_type is unsupported")
        if observation["currency"] != "TWD":
            raise FlowObservationContractError("currency must equal TWD")
        if type(observation["net_buy_value_1d"]) is not int:
            raise FlowObservationContractError(
                "net_buy_value_1d must be an integer TWD amount"
            )
        if observation["source_id"] != source_id:
            raise FlowObservationContractError("observation references unknown source")
        if (
            not isinstance(observation["evidence_id"], str)
            or observation["evidence_id"] not in evidence_ids
        ):
            raise FlowObservationContractError(
                "observation references unknown evidence"
            )
        try:
            observed_at = parse_utc_instant(observation["observed_at"])
            retrieved_at = parse_utc_instant(observation["retrieved_at"])
        except ValueError as error:
            raise FlowObservationContractError(str(error)) from error
        if retrieved_at < observed_at:
            raise FlowObservationContractError(
                "retrieved_at must not be before observed_at"
            )
        freshness = observation["freshness"]
        if not isinstance(freshness, str) or freshness not in _FRESHNESS_STATES:
            raise FlowObservationContractError("freshness is unsupported")
        if type(observation["is_stale"]) is not bool:
            raise FlowObservationContractError("is_stale must be boolean")
        if observation["is_stale"] != (freshness == "STALE"):
            raise FlowObservationContractError(
                "is_stale must agree with freshness"
            )

    @staticmethod
    def _semantic_key(observation: Mapping[str, Any]) -> tuple[str, str, str]:
        return (
            observation["security_id"],
            observation["trade_date"],
            observation["investor_type"],
        )

    @classmethod
    def _reject_prohibited_fields(cls, value: Any) -> None:
        if isinstance(value, dict):
            prohibited = _PROHIBITED_FIELDS.intersection(value)
            if prohibited:
                field = sorted(prohibited)[0]
                raise FlowObservationContractError(
                    f"prohibited derived or trading field: {field}"
                )
            for child in value.values():
                cls._reject_prohibited_fields(child)
        elif isinstance(value, list):
            for child in value:
                cls._reject_prohibited_fields(child)


def _require_closed_shape(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise FlowObservationContractError(
            f"{label} must contain exactly: {', '.join(sorted(fields))}"
        )


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
