"""TSKG-SRC-01 離線 Source Gate 公開行為測試。"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from app.tskg.source_policy import (
    SourcePolicyContractError,
    SourcePolicyRegistry,
    preflight_source,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "tskg" / "source_policy_v1.json"
FIXED_AS_OF = "2026-07-18T00:00:00Z"


class ReaderSpy:
    """只記錄 invocation，不執行任何 I/O。"""

    def __init__(self, result: Any = None) -> None:
        self.calls = 0
        self.paths: list[str] = []
        self.result = {"synthetic": True} if result is None else result

    def __call__(self, path: str) -> Any:
        self.calls += 1
        self.paths.append(path)
        return self.result


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _approved_policy(payload: dict[str, Any]) -> dict[str, Any]:
    return next(
        policy
        for policy in payload["policies"]
        if policy["decision_status"] == "APPROVED"
    )


def _run(
    registry: SourcePolicyRegistry,
    reader: Callable[[str], Any],
    **overrides: Any,
) -> dict[str, Any]:
    request = {
        "source_id": "source-synthetic-approved",
        "method": "GET",
        "path": "/synthetic/v1/records/item-1",
        "media_type": "application/json",
        "as_of": FIXED_AS_OF,
        "reader": reader,
        "requested_rate": 1,
        "requested_concurrency": 1,
    }
    request.update(overrides)
    return preflight_source(registry, **request)


class TskgSrc01PublicBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = SourcePolicyRegistry.from_file(FIXTURE_PATH)

    def test_fixture_is_versioned_synthetic_and_public_is_never_approved(self) -> None:
        summary = self.registry.summary()

        self.assertEqual(summary["schema_version"], "tskg-source-policy-v1")
        self.assertEqual(summary["registry_version"], "source-policy-fixture-v1")
        self.assertEqual(summary["policy_count"], 3)
        self.assertEqual(summary["approved_synthetic_count"], 1)
        self.assertEqual(summary["approved_public_count"], 0)
        self.assertRegex(self.registry.checksum, r"^[0-9a-f]{64}$")

    def test_registry_and_policy_are_closed_shapes(self) -> None:
        payload = _fixture()

        for malformed_root in (None, [], "registry"):
            with self.subTest(malformed_root=malformed_root):
                with self.assertRaises(SourcePolicyContractError):
                    SourcePolicyRegistry.from_mapping(malformed_root)

        for field in payload:
            with self.subTest(missing_top_level_field=field):
                malformed = deepcopy(payload)
                malformed.pop(field)
                with self.assertRaises(SourcePolicyContractError):
                    SourcePolicyRegistry.from_mapping(malformed)

        for field in _approved_policy(payload):
            with self.subTest(missing_policy_field=field):
                malformed = deepcopy(payload)
                _approved_policy(malformed).pop(field)
                with self.assertRaises(SourcePolicyContractError):
                    SourcePolicyRegistry.from_mapping(malformed)

        mutations = {
            "unknown top-level field": lambda value: value.update(unexpected=True),
            "unknown policy field": lambda value: value["policies"][0].update(
                unexpected=True
            ),
        }
        for case_name, mutate in mutations.items():
            with self.subTest(case_name=case_name):
                malformed = deepcopy(payload)
                mutate(malformed)
                with self.assertRaises(SourcePolicyContractError):
                    SourcePolicyRegistry.from_mapping(malformed)

    def test_registry_rejects_enum_type_timestamp_and_bounded_numeric_errors(
        self,
    ) -> None:
        payload = _fixture()

        def mutate(field: str, value: Any) -> dict[str, Any]:
            malformed = deepcopy(payload)
            _approved_policy(malformed)[field] = value
            return malformed

        invalid_values = (
            ("source_class", "PRIVATE"),
            ("decision_status", "PENDING"),
            ("terms_decision", "UNKNOWN"),
            ("legal_basis", "UNKNOWN"),
            ("robots_decision", "UNKNOWN"),
            ("reviewed_at", "2026-07-18"),
            ("expires_at", "2027-07-18T00:00:00+08:00"),
            ("rate_limit", 0),
            ("rate_limit", 1001),
            ("concurrency_limit", True),
            ("concurrency_limit", 101),
            ("allowed_methods", "GET"),
            ("decision_evidence", []),
        )
        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                with self.assertRaises(SourcePolicyContractError):
                    SourcePolicyRegistry.from_mapping(mutate(field, value))

    def test_registry_rejects_empty_governance_decisions_before_reader_exists(
        self,
    ) -> None:
        governance_fields = (
            "publisher",
            "owner",
            "terms_decision",
            "legal_basis",
            "robots_decision",
            "authentication_constraints",
            "user_agent",
            "contact",
            "raw_retention",
            "snippet_retention",
            "metadata_retention",
            "redaction_policy",
            "deletion_policy",
            "redistribution_policy",
        )
        for field in governance_fields:
            with self.subTest(field=field):
                malformed = _fixture()
                _approved_policy(malformed)[field] = " "
                spy = ReaderSpy()
                with self.assertRaises(SourcePolicyContractError):
                    SourcePolicyRegistry.from_mapping(malformed)
                self.assertEqual(spy.calls, 0)

    def test_registry_rejects_duplicate_policy_and_source_ids(self) -> None:
        for duplicate_field in ("policy_id", "source_id"):
            with self.subTest(duplicate_field=duplicate_field):
                malformed = _fixture()
                malformed["policies"][1][duplicate_field] = malformed["policies"][0][
                    duplicate_field
                ]
                with self.assertRaises(SourcePolicyContractError):
                    SourcePolicyRegistry.from_mapping(malformed)

    def test_generic_mapping_cannot_grant_public_approval(self) -> None:
        payload = _fixture()
        policy = _approved_policy(payload)
        policy.update(
            policy_id="policy-public-manufactured-v1",
            source_id="source-public-manufactured",
            source_class="PUBLIC",
        )
        spy = ReaderSpy()

        with self.assertRaises(SourcePolicyContractError):
            SourcePolicyRegistry.from_mapping(payload)

        self.assertEqual(spy.calls, 0)

    def test_file_loader_rejects_duplicate_json_members_recursively(self) -> None:
        fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
        duplicate_documents = {
            "registry": fixture_text.replace(
                '  "schema_version": "tskg-source-policy-v1",',
                '  "schema_version": "shadowed",\n'
                '  "schema_version": "tskg-source-policy-v1",',
                1,
            ),
            "policy": fixture_text.replace(
                '      "source_class": "SYNTHETIC",',
                '      "source_class": "PUBLIC",\n'
                '      "source_class": "SYNTHETIC",',
                1,
            ),
            "nested_object": fixture_text.replace(
                '      "authentication_constraints": "OFFLINE_CALLBACK_ONLY",',
                '      "authentication_constraints": '
                '{"mode": "PUBLIC", "mode": "OFFLINE_CALLBACK_ONLY"},',
                1,
            ),
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            for case_name, document in duplicate_documents.items():
                with self.subTest(case_name=case_name):
                    duplicate_path = Path(temporary_directory) / f"{case_name}.json"
                    duplicate_path.write_text(document, encoding="utf-8")
                    with self.assertRaises(SourcePolicyContractError):
                        SourcePolicyRegistry.from_file(duplicate_path)

    def test_checksum_is_deterministic_after_input_reordering(self) -> None:
        payload = _fixture()
        reordered = deepcopy(payload)
        reordered["policies"] = list(reversed(reordered["policies"]))
        for policy in reordered["policies"]:
            for field in (
                "allowed_methods",
                "allowed_paths",
                "allowed_media_types",
                "decision_evidence",
            ):
                policy[field] = list(reversed(policy[field]))

        self.assertEqual(
            SourcePolicyRegistry.from_mapping(payload).checksum,
            SourcePolicyRegistry.from_mapping(reordered).checksum,
        )

    def test_approved_request_calls_reader_once_with_stable_receipt(self) -> None:
        first_spy = ReaderSpy({"batch": "synthetic-1"})
        second_spy = ReaderSpy({"batch": "synthetic-1"})

        first = _run(self.registry, first_spy)
        second = _run(self.registry, second_spy)

        self.assertTrue(first["ok"])
        self.assertEqual(first_spy.calls, 1)
        self.assertEqual(second_spy.calls, 1)
        self.assertEqual(first_spy.paths, ["/synthetic/v1/records/item-1"])
        self.assertEqual(second_spy.paths, ["/synthetic/v1/records/item-1"])
        self.assertEqual(first["reader_result"], {"batch": "synthetic-1"})
        self.assertEqual(first["receipt"], second["receipt"])
        self.assertEqual(
            set(first["receipt"]),
            {
                "receipt_id",
                "policy_id",
                "policy_checksum",
                "source_id",
                "method",
                "path",
                "media_type",
                "as_of",
                "requested_rate",
                "requested_concurrency",
            },
        )
        self.assertEqual(first["receipt"]["policy_checksum"], self.registry.checksum)

    def test_robots_allow_does_not_replace_terms_or_legal_approval(self) -> None:
        for field in ("terms_decision", "legal_basis"):
            with self.subTest(field=field):
                payload = _fixture()
                _approved_policy(payload)[field] = "BLOCKED"
                registry = SourcePolicyRegistry.from_mapping(payload)
                spy = ReaderSpy()

                result = _run(registry, spy)

                self.assertEqual(result["error"]["code"], "GOVERNANCE_INCOMPLETE")
                self.assertEqual(spy.calls, 0)

    def test_blocked_expired_and_unknown_sources_never_call_reader(self) -> None:
        cases = (
            ("source-public-blocked", "SOURCE_BLOCKED"),
            ("source-public-expired", "POLICY_EXPIRED"),
            ("source-missing", "SOURCE_UNKNOWN"),
        )
        for source_id, expected_code in cases:
            with self.subTest(source_id=source_id):
                spy = ReaderSpy()
                result = _run(self.registry, spy, source_id=source_id)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], expected_code)
                self.assertEqual(spy.calls, 0)
                self.assertEqual(
                    set(result),
                    {"ok", "error"},
                )
                self.assertEqual(
                    set(result["error"]),
                    {
                        "code",
                        "message",
                        "source_id",
                        "policy_id",
                        "policy_checksum",
                    },
                )

    def test_approval_time_window_fails_closed(self) -> None:
        cases = (
            ("2025-12-31T23:59:59Z", "POLICY_NOT_YET_EFFECTIVE"),
            ("2027-01-01T00:00:00Z", "POLICY_EXPIRED"),
            ("not-a-timestamp", "INVALID_REQUEST"),
        )
        for as_of, expected_code in cases:
            with self.subTest(as_of=as_of):
                spy = ReaderSpy()
                result = _run(self.registry, spy, as_of=as_of)
                self.assertEqual(result["error"]["code"], expected_code)
                self.assertEqual(spy.calls, 0)

    def test_request_boundaries_are_checked_before_reader(self) -> None:
        cases = (
            ({"method": "POST"}, "METHOD_NOT_ALLOWED"),
            ({"path": "/synthetic/v2/records/item-1"}, "PATH_NOT_ALLOWED"),
            ({"media_type": "text/html"}, "MEDIA_TYPE_NOT_ALLOWED"),
            ({"requested_rate": 11}, "RATE_LIMIT_EXCEEDED"),
            ({"requested_concurrency": 3}, "CONCURRENCY_LIMIT_EXCEEDED"),
            ({"requested_rate": 0}, "INVALID_REQUEST"),
            ({"requested_concurrency": True}, "INVALID_REQUEST"),
        )
        for overrides, expected_code in cases:
            with self.subTest(overrides=overrides):
                spy = ReaderSpy()
                result = _run(self.registry, spy, **overrides)
                self.assertEqual(result["error"]["code"], expected_code)
                self.assertEqual(spy.calls, 0)

    def test_unsafe_and_prefix_confused_paths_fail_closed(self) -> None:
        paths = (
            "/synthetic/v1/records/../secret",
            "/synthetic/v1/recordsevil/item-1",
            "/synthetic/v1/records/%2e%2e/secret",
            "//synthetic/v1/records/item-1",
            "/synthetic/v1/records/item-1?query=1",
        )
        for path in paths:
            with self.subTest(path=path):
                spy = ReaderSpy()
                result = _run(self.registry, spy, path=path)
                self.assertIn(
                    result["error"]["code"],
                    {"INVALID_REQUEST", "PATH_NOT_ALLOWED"},
                )
                self.assertEqual(spy.calls, 0)

    def test_unicode_compatibility_and_control_paths_fail_closed(self) -> None:
        unsafe_paths = (
            "/synthetic/v1/records/．．／secret",
            "/synthetic/v1/records/\uff0esecret",
            "/synthetic/v1/records/secret\uff0fchild",
            "/synthetic/v1/records/secret\u0000child",
            "/synthetic/v1/records/secret\u001fchild",
            "/synthetic/v1/records/secret\u007fchild",
            "/synthetic/v1/records/%2Fsecret",
            "/synthetic/v1/records/%2fsecret",
            "/synthetic/v1/records/%252e%252e/secret",
            "https://example.invalid/synthetic/v1/records/item-1",
            "/synthetic/v1/records/item-1#fragment",
            "/synthetic/v1/records/item-1\\child",
        )
        for path in unsafe_paths:
            with self.subTest(path=path):
                spy = ReaderSpy()

                result = _run(self.registry, spy, path=path)

                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "INVALID_REQUEST")
                self.assertEqual(spy.calls, 0)

    def test_public_contract_is_exported_without_runtime_side_effects(self) -> None:
        from app import tskg

        self.assertIs(tskg.SourcePolicyContractError, SourcePolicyContractError)
        self.assertIs(tskg.SourcePolicyRegistry, SourcePolicyRegistry)
        self.assertIs(tskg.preflight_source, preflight_source)

    def test_fixture_contains_no_url_or_real_source_bytes(self) -> None:
        text = FIXTURE_PATH.read_text(encoding="utf-8")

        self.assertIsNone(re.search(r"https?://|www\.", text, flags=re.IGNORECASE))
        self.assertNotIn("raw_bytes", text)
        self.assertNotIn("html", text.casefold())
        self.assertNotIn("pdf", text.casefold())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
