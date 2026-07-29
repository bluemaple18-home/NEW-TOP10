from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.research import fog_map_domain, fog_map_render, map_contract
from scripts import build_research_fog_map as adapter


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ResearchFogMapRefactorTests(unittest.TestCase):
    def test_legacy_public_functions_remain_importable(self) -> None:
        public_functions = {
            "parse_args",
            "resolve_path",
            "repo_path",
            "read_json",
            "latest_weekend_rollup_path",
            "build_burn_down_progress",
            "write_json",
            "safe_text",
            "safe_number",
            "sanitize_action",
            "clean_repoish_path",
            "classify_family",
            "classify_status",
            "node_position",
            "outcome_by_topic_id",
            "scenario_summary",
            "delta_summary",
            "fixture_topics",
            "build_nodes",
            "aggregate_nodes_from_scenarios",
            "summary_from_nodes",
            "progress_bar",
            "build_family_summary",
            "build_mission_queue",
            "build_active_expansion_queue",
            "build_unlit_representative_queue",
            "build_payload",
            "render_metric_card",
            "render_html",
            "main",
        }

        self.assertTrue(all(callable(getattr(adapter, name, None)) for name in public_functions))
        self.assertIs(adapter.render_html, fog_map_render.render_html)
        self.assertEqual(adapter.STATUS_PRIORITY, fog_map_domain.STATUS_PRIORITY)
        self.assertEqual(adapter.SCHEMA_VERSION, fog_map_domain.SCHEMA_VERSION)

    def test_adapter_payload_matches_pure_domain_fixture(self) -> None:
        date = "2099-01-01"
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "autonomous_research"
            weekend_dir = Path(tmp) / "weekend_training"
            parent_path = Path(tmp) / "missing-parent.json"
            with (
                patch.object(adapter, "SOURCE_DIR", source_dir),
                patch.object(adapter, "WEEKEND_DIR", weekend_dir),
                patch.object(adapter, "ACTIVE_EXPANSION_PARENT_PATH", parent_path),
            ):
                actual = adapter.build_payload(date)

        with patch.object(Path, "read_text", side_effect=AssertionError("domain 不得讀檔")):
            expected = fog_map_domain.build_payload(
                date,
                progress={},
                registry={},
                queue={},
                history={},
                history_records=[],
                weekend_rollup=None,
                weekend_rollup_source=None,
                active_expansion_parent={},
                active_expansion_parent_evidence=None,
                source_paths={
                    "progress": None,
                    "topic_registry": None,
                    "run_history": None,
                    "run_history_jsonl": None,
                    "next_action_queue": None,
                },
                generated_at=actual["generated_at"],
            )

        self.assertEqual(actual, expected)
        self.assertEqual(actual["schema_version"], "research-fog-map.v2")
        self.assertTrue(actual["contract"]["does_not_change_production_ranking"])

    def test_development_lifecycle_evidence_does_not_expand_fog_universe(self) -> None:
        parent_id = "strategy-matrix:artifacts-backtest-shadow"
        lifecycle_id = f"{parent_id}:development_screen"
        dimensions = {
            "horizon": "3",
            "stop_loss": "none",
            "take_profit": "none",
            "group_exposure": "none",
        }
        lifecycle_topic = {
            "topic_id": lifecycle_id,
            "candidate_dir": "artifacts/backtest/shadow",
            "manager_status": "development_screen_passed",
            "selection_rationale": {"parent_topic_id": parent_id},
        }
        payload = fog_map_domain.build_payload(
            "2099-01-01",
            progress={},
            registry={
                "topics": [
                    {
                        "topic_id": parent_id,
                        "candidate_dir": "artifacts/backtest/shadow",
                        "manager_status": "candidate",
                    },
                    lifecycle_topic,
                ]
            },
            queue={},
            history={},
            history_records=[
                {
                    "topic_id": lifecycle_id,
                    "combo_id": map_contract.combo_id(lifecycle_topic, dimensions),
                    "dimensions": dimensions,
                    "status": "OK",
                    "decision": "DEVELOPMENT_CANDIDATE",
                    "finished_at": "2099-01-01T00:00:00+00:00",
                }
            ],
            weekend_rollup=None,
            weekend_rollup_source=None,
            active_expansion_parent={},
            active_expansion_parent_evidence=None,
            source_paths={},
        )

        self.assertEqual(payload["summary"]["total_topics"], 1)
        self.assertEqual(payload["summary"]["processed_combos"], 1)
        self.assertEqual(payload["nodes"][0]["topic_id"], parent_id)
        self.assertEqual(payload["nodes"][0]["lifecycle_topic_id"], lifecycle_id)

    def test_cli_writes_expected_json_and_html(self) -> None:
        date = "2099-01-01"
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "build_research_fog_map.py"),
                    "--date",
                    date,
                    "--output-dir",
                    tmp,
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            output = json.loads(completed.stdout)
            payload_path = Path(tmp) / f"research_fog_map_{date}.json"
            latest_path = Path(tmp) / "research_fog_map_latest.json"
            html_path = Path(tmp) / "index.html"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))

            self.assertEqual(output["status"], payload["status"])
            self.assertEqual(output["source_mode"], payload["source_mode"])
            self.assertEqual(output["total_topics"], payload["summary"]["total_topics"])
            self.assertEqual(payload, json.loads(latest_path.read_text(encoding="utf-8")))
            self.assertEqual(html_path.read_text(encoding="utf-8"), fog_map_render.render_html(payload))


if __name__ == "__main__":
    unittest.main()
