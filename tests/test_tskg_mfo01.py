"""TSKG-MFO-01 synthetic SecurityFlowObservation 公開契約測試。"""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.tskg.flow_observation import (
    FlowObservationContractError,
    SecurityFlowObservationFixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    PROJECT_ROOT
    / "data"
    / "fixtures"
    / "tskg"
    / "security_flow_observations_v1.json"
)
DERIVED_OR_TRADING_FIELDS = {
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


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value), set())
    return set()


class TskgMfo01ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.repository = SecurityFlowObservationFixture.from_file(FIXTURE_PATH)

    def test_valid_fixture_summary_and_deterministic_order(self) -> None:
        summary = self.repository.summary()

        self.assertEqual(summary["fixture_version"], "security-flow-v1")
        self.assertEqual(
            summary["schema_version"], "tskg-security-flow-observation-v1"
        )
        self.assertEqual(summary["formula_version"], "raw-only-v1")
        self.assertEqual(summary["observation_count"], 8)
        self.assertEqual(summary["security_count"], 2)
        self.assertEqual(summary["stale_count"], 2)
        self.assertEqual(
            summary["investor_types"],
            ["ALL_INSTITUTIONAL", "DEALER", "FOREIGN", "INVESTMENT_TRUST"],
        )

        records = self.repository.observations()
        semantic_keys = [
            (row["trade_date"], row["security_id"], row["investor_type"])
            for row in records
        ]
        self.assertEqual(semantic_keys, sorted(semantic_keys))

    def test_semantic_key_lookup_returns_copy(self) -> None:
        record = self.repository.get(
            security_id="security-3017-xtai",
            trade_date="2026-07-17",
            investor_type="FOREIGN",
        )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["net_buy_value_1d"], 125000000)
        record["net_buy_value_1d"] = 0
        self.assertEqual(
            self.repository.get(
                security_id="security-3017-xtai",
                trade_date="2026-07-17",
                investor_type="FOREIGN",
            )["net_buy_value_1d"],
            125000000,
        )
        self.assertIsNone(
            self.repository.get(
                security_id="security-missing",
                trade_date="2026-07-17",
                investor_type="FOREIGN",
            )
        )

    def test_fixture_is_raw_only_and_contains_no_trading_fields(self) -> None:
        self.assertEqual(
            DERIVED_OR_TRADING_FIELDS.intersection(_all_keys(self.fixture)), set()
        )
        self.assertNotIn("relationship_claims", self.fixture)
        self.assertNotIn("theme_observations", self.fixture)

    def test_closed_schema_and_version_gate(self) -> None:
        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "missing top-level": lambda value: value.pop("evidence"),
            "extra top-level": lambda value: value.update({"unexpected": True}),
            "wrong fixture version": lambda value: value.update(
                {"fixture_version": "security-flow-v2"}
            ),
            "wrong schema version": lambda value: value.update(
                {"schema_version": "unknown"}
            ),
            "derived formula version": lambda value: value.update(
                {"formula_version": "momentum-v1"}
            ),
            "missing observation field": lambda value: value["observations"][0].pop(
                "currency"
            ),
            "extra observation field": lambda value: value["observations"][0].update(
                {"flow_acceleration": 1}
            ),
            "extra provenance field": lambda value: value["provenance"].update(
                {"owner": "unknown"}
            ),
            "extra evidence field": lambda value: value["evidence"][0].update(
                {"note": "unknown"}
            ),
        }
        self._assert_mutations_rejected(mutations)

    def test_identity_provenance_and_duplicate_gates(self) -> None:
        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "duplicate observation ID": lambda value: value["observations"][1].update(
                {"observation_id": value["observations"][0]["observation_id"]}
            ),
            "duplicate semantic key": lambda value: value["observations"][1].update(
                {
                    field: value["observations"][0][field]
                    for field in ("security_id", "trade_date", "investor_type")
                }
            ),
            "dangling source": lambda value: value["observations"][0].update(
                {"source_id": "source-missing"}
            ),
            "dangling evidence": lambda value: value["observations"][0].update(
                {"evidence_id": "evidence-missing"}
            ),
            "duplicate evidence": lambda value: value["evidence"].append(
                deepcopy(value["evidence"][0])
            ),
            "non-synthetic source": lambda value: value["provenance"].update(
                {"source_type": "PUBLIC_WEB"}
            ),
            "empty security ID": lambda value: value["observations"][0].update(
                {"security_id": " "}
            ),
        }
        self._assert_mutations_rejected(mutations)

    def test_value_date_time_and_freshness_gates(self) -> None:
        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "invalid trade date": lambda value: value["observations"][0].update(
                {"trade_date": "2026-02-30"}
            ),
            "timestamp instead of date": lambda value: value["observations"][0].update(
                {"trade_date": "2026-07-17T00:00:00Z"}
            ),
            "invalid investor type": lambda value: value["observations"][0].update(
                {"investor_type": "RETAIL"}
            ),
            "non-string investor type": lambda value: value["observations"][0].update(
                {"investor_type": ["FOREIGN"]}
            ),
            "wrong currency": lambda value: value["observations"][0].update(
                {"currency": "USD"}
            ),
            "float amount": lambda value: value["observations"][0].update(
                {"net_buy_value_1d": 1.5}
            ),
            "boolean amount": lambda value: value["observations"][0].update(
                {"net_buy_value_1d": True}
            ),
            "naive observed time": lambda value: value["observations"][0].update(
                {"observed_at": "2026-07-17T13:30:00"}
            ),
            "non-UTC retrieved time": lambda value: value["observations"][0].update(
                {"retrieved_at": "2026-07-17T13:31:00+08:00"}
            ),
            "retrieved before observed": lambda value: value["observations"][0].update(
                {"retrieved_at": "2026-07-17T13:29:59Z"}
            ),
            "invalid freshness": lambda value: value["observations"][0].update(
                {"freshness": "UNKNOWN"}
            ),
            "non-string freshness": lambda value: value["observations"][0].update(
                {"freshness": ["FRESH"]}
            ),
            "non-string evidence ID": lambda value: value["observations"][0].update(
                {"evidence_id": ["evidence-synthetic-security-flow-v1"]}
            ),
            "fresh marked stale": lambda value: value["observations"][0].update(
                {"freshness": "FRESH", "is_stale": True}
            ),
            "stale marked fresh": lambda value: value["observations"][0].update(
                {"freshness": "STALE", "is_stale": False}
            ),
            "non-boolean stale": lambda value: value["observations"][0].update(
                {"is_stale": 0}
            ),
        }
        self._assert_mutations_rejected(mutations)

    def test_timestamp_fields_require_rfc3339_utc_strings(self) -> None:
        for field in ("observed_at", "retrieved_at"):
            with self.subTest(field=field):
                malformed = deepcopy(self.fixture)
                malformed["observations"][0][field] = datetime(
                    2026, 7, 17, 13, 30, tzinfo=timezone.utc
                )
                with self.assertRaises(FlowObservationContractError):
                    SecurityFlowObservationFixture.from_mapping(malformed)

    def test_invalid_json_is_wrapped_with_decode_error_cause(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_path = Path(temporary_directory) / "invalid.json"
            fixture_path.write_text("{", encoding="utf-8")

            with self.assertRaises(FlowObservationContractError) as raised:
                SecurityFlowObservationFixture.from_file(fixture_path)

        self.assertIsInstance(raised.exception.__cause__, json.JSONDecodeError)

    def test_from_file_does_not_swallow_os_error(self) -> None:
        missing_path = PROJECT_ROOT / "does-not-exist-mfo01.json"

        with self.assertRaises(FileNotFoundError):
            SecurityFlowObservationFixture.from_file(missing_path)

    def test_prohibited_trading_field_fails_loud(self) -> None:
        for prohibited_field in sorted(DERIVED_OR_TRADING_FIELDS):
            with self.subTest(prohibited_field=prohibited_field):
                malformed = deepcopy(self.fixture)
                malformed["observations"][0][prohibited_field] = 0
                with self.assertRaises(FlowObservationContractError):
                    SecurityFlowObservationFixture.from_mapping(malformed)

    def _assert_mutations_rejected(
        self, mutations: dict[str, Callable[[dict[str, Any]], None]]
    ) -> None:
        for case_name, mutate in mutations.items():
            with self.subTest(case_name=case_name):
                malformed = deepcopy(self.fixture)
                mutate(malformed)
                with self.assertRaises(FlowObservationContractError):
                    SecurityFlowObservationFixture.from_mapping(malformed)


if __name__ == "__main__":
    unittest.main()
