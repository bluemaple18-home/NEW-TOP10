from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from scripts import run_autonomous_research as research


class AutonomousResearchTopicBankTests(unittest.TestCase):
    def test_profile_topics_have_distinct_ids_and_params(self):
        row = {"repo_path": "artifacts/backtest/shadow_rankings_regime_guard_recent", "count": 12}
        topics = [
            research.topic_for_dir(
                row,
                baseline_dir=research.BASELINE_RANKINGS_DIR,
                ledger_candidates=[],
                external_signals=[],
                evidence_sources=[],
                profile=profile,
            )
            for profile in research.VALIDATION_PROFILES
        ]
        topics = [topic for topic in topics if topic]

        self.assertEqual(len(topics), len(research.VALIDATION_PROFILES))
        self.assertEqual(topics[0].validation_profile, "standard")
        self.assertEqual(topics[0].topic_id, "strategy-matrix:artifacts-backtest-shadow_rankings_regime_guard_recent")
        self.assertTrue(any(topic.topic_id.endswith(":risk_guard") for topic in topics))
        self.assertGreater(len({topic.topic_id for topic in topics}), 1)
        self.assertGreater(len({topic.horizons for topic in topics}), 1)

    def test_matrix_command_uses_topic_profile_params(self):
        args = argparse.Namespace(
            features="data/clean/features.parquet",
            max_ranking_files=8,
            horizons="3,5,10",
            stop_loss_pcts="none,0.08,0.12",
            take_profit_pcts="none,0.15,0.25",
            max_group_exposures="none,0.35,0.55",
        )
        topic = research.topic_for_dir(
            {"repo_path": "artifacts/backtest/shadow_rankings_regime_guard_recent", "count": 12},
            baseline_dir=research.BASELINE_RANKINGS_DIR,
            ledger_candidates=[],
            external_signals=[],
            evidence_sources=[],
            profile=research.VALIDATION_PROFILES[1],
        )
        assert topic is not None

        command = research.matrix_command(args, topic.candidate_dir, "out.json", topic)

        self.assertEqual(command[command.index("--horizons") + 1], topic.horizons)
        self.assertEqual(command[command.index("--stop-loss-pcts") + 1], topic.stop_loss_pcts)
        self.assertEqual(command[command.index("--max-group-exposures") + 1], topic.max_group_exposures)

    def test_active_topic_bank_excludes_completed_and_queued_topics(self):
        args = argparse.Namespace(max_topics=12)
        with tempfile.TemporaryDirectory() as tmp:
            original_output_dir = research.OUTPUT_DIR
            try:
                research.OUTPUT_DIR = Path(tmp)
                topics = [
                    research.topic_for_dir(
                        {"repo_path": f"artifacts/backtest/shadow_rankings_regime_guard_recent_{index}", "count": 12},
                        baseline_dir=research.BASELINE_RANKINGS_DIR,
                        ledger_candidates=[],
                        external_signals=[],
                        evidence_sources=[],
                        profile=research.VALIDATION_PROFILES[0],
                    )
                    for index in range(3)
                ]
                topics = [topic for topic in topics if topic]
                registry = {
                    topics[0].topic_id: {"topic_id": topics[0].topic_id, "run_count": 1, "manager_status": "rejected"},
                    topics[1].topic_id: {"topic_id": topics[1].topic_id, "run_count": 0, "manager_status": "candidate"},
                }

                path = research.write_topic_bank(topics, args, registry_rows=registry, queued_ids={topics[1].topic_id})
                payload = json.loads(path.read_text(encoding="utf-8"))

                self.assertEqual(payload["generated_topic_count"], 3)
                self.assertEqual(payload["topic_count"], 1)
                self.assertEqual(payload["topics"][0]["topic_id"], topics[2].topic_id)
                self.assertTrue(payload["contract"]["active_bank_excludes_completed_topics"])
                self.assertTrue(payload["contract"]["active_bank_excludes_queued_topics"])
            finally:
                research.OUTPUT_DIR = original_output_dir


if __name__ == "__main__":
    unittest.main()
