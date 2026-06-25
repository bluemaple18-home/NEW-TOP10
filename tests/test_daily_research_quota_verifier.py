from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_daily_research_quota import build_payload


class DailyResearchQuotaVerifierTest(unittest.TestCase):
    def test_from_queue_no_executable_topic_is_ok_queue_empty(self) -> None:
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

        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["summary"]["research_value_status"], "QUEUE_EMPTY")


if __name__ == "__main__":
    unittest.main()
