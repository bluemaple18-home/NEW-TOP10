from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.verify_daily_research_quota import build_payload
from scripts.verify_closed_regime_runtime import build_receipt, verify_receipt
from scripts.fog_runtime_time_authority import build_run_context
from tests.test_fog_closed_regime_runtime import _runtime_fixture


class DailyResearchQuotaVerifierTest(unittest.TestCase):
    def build_artifact(self, topic_count: int, quota: int = 5) -> Path:
        directory = Path(tempfile.mkdtemp())
        artifact = directory / "quota.json"
        topic_runs = [
            {
                "topic": {"topic_id": f"topic-{index}"},
                "status": "OK",
                "outcome": {"decision": "REJECTED_BY_STRATEGY_MATRIX", "promotion_allowed": False},
                "steps": [],
            }
            for index in range(topic_count)
        ]
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "autonomous-research-run.v1",
                    "status": "OK",
                    "contract": {
                        "research_only": True,
                        "does_not_train_model": True,
                        "does_not_write_models_latest_lgbm": True,
                        "does_not_change_risk_adjusted_score": True,
                        "does_not_change_production_ranking": True,
                        "production_promotion_allowed": False,
                    },
                    "inputs": {"execute": True, "from_queue": True, "execute_topic_count": quota},
                    "selected_topics": [run["topic"] for run in topic_runs],
                    "topic_runs": topic_runs,
                    "outcome": {"decision": "NO_EXECUTABLE_TOPIC" if not topic_runs else "REJECTED_BY_STRATEGY_MATRIX"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.addCleanup(shutil.rmtree, directory)
        return artifact

    def test_zero_topics_is_partial_no_more_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "quota.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "autonomous-research-run.v1",
                        "status": "OK",
                        "contract": {
                            "research_only": True,
                            "does_not_train_model": True,
                            "does_not_write_models_latest_lgbm": True,
                            "does_not_change_risk_adjusted_score": True,
                            "does_not_change_production_ranking": True,
                            "production_promotion_allowed": False,
                        },
                        "inputs": {"execute": True, "from_queue": True, "execute_topic_count": 5},
                        "selected_topics": [],
                        "topic_runs": [],
                        "outcome": {"decision": "NO_EXECUTABLE_TOPIC", "promotion_allowed": False},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_payload(artifact, min_quota=5)

        self.assertEqual(payload["status"], "PARTIAL_NO_MORE_WORK")
        self.assertEqual(payload["summary"]["research_value_status"], "NO_MORE_EXECUTABLE_TOPIC")

    def test_topic_supply_exhausted_has_stable_research_value_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "quota.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "autonomous-research-run.v1",
                        "status": "OK",
                        "contract": {
                            "research_only": True,
                            "does_not_train_model": True,
                            "does_not_write_models_latest_lgbm": True,
                            "does_not_change_risk_adjusted_score": True,
                            "does_not_change_production_ranking": True,
                            "production_promotion_allowed": False,
                        },
                        "inputs": {"execute": True, "from_queue": False, "execute_topic_count": 5},
                        "selected_topics": [],
                        "topic_runs": [],
                        "outcome": {
                            "decision": "TOPIC_SUPPLY_EXHAUSTED",
                            "promotion_allowed": False,
                            "topic_supply": {"status": "TOPIC_SUPPLY_EXHAUSTED"},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_payload(artifact, min_quota=5)

        self.assertEqual(payload["status"], "PARTIAL_NO_MORE_WORK")
        self.assertEqual(payload["summary"]["failed_count"], 0)
        self.assertEqual(payload["summary"]["research_value_status"], "SUPPLY_EXHAUSTED")

    def test_attempt_budget_exceeded_is_retryable_not_no_more_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "quota.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "autonomous-research-run.v1",
                        "status": "OK",
                        "contract": {
                            "research_only": True,
                            "does_not_train_model": True,
                            "does_not_write_models_latest_lgbm": True,
                            "does_not_change_risk_adjusted_score": True,
                            "does_not_change_production_ranking": True,
                            "production_promotion_allowed": False,
                        },
                        "inputs": {"execute": True, "from_queue": False, "execute_topic_count": 5},
                        "selected_topics": [],
                        "topic_runs": [],
                        "outcome": {
                            "decision": "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED",
                            "promotion_allowed": False,
                            "topic_supply": {
                                "status": "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED",
                                "attempt_budget_exhausted": True,
                                "reason_code": "ATTEMPT_BUDGET_EXCEEDED",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_payload(artifact, min_quota=5)

        self.assertEqual(payload["status"], "PARTIAL_RETRYABLE_TOPIC_SUPPLY")
        self.assertEqual(payload["summary"]["failed_count"], 0)
        self.assertEqual(
            payload["summary"]["research_value_status"],
            "TOPIC_SUPPLY_ATTEMPT_BUDGET_RETRYABLE",
        )

    def test_no_executable_topic_status_is_not_supply_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "quota.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "autonomous-research-run.v1",
                        "status": "OK",
                        "contract": {
                            "research_only": True,
                            "does_not_train_model": True,
                            "does_not_write_models_latest_lgbm": True,
                            "does_not_change_risk_adjusted_score": True,
                            "does_not_change_production_ranking": True,
                            "production_promotion_allowed": False,
                        },
                        "inputs": {"execute": True, "from_queue": False, "execute_topic_count": 5},
                        "selected_topics": [],
                        "topic_runs": [],
                        "outcome": {"decision": "NO_EXECUTABLE_TOPIC", "promotion_allowed": False},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_payload(artifact, min_quota=5)

        self.assertEqual(payload["status"], "PARTIAL_NO_MORE_WORK")
        self.assertEqual(payload["summary"]["research_value_status"], "NO_MORE_EXECUTABLE_TOPIC")

    def test_one_topic_is_partial_no_more_work(self) -> None:
        artifact = self.build_artifact(1)
        self.assertEqual(build_payload(artifact, min_quota=5)["status"], "PARTIAL_NO_MORE_WORK")

    def test_three_topics_is_partial_no_more_work(self) -> None:
        artifact = self.build_artifact(3)
        self.assertEqual(build_payload(artifact, min_quota=5)["status"], "PARTIAL_NO_MORE_WORK")

    def test_five_topics_completes_batch(self) -> None:
        artifact = self.build_artifact(5)
        self.assertEqual(build_payload(artifact, min_quota=5)["status"], "COMPLETED")

    def test_topic_failure_is_failed(self) -> None:
        artifact = self.build_artifact(1)
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        payload["status"] = "FAILED"
        payload["topic_runs"][0]["status"] = "FAILED"
        artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        self.assertEqual(build_payload(artifact, min_quota=5)["status"], "FAILED")

    def test_development_screen_requires_explicit_no_registry_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            contract_path = directory / "development_screen_contract.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "schema_version": "development-screen-contract.v1",
                        "boundary": {
                            "experiment_registry_write_allowed": False,
                            "production_promotion_allowed": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            artifact = directory / "quota.json"
            topic = {"topic_id": "topic:development:development_screen"}
            matrix_command = [
                ".venv/bin/python",
                "scripts/run_backtest_strategy_matrix.py",
                "--development-only",
            ]
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "autonomous-research-run.v1",
                        "status": "OK",
                        "contract": {
                            "research_only": True,
                            "does_not_train_model": True,
                            "does_not_write_models_latest_lgbm": True,
                            "does_not_change_risk_adjusted_score": True,
                            "does_not_change_production_ranking": True,
                            "production_promotion_allowed": False,
                            "development_screen_enabled": True,
                            "development_screen_registry_write_allowed": False,
                        },
                        "inputs": {
                            "execute": True,
                            "from_queue": False,
                            "execute_topic_count": 5,
                        },
                        "selected_topics": [topic],
                        "topic_runs": [
                            {
                                "topic": topic,
                                "status": "OK",
                                "outcome": {
                                    "decision": "DEVELOPMENT_CANDIDATE",
                                    "research_stage": "DEVELOPMENT_SCREEN",
                                    "promotion_allowed": False,
                                },
                                "steps": [
                                    {"command": matrix_command},
                                    {"command": matrix_command},
                                ],
                                "outputs": {
                                    "development_screen_contract": str(contract_path),
                                },
                            }
                        ],
                        "outcome": {
                            "decision": "DEVELOPMENT_CANDIDATE",
                            "promotion_allowed": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            payload = build_payload(artifact, min_quota=5)

        boundary = next(
            check
            for check in payload["checks"]
            if check["name"] == "development_screen_boundary"
        )
        self.assertTrue(boundary["ok"])
        self.assertEqual(payload["summary"]["research_value_status"], "HAS_FOLLOWUP_SIGNAL")

    def test_quota_above_cap_is_blocked(self) -> None:
        artifact = self.build_artifact(5, quota=6)
        self.assertEqual(build_payload(artifact, min_quota=5)["status"], "BLOCKED")


class DailyRuntimeReceiptVerifierTest(unittest.TestCase):
    def _receipt(self, root: Path) -> dict:
        context = build_run_context(
            "2026-08-08T02:00:00Z",
            project_root=root,
        )
        return build_receipt(
            run_context=context,
            generated_at_utc="2026-08-08T02:01:00Z",
            project_root=root,
        )

    def test_independent_clock_exact_freshness_boundaries(self) -> None:
        with _runtime_fixture() as (root, _):
            receipt = self._receipt(root)
            cases = [
                ("2026-08-08T02:00:55Z", True, None),
                ("2026-08-08T02:00:54.999000Z", False, "FUTURE_RECEIPT"),
                ("2026-08-08T02:16:00Z", True, None),
                ("2026-08-08T02:16:00.001000Z", False, "STALE_RECEIPT"),
            ]
            results = [
                verify_receipt(
                    receipt,
                    project_root=root,
                    verification_time_utc=verification_time,
                )
                for verification_time, _, _ in cases
            ]

        for result, (_, expected_ok, expected_reason) in zip(results, cases):
            self.assertIs(result["ok"], expected_ok, result)
            if expected_reason:
                self.assertIn(expected_reason, result["reason_codes"])

    def test_verifier_recomputes_contract_hash_and_source_lineage(self) -> None:
        with _runtime_fixture() as (root, _):
            receipt = self._receipt(root)
            receipt["time_authority"]["contract_hash"] = "0" * 64
            result = verify_receipt(
                receipt,
                project_root=root,
                verification_time_utc="2026-08-08T02:02:00Z",
            )

        self.assertFalse(result["ok"])
        self.assertIn("TIME_CONTRACT_HASH_MISMATCH", result["reason_codes"])
        self.assertNotEqual(
            result["contract_hash_expected"],
            result["contract_hash_observed"],
        )

    def test_host_timezone_drift_does_not_change_verdict(self) -> None:
        original_tz = os.environ.get("TZ")
        try:
            with _runtime_fixture() as (root, _):
                receipt = self._receipt(root)
                results = []
                for host_tz in ("UTC", "Asia/Taipei", "America/Los_Angeles"):
                    os.environ["TZ"] = host_tz
                    time.tzset()
                    results.append(
                        verify_receipt(
                            receipt,
                            project_root=root,
                            verification_time_utc="2026-08-08T02:02:00Z",
                        )
                    )
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()

        self.assertTrue(all(result["ok"] for result in results), results)
        self.assertEqual(
            [result["computed_market_run_date"] for result in results],
            ["2026-08-08"] * 3,
        )

    def test_market_midnight_rollover_is_rejected(self) -> None:
        with _runtime_fixture() as (root, _):
            receipt = self._receipt(root)
            receipt["time_authority"]["generated_at_utc"] = "2026-08-08T16:00:00Z"
            receipt["time_authority"]["generated_market_datetime"] = (
                "2026-08-09T00:00:00+08:00"
            )
            result = verify_receipt(
                receipt,
                project_root=root,
                verification_time_utc="2026-08-08T16:00:01Z",
            )

        self.assertFalse(result["ok"])
        self.assertIn("MARKET_DATE_MISMATCH", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
