"""TSKG-SLC-01 離線 identity-to-company 公開行為測試。"""

from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.tskg.identity import ResolutionStatus, normalize_alias
from app.tskg.repository import FixtureRepository
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

        self.assertTrue(PROHIBITED_FIELDS.isdisjoint(_all_keys(payload)))


if __name__ == "__main__":
    unittest.main()
