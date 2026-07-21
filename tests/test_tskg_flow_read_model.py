"""TSKG-MFO-RM-01 source-neutral read-model contract tests。"""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.tskg.flow_observation import SecurityFlowObservationFixture
from app.tskg.flow_read_model import (
    build_security_flow_read_model,
    query_security_flow_read_model,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "tskg" / "security_flow_observations_v1.json"
PROHIBITED_FIELDS = {
    "rank",
    "score",
    "weight",
    "signal",
    "prediction",
    "recommendation",
    "expected_return",
    "buy_signal",
    "sell_signal",
}


def all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(all_keys(child) for child in value.values()), set())
    if isinstance(value, list):
        return set().union(*(all_keys(child) for child in value), set())
    return set()


class TskgFlowReadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def build(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        fixture = SecurityFlowObservationFixture.from_mapping(payload or self.raw_fixture)
        return build_security_flow_read_model(fixture)

    def test_projection_is_deterministic_and_strategy_free(self) -> None:
        projected = self.build()
        reordered = deepcopy(self.raw_fixture)
        reordered["observations"].reverse()
        projected_reordered = self.build(reordered)

        self.assertEqual(projected, projected_reordered)
        self.assertEqual(projected["schema_version"], "tskg-security-flow-read-model-v1")
        self.assertEqual(projected["formula_version"], "raw-only-v1")
        self.assertEqual(len(projected["items"]), 2)
        self.assertEqual(len(projected["canonical_hash"]), 64)
        self.assertFalse(PROHIBITED_FIELDS.intersection(all_keys(projected)))

    def test_stale_and_partial_states_propagate_without_zero_fill(self) -> None:
        partial = deepcopy(self.raw_fixture)
        partial["observations"] = [
            row
            for row in partial["observations"]
            if not (
                row["security_id"] == "security-3017-xtai"
                and row["investor_type"] == "DEALER"
            )
        ]
        projected = self.build(partial)
        item = query_security_flow_read_model(
            projected,
            security_id="security-3017-xtai",
            trade_date="2026-07-17",
        )

        self.assertIsNotNone(item)
        assert item is not None
        self.assertTrue(item["is_stale"])
        self.assertEqual(item["freshness"], "STALE")
        self.assertIn("missing investor types: DEALER", item["warnings"])
        self.assertNotIn("DEALER", [row["investor_type"] for row in item["observations"]])

    def test_query_returns_defensive_copy_and_none_for_missing(self) -> None:
        projected = self.build()
        first = query_security_flow_read_model(
            projected,
            security_id="security-2330-xtai",
            trade_date="2026-07-17",
        )
        self.assertIsNotNone(first)
        assert first is not None
        first["warnings"].append("mutated")
        second = query_security_flow_read_model(
            projected,
            security_id="security-2330-xtai",
            trade_date="2026-07-17",
        )
        assert second is not None
        self.assertNotIn("mutated", second["warnings"])
        self.assertIsNone(
            query_security_flow_read_model(
                projected,
                security_id="security-missing",
                trade_date="2026-07-17",
            )
        )

    def test_wrong_input_type_fails_loud(self) -> None:
        with self.assertRaises(TypeError):
            build_security_flow_read_model({})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
