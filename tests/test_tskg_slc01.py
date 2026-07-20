"""TSKG-SLC-01 離線 identity-to-company 公開行為測試。"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.tskg.identity import ResolutionStatus, normalize_alias
from app.tskg.repository import FixtureContractError, FixtureRepository
from app.tskg.router import create_tskg_router
from app.tskg.service import CompanyService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "tskg" / "identity_v1.json"
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
PROHIBITED_FIELDS = {
    "score",
    "weight",
    "prediction",
    "buy",
    "sell",
    "target",
    "stop",
}


def _canonical_checksum(payload: dict[str, Any]) -> str:
    canonical = deepcopy(payload)
    canonical.pop("request_id", None)
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value), set())
    return set()


def _semantic_key_tokens(key: str) -> set[str]:
    """把 snake/camel/kebab key 拆成可比對的語意 token。"""

    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", key)
    return {
        token.casefold()
        for token in re.split(r"[^A-Za-z0-9]+", camel_split)
        if token
    }


def _all_key_tokens(value: Any) -> set[str]:
    return {
        token
        for key in _all_keys(value)
        for token in _semantic_key_tokens(key)
    }


class TskgSlc01PublicBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = FixtureRepository.from_file(FIXTURE_PATH)
        cls.resolver = cls.repository.create_resolver()
        cls.service = CompanyService(cls.repository)

        app = FastAPI()
        app.include_router(
            create_tskg_router(
                cls.service,
                request_id_factory=lambda: "req-slc01-test",
            )
        )
        cls.client = TestClient(app)

    def test_fixture_contract_and_counts(self) -> None:
        summary = self.repository.summary()

        self.assertEqual(summary["fixture_version"], "identity-v1")
        self.assertEqual(summary["schema_version"], "tskg-identity-fixture-v1")
        self.assertEqual(summary["normalizer_version"], "nfkc-casefold-v1")
        self.assertGreaterEqual(summary["entity_count"], 12)
        self.assertGreaterEqual(summary["organization_count"], 1)
        self.assertGreaterEqual(summary["security_count"], 1)
        self.assertGreaterEqual(summary["alias_collision_count"], 1)

    def test_fixture_closed_schema_rejects_malformed_records(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        def remove_top_level(value: dict[str, Any]) -> None:
            value.pop("provenance")

        def add_top_level(value: dict[str, Any]) -> None:
            value["unexpected"] = True

        def remove_organization_field(value: dict[str, Any]) -> None:
            value["entities"][0].pop("status")

        def add_organization_field(value: dict[str, Any]) -> None:
            value["entities"][0]["unexpected"] = True

        def invalid_organization_kind(value: dict[str, Any]) -> None:
            value["entities"][0]["organization_kind"] = "UNKNOWN"

        def invalid_organization_status(value: dict[str, Any]) -> None:
            value["entities"][0]["status"] = "UNKNOWN"

        def missing_security_field(value: dict[str, Any]) -> None:
            value["entities"][9].pop("issuer_id")

        def extra_security_field(value: dict[str, Any]) -> None:
            value["entities"][9]["unexpected"] = True

        def invalid_security_type(value: dict[str, Any]) -> None:
            value["entities"][9]["security_type"] = "TOKEN"

        def lowercase_market(value: dict[str, Any]) -> None:
            value["entities"][9]["market"] = "xtai"

        def empty_code(value: dict[str, Any]) -> None:
            value["entities"][9]["code"] = ""

        def invalid_code(value: dict[str, Any]) -> None:
            value["entities"][9]["code"] = "30-17"

        def whitespace_entity_id(value: dict[str, Any]) -> None:
            value["entities"][0]["entity_id"] = " "

        def missing_provenance_field(value: dict[str, Any]) -> None:
            value["provenance"].pop("description")

        def extra_provenance_field(value: dict[str, Any]) -> None:
            value["provenance"]["unexpected"] = True

        def invalid_provenance_type(value: dict[str, Any]) -> None:
            value["provenance"]["source_type"] = "PUBLIC_WEB"

        def missing_evidence_field(value: dict[str, Any]) -> None:
            value["identity_evidence"][0].pop("locator")

        def extra_evidence_field(value: dict[str, Any]) -> None:
            value["identity_evidence"][0]["unexpected"] = True

        def dangling_evidence_source(value: dict[str, Any]) -> None:
            value["identity_evidence"][0]["source_id"] = "source-missing"

        def duplicate_evidence(value: dict[str, Any]) -> None:
            value["identity_evidence"].append(
                deepcopy(value["identity_evidence"][0])
            )

        def missing_alias_field(value: dict[str, Any]) -> None:
            value["aliases"][0].pop("evidence_id")

        def extra_alias_field(value: dict[str, Any]) -> None:
            value["aliases"][0]["unexpected"] = True

        def dangling_alias_source(value: dict[str, Any]) -> None:
            value["aliases"][0]["source_id"] = "source-missing"

        def dangling_alias_evidence(value: dict[str, Any]) -> None:
            value["aliases"][0]["evidence_id"] = "evidence-missing"

        def whitespace_alias(value: dict[str, Any]) -> None:
            value["aliases"][0]["raw_alias"] = " "
            value["aliases"][0]["normalized_alias"] = ""

        def duplicate_alias(value: dict[str, Any]) -> None:
            value["aliases"].append(deepcopy(value["aliases"][0]))

        def duplicate_entity(value: dict[str, Any]) -> None:
            value["entities"].append(deepcopy(value["entities"][0]))

        mutations = {
            "missing top-level field": remove_top_level,
            "unknown top-level field": add_top_level,
            "missing Organization field": remove_organization_field,
            "unknown Organization field": add_organization_field,
            "invalid organization kind": invalid_organization_kind,
            "invalid organization status": invalid_organization_status,
            "missing Security field": missing_security_field,
            "unknown Security field": extra_security_field,
            "invalid security type": invalid_security_type,
            "lowercase market": lowercase_market,
            "empty code": empty_code,
            "invalid code syntax": invalid_code,
            "whitespace entity ID": whitespace_entity_id,
            "missing provenance field": missing_provenance_field,
            "unknown provenance field": extra_provenance_field,
            "invalid provenance type": invalid_provenance_type,
            "missing evidence field": missing_evidence_field,
            "unknown evidence field": extra_evidence_field,
            "dangling evidence source": dangling_evidence_source,
            "duplicate evidence": duplicate_evidence,
            "missing alias field": missing_alias_field,
            "unknown alias field": extra_alias_field,
            "dangling alias source": dangling_alias_source,
            "dangling alias evidence": dangling_alias_evidence,
            "whitespace alias": whitespace_alias,
            "duplicate alias": duplicate_alias,
            "duplicate entity": duplicate_entity,
        }

        for case_name, mutate in mutations.items():
            with self.subTest(case_name=case_name):
                malformed = deepcopy(fixture)
                mutate(malformed)
                with self.assertRaises(FixtureContractError):
                    FixtureRepository.from_mapping(malformed)

    def test_fixture_rejects_malformed_temporal_endpoints(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        invalid_intervals = (
            {"start": {}, "end": {"kind": "UNBOUNDED"}},
            {
                "start": {"kind": "KNOWN", "inclusive": True},
                "end": {"kind": "UNBOUNDED"},
            },
            {
                "start": {
                    "kind": "KNOWN",
                    "timestamp": "2026-01-01T00:00:00",
                    "inclusive": True,
                },
                "end": {"kind": "UNBOUNDED"},
            },
            {
                "start": {"kind": "UNBOUNDED", "timestamp": "2026-01-01T00:00:00Z"},
                "end": {"kind": "UNBOUNDED"},
            },
            {
                "start": {"kind": "UNKNOWN", "inclusive": True},
                "end": {"kind": "UNBOUNDED"},
            },
            {
                "start": {
                    "kind": "KNOWN",
                    "timestamp": "2027-01-01T00:00:00Z",
                    "inclusive": True,
                },
                "end": {
                    "kind": "KNOWN",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "inclusive": True,
                },
            },
            {
                "start": {
                    "kind": "KNOWN",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "inclusive": False,
                },
                "end": {
                    "kind": "KNOWN",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "inclusive": True,
                },
            },
        )

        for interval in invalid_intervals:
            with self.subTest(interval=interval):
                malformed = deepcopy(fixture)
                malformed["entities"][9]["valid_time"] = interval
                with self.assertRaises(FixtureContractError):
                    FixtureRepository.from_mapping(malformed)

    def test_security_resolution_respects_current_and_explicit_instant(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        original = fixture["entities"][9]
        original["valid_time"] = {
            "start": {"kind": "UNBOUNDED"},
            "end": {
                "kind": "KNOWN",
                "timestamp": "2020-01-01T00:00:00Z",
                "inclusive": False,
            },
        }
        successor = deepcopy(original)
        successor["entity_id"] = "sec-fixture-3017-xtai-successor"
        successor["valid_time"] = {
            "start": {
                "kind": "KNOWN",
                "timestamp": "2020-01-01T00:00:00Z",
                "inclusive": True,
            },
            "end": {"kind": "UNBOUNDED"},
        }
        fixture["entities"].append(successor)
        resolver = FixtureRepository.from_mapping(fixture).create_resolver(
            clock=lambda: datetime(2026, 7, 18, tzinfo=UTC)
        )

        current = resolver.resolve_security("3017", market="XTAI")
        historical = resolver.resolve_security(
            "3017",
            market="XTAI",
            effective_at="2019-12-31T23:59:59Z",
        )

        self.assertEqual(current.status, ResolutionStatus.RESOLVED)
        self.assertEqual(current.entity["entity_id"], successor["entity_id"])
        self.assertEqual(historical.status, ResolutionStatus.RESOLVED)
        self.assertEqual(historical.entity["entity_id"], original["entity_id"])

    def test_security_resolution_rejects_expired_and_future_records(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixed_now = datetime(2026, 7, 18, tzinfo=UTC)

        expired = deepcopy(fixture)
        expired["entities"][9]["valid_time"] = {
            "start": {"kind": "UNBOUNDED"},
            "end": {
                "kind": "KNOWN",
                "timestamp": "2011-01-01T00:00:00Z",
                "inclusive": False,
            },
        }
        future = deepcopy(fixture)
        future["entities"][9]["valid_time"] = {
            "start": {
                "kind": "KNOWN",
                "timestamp": "2030-01-01T00:00:00Z",
                "inclusive": True,
            },
            "end": {"kind": "UNBOUNDED"},
        }

        for case_name, candidate in (("expired", expired), ("future", future)):
            with self.subTest(case_name=case_name):
                result = FixtureRepository.from_mapping(candidate).create_resolver(
                    clock=lambda: fixed_now
                ).resolve_security("3017")
                self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)

    def test_security_interval_overlap_and_boundaries_fail_closed(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        first = fixture["entities"][9]
        first["valid_time"] = {
            "start": {"kind": "UNBOUNDED"},
            "end": {
                "kind": "KNOWN",
                "timestamp": "2020-01-01T00:00:00Z",
                "inclusive": True,
            },
        }
        second = deepcopy(first)
        second["entity_id"] = "sec-fixture-3017-xtai-reuse"
        second["valid_time"] = {
            "start": {
                "kind": "KNOWN",
                "timestamp": "2020-01-01T00:00:00Z",
                "inclusive": True,
            },
            "end": {"kind": "UNBOUNDED"},
        }
        overlapping = deepcopy(fixture)
        overlapping["entities"].append(second)
        with self.assertRaises(FixtureContractError):
            FixtureRepository.from_mapping(overlapping)

        first["valid_time"]["end"]["inclusive"] = False
        non_overlapping = deepcopy(fixture)
        non_overlapping["entities"].append(second)
        repository = FixtureRepository.from_mapping(non_overlapping)
        before = repository.create_resolver().resolve_security(
            "3017", effective_at="2019-12-31T23:59:59Z"
        )
        boundary = repository.create_resolver().resolve_security(
            "3017", effective_at="2020-01-01T00:00:00Z"
        )
        self.assertEqual(before.entity["entity_id"], first["entity_id"])
        self.assertEqual(boundary.entity["entity_id"], second["entity_id"])

    def test_unknown_temporal_endpoint_is_not_treated_as_expired(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture["entities"][9]["valid_time"] = {
            "start": {"kind": "UNKNOWN"},
            "end": {"kind": "UNKNOWN"},
        }
        result = FixtureRepository.from_mapping(fixture).create_resolver(
            clock=lambda: datetime(2026, 7, 18, tzinfo=UTC)
        ).resolve_security("3017")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)

    def test_multiple_temporally_possible_reuses_are_ambiguous(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        first = fixture["entities"][9]
        first["valid_time"] = {
            "start": {"kind": "UNKNOWN"},
            "end": {"kind": "UNKNOWN"},
        }
        second = deepcopy(first)
        second["entity_id"] = "sec-fixture-3017-xtai-uncertain-reuse"
        fixture["entities"].append(second)

        result = FixtureRepository.from_mapping(fixture).create_resolver(
            clock=lambda: datetime(2026, 7, 18, tzinfo=UTC)
        ).resolve_security("3017", market="XTAI")

        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertEqual(result.candidate_ids, tuple(sorted(result.candidate_ids)))

    def test_company_api_supports_explicit_as_of_and_injected_clock(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        original = fixture["entities"][9]
        original["valid_time"] = {
            "start": {"kind": "UNBOUNDED"},
            "end": {
                "kind": "KNOWN",
                "timestamp": "2020-01-01T00:00:00Z",
                "inclusive": False,
            },
        }
        successor = deepcopy(original)
        successor["entity_id"] = "sec-fixture-3017-xtai-api-successor"
        successor["valid_time"] = {
            "start": {
                "kind": "KNOWN",
                "timestamp": "2020-01-01T00:00:00Z",
                "inclusive": True,
            },
            "end": {"kind": "UNBOUNDED"},
        }
        fixture["entities"].append(successor)
        service = CompanyService(
            FixtureRepository.from_mapping(fixture),
            clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        )
        app = FastAPI()
        app.include_router(
            create_tskg_router(service, request_id_factory=lambda: "req-as-of")
        )
        client = TestClient(app)

        current = client.get("/v1/company/3017")
        historical = client.get(
            "/v1/company/3017", params={"as_of": "2019-12-31T23:59:59Z"}
        )
        invalid = client.get("/v1/company/3017", params={"as_of": "2019-12-31"})

        self.assertEqual(current.status_code, 200)
        self.assertEqual(
            current.json()["data"]["company"]["security"]["entity_id"],
            successor["entity_id"],
        )
        self.assertEqual(historical.status_code, 200)
        self.assertEqual(
            historical.json()["data"]["company"]["security"]["entity_id"],
            original["entity_id"],
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "INVALID_ARGUMENT")

    def test_alias_normalization_contract(self) -> None:
        self.assertEqual(normalize_alias("  Ｎｖｉｄｉａ\tInc  "), "nvidia inc")

    def test_expected_alias_groups_resolve_to_canonical_organizations(self) -> None:
        groups = (
            (("NVIDIA", "NVDA", "Nvidia"), "org-fixture-nvidia"),
            (("Tesla", "TESLA"), "org-fixture-tesla"),
            (("Meta", "Facebook"), "org-fixture-meta"),
        )

        for aliases, expected_entity_id in groups:
            with self.subTest(aliases=aliases):
                resolved_ids = {
                    self.resolver.resolve_alias(alias).entity["entity_id"]
                    for alias in aliases
                }
                self.assertEqual(resolved_ids, {expected_entity_id})

    def test_alias_collision_is_structured_and_not_auto_merged(self) -> None:
        result = self.resolver.resolve_alias("Global Labs")

        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(result.entity)
        self.assertGreaterEqual(len(result.candidate_ids), 2)
        self.assertEqual(result.candidate_ids, tuple(sorted(result.candidate_ids)))

    def test_security_3017_preserves_string_code_and_follows_issuer_id(self) -> None:
        result = self.resolver.resolve_security("3017")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.entity["entity_type"], "Security")
        self.assertEqual(result.entity["code"], "3017")
        self.assertIsInstance(result.entity["code"], str)
        company = self.service.get_company("3017", request_id="req-service")
        self.assertEqual(
            company["data"]["company"]["entity_id"],
            result.entity["issuer_id"],
        )

    def test_security_code_preserves_leading_zeroes(self) -> None:
        result = self.resolver.resolve_security("0123", market="XTAI")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.entity["code"], "0123")

    def test_market_ambiguity_and_market_specific_resolution(self) -> None:
        ambiguous = self.resolver.resolve_security("7777")
        unique = self.resolver.resolve_security("7777", market="XTAI")

        self.assertEqual(ambiguous.status, ResolutionStatus.AMBIGUOUS)
        self.assertEqual(unique.status, ResolutionStatus.RESOLVED)
        self.assertEqual(unique.entity["market"], "XTAI")

    def test_company_api_happy_path_has_envelope_and_empty_sections(self) -> None:
        response = self.client.get("/v1/company/3017")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload),
            {"request_id", "data", "freshness", "provenance_summary", "warnings"},
        )
        self.assertEqual(payload["request_id"], "req-slc01-test")
        self.assertEqual(payload["data"]["company"]["security"]["code"], "3017")
        self.assertTrue(payload["provenance_summary"]["synthetic_fixture"])
        self.assertFalse(payload["freshness"]["is_stale"])
        for section_name in RELATION_SECTIONS:
            with self.subTest(section_name=section_name):
                self.assertEqual(
                    payload["data"][section_name],
                    {"items": [], "next_cursor": None},
                )

    def test_company_api_missing_invalid_and_ambiguous_errors_are_stable(self) -> None:
        cases = (
            ("/v1/company/9999", 404, "ENTITY_NOT_FOUND"),
            ("/v1/company/30-17", 400, "INVALID_ARGUMENT"),
            ("/v1/company/7777", 409, "AMBIGUOUS_ENTITY"),
        )

        for path, status_code, error_code in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(
                    set(response.json()["error"]),
                    {"code", "message", "request_id", "details", "retryable"},
                )
                self.assertEqual(response.json()["error"]["code"], error_code)
                self.assertFalse(response.json()["error"]["retryable"])

    def test_company_api_market_selects_unique_security(self) -> None:
        response = self.client.get("/v1/company/7777", params={"market": "XOTC"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["company"]["security"]["market"],
            "XOTC",
        )

    def test_deterministic_reordered_fixture_produces_same_checksum(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        reordered = deepcopy(fixture)
        reordered["entities"] = list(reversed(reordered["entities"]))
        reordered["aliases"] = list(reversed(reordered["aliases"]))
        reversed_repository = FixtureRepository.from_mapping(reordered)

        first = self.service.get_company("3017", request_id="req-first")
        second = CompanyService(reversed_repository).get_company(
            "3017", request_id="req-second"
        )
        self.assertEqual(_canonical_checksum(first), _canonical_checksum(second))

    def test_existing_api_import_isolated_from_standalone_router(self) -> None:
        from app.api.main import app as existing_app

        paths = existing_app.openapi()["paths"]
        self.assertNotIn("/v1/company/{stock_id}", paths)

    def test_response_contains_no_trading_or_model_fields(self) -> None:
        payload = self.client.get("/v1/company/3017").json()

        self.assertTrue(PROHIBITED_FIELDS.isdisjoint(_all_key_tokens(payload)))

    def test_prohibited_field_scanner_detects_compound_nested_keys(self) -> None:
        compound_keys = (
            "prediction_score",
            "target_price",
            "buy_signal",
            "stop_loss",
            "targetPrice",
            "buy-signal",
        )

        for key in compound_keys:
            with self.subTest(key=key):
                payload = {"outer": [{"inner": {key: 1}}]}
                self.assertFalse(PROHIBITED_FIELDS.isdisjoint(_all_key_tokens(payload)))


if __name__ == "__main__":
    unittest.main()
