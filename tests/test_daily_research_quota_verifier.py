from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.verify_daily_research_quota import build_payload


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
        self.assertEqual(payload["summary"]["research_value_status"], "QUEUE_EMPTY")

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

    def test_quota_above_cap_is_blocked(self) -> None:
        artifact = self.build_artifact(5, quota=6)
        self.assertEqual(build_payload(artifact, min_quota=5)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
