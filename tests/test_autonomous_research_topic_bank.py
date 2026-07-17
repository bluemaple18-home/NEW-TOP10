from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from scripts import run_autonomous_research as research


class AutonomousResearchTopicBankTests(unittest.TestCase):
    def make_topic(self, suffix: str) -> research.ResearchTopic:
        return research.ResearchTopic(
            topic_id=f"topic:{suffix}",
            title=suffix,
            hypothesis="fixture",
            validation_plan="fixture",
            runner="strategy_matrix_comparison",
            candidate_dir=f"artifacts/backtest/{suffix}",
            baseline_dir=research.BASELINE_RANKINGS_DIR,
            score=1.0,
            reasons=[],
            evidence_sources=[],
            ranking_file_count=3,
        )

    def manager_args(self, **overrides):
        values = {"execute_topic_count": 10, "from_queue": True, "topic_index": 0, "execute": True, "rerun": False, "include_rejected": False}
        values.update(overrides)
        return SimpleNamespace(**values)

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

    def test_controlled_rerun_allows_only_supported_status_after_cooldown(self):
        now = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)
        last_run = (now - timedelta(hours=25)).isoformat()
        for status, run_count in [("confirmed_for_next_replay", 1), ("partial_needs_followup", 2)]:
            topic = self.make_topic(status)
            registry = {topic.topic_id: {"manager_status": status, "run_count": run_count, "last_run_at": last_run}}
            self.assertTrue(research.topic_allowed_by_manager(topic, registry, self.manager_args(), now=now))

    def test_controlled_rerun_rejects_cooldown_limit_missing_time_and_rejected(self):
        now = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)
        cases = [
            ("partial_needs_followup", 1, (now - timedelta(hours=23)).isoformat()),
            ("partial_needs_followup", 3, (now - timedelta(hours=25)).isoformat()),
            ("confirmed_for_next_replay", 2, (now - timedelta(hours=25)).isoformat()),
            ("confirmed_for_next_replay", 1, None),
            ("rejected", 1, (now - timedelta(days=10)).isoformat()),
            ("blocked_missing_evidence", 1, (now - timedelta(days=10)).isoformat()),
        ]
        for index, (status, run_count, last_run_at) in enumerate(cases):
            topic = self.make_topic(f"blocked-{index}")
            registry = {topic.topic_id: {"manager_status": status, "run_count": run_count, "last_run_at": last_run_at}}
            args = self.manager_args(rerun=True, include_rejected=True)
            self.assertFalse(research.topic_allowed_by_manager(topic, registry, args, now=now), status)

    def test_queue_selection_is_controlled_and_empty_queue_stops_safely(self):
        now = datetime.now(timezone.utc)
        eligible = self.make_topic("eligible")
        rejected = self.make_topic("rejected")
        with tempfile.TemporaryDirectory() as tmp:
            original_output_dir = research.OUTPUT_DIR
            try:
                research.OUTPUT_DIR = Path(tmp)
                paths = research.manager_paths()
                paths["registry"].write_text(
                    json.dumps(
                        {
                            "topics": [
                                {"topic_id": eligible.topic_id, "manager_status": "partial_needs_followup", "run_count": 1},
                                {"topic_id": rejected.topic_id, "manager_status": "rejected", "run_count": 1, "last_run_at": (now - timedelta(days=5)).isoformat()},
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                paths["history"].write_text(
                    json.dumps(
                        {
                            "runs": [
                                {
                                    "generated_at": (now - timedelta(hours=25)).isoformat(),
                                    "selected_topic_ids": [eligible.topic_id],
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                paths["queue"].write_text(
                    json.dumps({"actions": [{"topic_id": rejected.topic_id}, {"topic_id": eligible.topic_id}]}),
                    encoding="utf-8",
                )
                selected = research.select_topics_for_run([eligible, rejected], self.manager_args(rerun=True, include_rejected=True))
                self.assertEqual([topic.topic_id for topic in selected], [eligible.topic_id])

                paths["queue"].write_text(json.dumps({"actions": []}), encoding="utf-8")
                self.assertEqual(research.select_topics_for_run([eligible, rejected], self.manager_args()), [])
            finally:
                research.OUTPUT_DIR = original_output_dir


if __name__ == "__main__":
    unittest.main()
