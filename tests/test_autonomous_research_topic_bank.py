from __future__ import annotations

import argparse
import unittest

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


if __name__ == "__main__":
    unittest.main()
