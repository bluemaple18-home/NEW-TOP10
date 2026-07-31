from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_queue_selection_is_controlled_and_empty_queue_falls_back_safely(self):
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
                                    "execute": True,
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
                fallback = research.select_topics_for_run(
                    [eligible, rejected],
                    self.manager_args(),
                )
                self.assertEqual(
                    [topic.topic_id for topic in fallback],
                    [eligible.topic_id],
                )
            finally:
                research.OUTPUT_DIR = original_output_dir

    def test_main_routes_nine_actionable_queue_topics_when_active_bank_is_empty(self):
        queued_topics = [
            self.make_topic(f"queued-actionable-{index}")
            for index in range(9)
        ]
        args = argparse.Namespace(
            date="2026-07-31",
            output="ignored.json",
            features="data/clean/features.parquet",
            baseline_dir=research.BASELINE_RANKINGS_DIR,
            candidate_dir=None,
            topic_index=0,
            max_topics=12,
            min_ranking_files=3,
            max_ranking_files=8,
            horizons="3,5,10",
            stop_loss_pcts="none,0.08,0.12",
            take_profit_pcts="none,0.15,0.25",
            max_group_exposures="none,0.35,0.55",
            execute=True,
            execute_topic_count=1,
            from_queue=False,
            rerun=False,
            include_rejected=False,
            no_manager_update=True,
            closed_regime_research=False,
            development_screen_on_sealed_exhaustion=False,
            development_screen_topic_count=1,
            market_regime_history=None,
            research_contract="config/regime_research_contract.json",
            coverage_map=None,
        )
        captured: dict[str, object] = {}

        with (
            patch.object(research, "parse_args", return_value=args),
            patch.object(
                research,
                "generate_all_topics",
                return_value=queued_topics,
            ),
            patch.object(research, "write_topic_bank", return_value=Path("topic_bank.json")),
            patch.object(
                research,
                "queued_topic_ids",
                return_value={topic.topic_id for topic in queued_topics},
            ),
            patch.object(research, "load_active_topic_bank", return_value=[]),
            patch.object(
                research,
                "load_next_action_queue",
                return_value=[
                    {"topic_id": topic.topic_id}
                    for topic in queued_topics
                ],
            ),
            patch.object(research, "load_topic_registry", return_value={}),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
            patch.object(
                research,
                "execute_topic",
                return_value=(
                    [],
                    {"decision": "REJECTED_BY_STRATEGY_MATRIX", "promotion_allowed": False},
                    {},
                ),
            ),
            patch.object(
                research,
                "write_run_artifacts",
                side_effect=lambda payload, _output: captured.update(payload),
            ),
        ):
            exit_code = research.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            [row["topic_id"] for row in captured["selected_topics"]],
            [queued_topics[0].topic_id],
        )

    def test_queue_first_falls_back_and_deduplicates_for_all_cli_modes(self):
        queued = self.make_topic("queue-first")
        active = self.make_topic("active-fallback")
        queue = [
            {"topic_id": "topic:stale"},
            {"topic_id": queued.topic_id},
            {"topic_id": queued.topic_id},
        ]

        with (
            patch.object(research, "load_next_action_queue", return_value=queue),
            patch.object(research, "load_topic_registry", return_value={}),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
        ):
            default_selected = research.select_topics_for_run(
                [active, queued],
                self.manager_args(from_queue=False, execute_topic_count=2),
            )
            explicit_selected = research.select_topics_for_run(
                [active, queued],
                self.manager_args(from_queue=True, execute_topic_count=2),
            )

        expected = [queued.topic_id, active.topic_id]
        self.assertEqual([topic.topic_id for topic in default_selected], expected)
        self.assertEqual([topic.topic_id for topic in explicit_selected], expected)

    def test_closed_capacity_excludes_topics_with_used_sealed_dataset(self):
        topic = replace(
            self.make_topic("used-sealed"),
            regime_identity={"base_regime": "RISK_OFF", "family_tags": []},
        )
        lineage = {
            "dataset_hash": "sha256:dataset",
            "sealed_episode_ids": ["sha256:sealed-episode"],
            "sealed_trade_dates": ["2026-07-22", "2026-07-23"],
            "sealed_trade_date_hash": "sha256:sealed-dates",
            "sealed_dataset_slice_hash": "sha256:sealed-slice",
        }
        registry = [
            {
                "experiment_id": "experiment:used",
                "sealed_episode_ids": lineage["sealed_episode_ids"],
                "sealed_trade_dates": lineage["sealed_trade_dates"],
                "sealed_trade_date_hash": lineage["sealed_trade_date_hash"],
                "sealed_dataset_slice_hash": lineage["sealed_dataset_slice_hash"],
            }
        ]
        args = self.manager_args(closed_regime_research=True)

        with (
            patch.object(research, "closed_experiment_context", return_value={"lineage": lineage}),
            patch.object(research, "load_experiment_registry", return_value=registry),
            patch.object(research, "load_topic_registry", return_value={}),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
        ):
            topics = research.apply_closed_experiment_capacity([topic], args)

        self.assertFalse(topics[0].eligible)
        self.assertEqual(topics[0].reason_code, "SEALED_DATASET_REUSE")
        self.assertEqual(
            topics[0].selection_rationale["sealed_capacity"]["source_experiment_id"],
            "experiment:used",
        )

    def test_used_sealed_dataset_routes_to_development_screen(self):
        topic = replace(
            self.make_topic("used-sealed-development"),
            regime_identity={"base_regime": "RISK_OFF", "family_tags": []},
            reason_code="ELIGIBLE",
        )
        lineage = {
            "dataset_hash": "sha256:dataset",
            "split_id": "sha256:split",
            "development_episode_ids": ["sha256:development-1", "sha256:development-2"],
            "validation_episode_ids": ["sha256:validation"],
            "embargo_episode_ids": ["sha256:embargo"],
            "sealed_episode_ids": ["sha256:sealed-episode"],
            "sealed_trade_dates": ["2026-07-22", "2026-07-23"],
            "sealed_trade_date_hash": "sha256:sealed-dates",
            "sealed_dataset_slice_hash": "sha256:sealed-slice",
        }
        registry = [
            {
                "experiment_id": "experiment:used",
                "sealed_episode_ids": lineage["sealed_episode_ids"],
                "sealed_trade_dates": lineage["sealed_trade_dates"],
                "sealed_trade_date_hash": lineage["sealed_trade_date_hash"],
                "sealed_dataset_slice_hash": lineage["sealed_dataset_slice_hash"],
            }
        ]
        args = self.manager_args(
            closed_regime_research=True,
            development_screen_on_sealed_exhaustion=True,
        )

        with (
            patch.object(research, "closed_experiment_context", return_value={"lineage": lineage}),
            patch.object(research, "load_experiment_registry", return_value=registry),
            patch.object(research, "load_topic_registry", return_value={}),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
        ):
            topics = research.apply_closed_experiment_capacity([topic], args)

        self.assertTrue(topics[0].eligible)
        self.assertEqual(topics[0].reason_code, "DEVELOPMENT_SCREEN_ONLY")
        self.assertTrue(topics[0].topic_id.endswith(":development_screen"))
        self.assertEqual(
            topics[0].selection_rationale["research_stage"],
            "DEVELOPMENT_SCREEN",
        )
        self.assertFalse(
            topics[0].selection_rationale["development_contract"]["experiment_registry_write_allowed"]
        )

    def test_fresh_sealed_capacity_requires_passed_development_screen(self):
        topic = replace(
            self.make_topic("fresh-after-development"),
            regime_identity={"base_regime": "RISK_OFF", "family_tags": []},
            reason_code="ELIGIBLE",
        )
        lineage = {
            "dataset_hash": "sha256:dataset",
            "split_id": "sha256:split",
            "development_episode_ids": ["sha256:development-1", "sha256:development-2"],
            "validation_episode_ids": ["sha256:validation"],
            "embargo_episode_ids": ["sha256:embargo"],
            "sealed_episode_ids": ["sha256:fresh-sealed"],
            "sealed_trade_dates": ["2026-08-03", "2026-08-04"],
            "sealed_trade_date_hash": "sha256:fresh-sealed-dates",
            "sealed_dataset_slice_hash": "sha256:fresh-sealed-slice",
        }
        args = self.manager_args(
            closed_regime_research=True,
            development_screen_on_sealed_exhaustion=True,
        )

        with (
            patch.object(research, "closed_experiment_context", return_value={"lineage": lineage}),
            patch.object(research, "load_experiment_registry", return_value=[]),
            patch.object(research, "load_topic_registry", return_value={}),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
        ):
            before_screen = research.apply_closed_experiment_capacity([topic], args)

        development_id = f"{topic.topic_id}:development_screen"
        manager_registry = {
            development_id: {
                "topic_id": development_id,
                "manager_status": "development_screen_passed",
                "run_count": 1,
            }
        }
        with (
            patch.object(research, "closed_experiment_context", return_value={"lineage": lineage}),
            patch.object(research, "load_experiment_registry", return_value=[]),
            patch.object(research, "load_topic_registry", return_value=manager_registry),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
        ):
            after_screen = research.apply_closed_experiment_capacity([topic], args)

        self.assertEqual(before_screen[0].topic_id, development_id)
        self.assertEqual(before_screen[0].reason_code, "DEVELOPMENT_SCREEN_ONLY")
        self.assertEqual(after_screen[0].topic_id, topic.topic_id)
        self.assertEqual(after_screen[0].reason_code, "ELIGIBLE")

    def test_development_matrix_uses_exact_episode_scope_without_closed_registry(self):
        topic = replace(
            self.make_topic("development-command"),
            regime_identity={"base_regime": "RISK_OFF", "family_tags": []},
            reason_code="DEVELOPMENT_SCREEN_ONLY",
            selection_rationale={"research_stage": "DEVELOPMENT_SCREEN"},
        )
        args = argparse.Namespace(
            features="data/clean/features.parquet",
            max_ranking_files=8,
            horizons="3,5,10",
            stop_loss_pcts="none,0.08,0.12",
            take_profit_pcts="none,0.15,0.25",
            max_group_exposures="none,0.35,0.55",
            closed_regime_research=True,
            market_regime_history="artifacts/market_regime_history.json",
        )

        command = research.matrix_command(
            args,
            topic.candidate_dir,
            "out.json",
            topic,
            allowed_episode_ids=["sha256:development-1"],
            research_stage="DEVELOPMENT_SCREEN",
        )

        self.assertIn("--require-exact-regime", command)
        self.assertIn("--development-only", command)
        self.assertNotIn("--pre-registration", command)
        self.assertNotIn("--experiment-registry", command)

    def test_development_selection_respects_its_own_batch_cap(self):
        topics = [
            replace(
                self.make_topic(f"development-cap-{index}"),
                reason_code="DEVELOPMENT_SCREEN_ONLY",
                selection_rationale={"research_stage": "DEVELOPMENT_SCREEN"},
            )
            for index in range(3)
        ]
        args = self.manager_args(
            from_queue=False,
            execute_topic_count=5,
            development_screen_topic_count=1,
        )

        with (
            patch.object(research, "load_topic_registry", return_value={}),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
        ):
            selected = research.select_topics_for_run(topics, args)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].topic_id, topics[0].topic_id)

    def test_development_outcome_is_diagnostic_and_never_promotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "comparison.json"
            path.write_text(
                json.dumps(
                    {
                        "summary": [
                            {
                                "variant": "baseline",
                                "research_stage": "DEVELOPMENT_SCREEN",
                                "best_score": 0.1,
                                "best_total_return": 0.01,
                                "best_max_drawdown": -0.10,
                            },
                            {
                                "variant": "candidate",
                                "research_stage": "DEVELOPMENT_SCREEN",
                                "best_score": 0.2,
                                "best_total_return": 0.02,
                                "best_max_drawdown": -0.09,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            outcome = research.outcome_from_comparison(
                path,
                research_stage="DEVELOPMENT_SCREEN",
            )

        self.assertEqual(outcome["decision"], "DEVELOPMENT_CANDIDATE")
        self.assertTrue(outcome["sealed_validation_required"])
        self.assertFalse(outcome["formal_candidate_allowed"])
        self.assertFalse(outcome["promotion_allowed"])

    def test_development_execution_writes_contract_without_closed_registry(self):
        topic = replace(
            self.make_topic("development-execution"),
            topic_id="topic:development-execution:development_screen",
            regime_identity={"base_regime": "RISK_OFF", "family_tags": []},
            reason_code="DEVELOPMENT_SCREEN_ONLY",
            selection_rationale={
                "research_stage": "DEVELOPMENT_SCREEN",
                "parent_topic_id": "topic:development-execution",
            },
        )
        lineage = {
            "dataset_hash": "sha256:dataset",
            "split_id": "sha256:split",
            "split_artifact_hash": "sha256:split-artifact",
            "development_episode_ids": ["sha256:development-1", "sha256:development-2"],
            "validation_episode_ids": ["sha256:validation"],
            "embargo_episode_ids": ["sha256:embargo"],
            "sealed_episode_ids": ["sha256:sealed"],
            "sealed_trade_date_hash": "sha256:sealed-dates",
        }
        args = argparse.Namespace(
            features="data/clean/features.parquet",
            max_ranking_files=8,
            horizons="3,5,10",
            stop_loss_pcts="none,0.08,0.12",
            take_profit_pcts="none,0.15,0.25",
            max_group_exposures="none,0.35,0.55",
            closed_regime_research=True,
            market_regime_history="artifacts/market_regime_history.json",
        )

        def fake_run_step(name: str, command: list[str]):
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            if name == "compare.strategy_matrices":
                output.write_text(
                    json.dumps(
                        {
                            "summary": [
                                {
                                    "variant": "baseline",
                                    "research_stage": "DEVELOPMENT_SCREEN",
                                    "best_score": 0.1,
                                    "best_total_return": 0.01,
                                    "best_max_drawdown": -0.10,
                                },
                                {
                                    "variant": "candidate",
                                    "research_stage": "DEVELOPMENT_SCREEN",
                                    "best_score": 0.2,
                                    "best_total_return": 0.02,
                                    "best_max_drawdown": -0.09,
                                },
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
            else:
                output.write_text("{}", encoding="utf-8")
            return {
                "name": name,
                "status": "OK",
                "returncode": 0,
                "started_at": "2026-07-29T00:00:00+00:00",
                "ended_at": "2026-07-29T00:00:01+00:00",
                "command": command,
                "stdout_tail": "",
                "stderr_tail": "",
            }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "manager"
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            with (
                patch.object(research, "OUTPUT_DIR", output_dir),
                patch.object(
                    research,
                    "closed_experiment_context",
                    return_value={
                        "lineage": lineage,
                        "regime_id": "RISK_OFF|",
                        "contract": {},
                    },
                ),
                patch.object(research, "run_step", side_effect=fake_run_step),
            ):
                steps, outcome, outputs = research.execute_topic(args, topic, run_dir)

            contract_path = Path(outputs["development_screen_contract"])
            self.assertTrue(contract_path.exists())
            self.assertFalse((output_dir / "closed_experiment_registry.jsonl").exists())

        matrix_steps = [
            step
            for step in steps
            if step["name"] in {"baseline.strategy_matrix", "candidate.strategy_matrix"}
        ]
        self.assertEqual(len(matrix_steps), 2)
        for step in matrix_steps:
            self.assertIn("--development-only", step["command"])
            self.assertNotIn("--experiment-registry", step["command"])
        self.assertEqual(outcome["decision"], "DEVELOPMENT_CANDIDATE")
        self.assertFalse(outcome["promotion_allowed"])

    def test_failed_development_run_stays_retryable_without_consuming_topic(self):
        topic = replace(
            self.make_topic("development-runtime-failure"),
            topic_id="topic:development-runtime-failure:development_screen",
            reason_code="DEVELOPMENT_SCREEN_ONLY",
            selection_rationale={"research_stage": "DEVELOPMENT_SCREEN"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            original_output_dir = research.OUTPUT_DIR
            try:
                research.OUTPUT_DIR = Path(tmp)
                output = Path(tmp) / "failed_run.json"
                payload = {
                    "date": "2026-07-29",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": "FAILED",
                    "inputs": {"execute": True},
                    "topics": [research.topic_to_json(topic)],
                    "all_topics": [research.topic_to_json(topic)],
                    "selected_topics": [research.topic_to_json(topic)],
                    "topic_runs": [
                        {
                            "topic": research.topic_to_json(topic),
                            "status": "FAILED",
                            "outcome": {
                                "decision": "DEVELOPMENT_NO_COMPARISON_EVIDENCE",
                                "research_stage": "DEVELOPMENT_SCREEN",
                                "promotion_allowed": False,
                            },
                        }
                    ],
                    "outcome": {
                        "decision": "DEVELOPMENT_NO_COMPARISON_EVIDENCE",
                        "promotion_allowed": False,
                    },
                }

                research.update_manager(payload, output)
                registered = research.load_topic_registry()[topic.topic_id]
                active = research.load_active_topic_bank()

                self.assertEqual(registered["manager_status"], "runtime_failed_retryable")
                self.assertEqual(registered["run_count"], 0)
                self.assertEqual(registered["failure_count"], 1)
                self.assertEqual(research.load_next_action_queue(), [])
                self.assertEqual([item.topic_id for item in active], [topic.topic_id])
            finally:
                research.OUTPUT_DIR = original_output_dir

    def test_closed_capacity_reserves_fresh_slice_for_one_topic_per_run(self):
        first = replace(
            self.make_topic("fresh-first"),
            regime_identity={"base_regime": "RISK_OFF", "family_tags": []},
        )
        second = replace(
            self.make_topic("fresh-second"),
            regime_identity={"base_regime": "RISK_OFF", "family_tags": []},
        )
        lineage = {
            "dataset_hash": "sha256:dataset",
            "sealed_episode_ids": ["sha256:sealed-episode"],
            "sealed_trade_dates": ["2026-07-22", "2026-07-23"],
            "sealed_trade_date_hash": "sha256:sealed-dates",
            "sealed_dataset_slice_hash": "sha256:sealed-slice",
        }
        args = self.manager_args(closed_regime_research=True)

        with (
            patch.object(research, "closed_experiment_context", return_value={"lineage": lineage}),
            patch.object(research, "load_experiment_registry", return_value=[]),
            patch.object(research, "load_topic_registry", return_value={}),
            patch.object(research, "load_last_run_at_by_topic", return_value={}),
        ):
            topics = research.apply_closed_experiment_capacity([first, second], args)

        self.assertTrue(topics[0].eligible)
        self.assertFalse(topics[1].eligible)
        self.assertEqual(topics[1].reason_code, "SEALED_DATASET_REUSE")

    def test_history_fallback_requires_proven_real_execution(self):
        now = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)
        topic = self.make_topic("legacy-history")
        with tempfile.TemporaryDirectory() as tmp:
            original_output_dir = research.OUTPUT_DIR
            try:
                research.OUTPUT_DIR = Path(tmp)
                history_path = research.manager_paths()["history"]
                base_row = {
                    "generated_at": (now - timedelta(hours=25)).isoformat(),
                    "selected_topic_id": topic.topic_id,
                }
                registry = {topic.topic_id: {"manager_status": "partial_needs_followup", "run_count": 1}}

                for row in [{**base_row, "execute": False}, base_row]:
                    history_path.write_text(json.dumps({"runs": [row]}), encoding="utf-8")
                    fallback = research.load_last_run_at_by_topic()
                    self.assertNotIn(topic.topic_id, fallback)
                    self.assertFalse(
                        research.topic_allowed_by_manager(
                            topic,
                            registry,
                            self.manager_args(),
                            last_run_at_by_topic=fallback,
                            now=now,
                        )
                    )

                history_path.write_text(json.dumps({"runs": [{**base_row, "execute": True}]}), encoding="utf-8")
                fallback = research.load_last_run_at_by_topic()
                self.assertIn(topic.topic_id, fallback)
                self.assertTrue(
                    research.topic_allowed_by_manager(
                        topic,
                        registry,
                        self.manager_args(),
                        last_run_at_by_topic=fallback,
                        now=now,
                    )
                )
            finally:
                research.OUTPUT_DIR = original_output_dir

    def test_partial_topic_stays_queued_until_third_run_then_exhausts(self):
        topic = self.make_topic("partial-lifecycle")
        with tempfile.TemporaryDirectory() as tmp:
            original_output_dir = research.OUTPUT_DIR
            try:
                research.OUTPUT_DIR = Path(tmp)
                paths = research.manager_paths()
                paths["registry"].write_text(
                    json.dumps(
                        {
                            "topics": [
                                {
                                    **research.topic_to_json(topic),
                                    "manager_status": "partial_needs_followup",
                                    "run_count": 1,
                                    "last_run_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                payload = {
                    "date": "2026-07-17",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": "OK",
                    "inputs": {"execute": True},
                    "topics": [research.topic_to_json(topic)],
                    "all_topics": [research.topic_to_json(topic)],
                    "selected_topics": [research.topic_to_json(topic)],
                    "topic_runs": [
                        {
                            "topic": research.topic_to_json(topic),
                            "status": "OK",
                            "outcome": {"decision": "PARTIAL_SCORE_ONLY", "promotion_allowed": False},
                        }
                    ],
                    "outcome": {"decision": "PARTIAL_SCORE_ONLY", "promotion_allowed": False},
                }

                self.assertTrue(research.topic_allowed_by_manager(topic, research.load_topic_registry(), self.manager_args()))
                research.update_manager(payload, paths["history"])
                registry = research.load_topic_registry()
                self.assertEqual(registry[topic.topic_id]["run_count"], 2)
                self.assertEqual(research.queued_topic_ids(), {topic.topic_id})
                self.assertEqual(research.select_topics_for_run([topic], self.manager_args()), [])

                registry[topic.topic_id]["last_run_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
                paths["registry"].write_text(json.dumps({"topics": list(registry.values())}), encoding="utf-8")
                self.assertEqual(
                    [item.topic_id for item in research.select_topics_for_run([topic], self.manager_args())],
                    [topic.topic_id],
                )

                research.update_manager(payload, paths["history"])
                self.assertEqual(research.load_topic_registry()[topic.topic_id]["run_count"], 3)
                self.assertEqual(research.load_next_action_queue(), [])
                self.assertEqual(research.select_topics_for_run([topic], self.manager_args()), [])
            finally:
                research.OUTPUT_DIR = original_output_dir


if __name__ == "__main__":
    unittest.main()
