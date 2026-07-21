"""SecurityFlowObservation 的 source-neutral、非策略 read model。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from app.tskg.flow_observation import SecurityFlowObservationFixture


SCHEMA_VERSION = "tskg-security-flow-read-model-v1"
INVESTOR_ORDER = (
    "FOREIGN",
    "INVESTMENT_TRUST",
    "DEALER",
    "ALL_INSTITUTIONAL",
)
_INVESTOR_POSITION = {name: position for position, name in enumerate(INVESTOR_ORDER)}


def build_security_flow_read_model(
    fixture: SecurityFlowObservationFixture,
) -> dict[str, Any]:
    """把已驗證 observation 投影成 deterministic read model。"""

    if not isinstance(fixture, SecurityFlowObservationFixture):
        raise TypeError("fixture must be a SecurityFlowObservationFixture")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for observation in fixture.observations():
        key = (observation["security_id"], observation["trade_date"])
        grouped.setdefault(key, []).append(observation)

    items: list[dict[str, Any]] = []
    for (security_id, trade_date), observations in sorted(grouped.items()):
        ordered = sorted(
            observations,
            key=lambda row: (
                _INVESTOR_POSITION[row["investor_type"]],
                row["observation_id"],
            ),
        )
        present = {row["investor_type"] for row in ordered}
        missing = [name for name in INVESTOR_ORDER if name not in present]
        is_stale = any(row["is_stale"] for row in ordered)
        warnings: list[str] = []
        if missing:
            warnings.append(f"missing investor types: {', '.join(missing)}")
        if is_stale:
            warnings.append("contains stale observations")

        provenance_refs = sorted(
            {
                (row["source_id"], row["evidence_id"])
                for row in ordered
            }
        )
        items.append(
            {
                "security_id": security_id,
                "trade_date": trade_date,
                "observations": [
                    {
                        field: deepcopy(row[field])
                        for field in (
                            "observation_id",
                            "investor_type",
                            "currency",
                            "net_buy_value_1d",
                            "source_id",
                            "evidence_id",
                            "observed_at",
                            "retrieved_at",
                            "freshness",
                            "is_stale",
                        )
                    }
                    for row in ordered
                ],
                "provenance_refs": [
                    {"source_id": source_id, "evidence_id": evidence_id}
                    for source_id, evidence_id in provenance_refs
                ],
                "freshness": "STALE" if is_stale else "FRESH",
                "is_stale": is_stale,
                "warnings": warnings,
            }
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "formula_version": fixture.summary()["formula_version"],
        "items": items,
    }
    return {**core, "canonical_hash": _canonical_hash(core)}


def query_security_flow_read_model(
    read_model: dict[str, Any],
    *,
    security_id: str,
    trade_date: str,
) -> dict[str, Any] | None:
    """以 security/date exact lookup，回傳 defensive copy。"""

    if not isinstance(read_model, dict) or read_model.get("schema_version") != SCHEMA_VERSION:
        raise TypeError("read_model must use tskg-security-flow-read-model-v1")
    for item in read_model.get("items", []):
        if item.get("security_id") == security_id and item.get("trade_date") == trade_date:
            return deepcopy(item)
    return None


def _canonical_hash(value: dict[str, Any]) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
