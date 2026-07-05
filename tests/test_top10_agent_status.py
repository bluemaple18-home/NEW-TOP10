from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_top10_agent_status_rollup import build_rollup
from scripts.top10_agent_status import build_event, read_manifest, validate_event, write_agent_event


class Top10AgentStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = read_manifest(Path("docs/architecture/top10_harness_team.dashboard.json"))

    def test_build_and_validate_event(self):
        event = build_event(
            run_id="daily-2026-06-23",
            run_date="2026-06-23",
            agent_id="ranking",
            status="ok",
            decision="pass",
            input_refs=["artifacts/daily_report_2026-06-23.json"],
            artifact_paths=["artifacts/ranking_2026-06-23.csv"],
        )

        self.assertEqual(validate_event(event, self.manifest), [])
        self.assertEqual(event["schema_version"], "top10-agent-status-event.v1")

    def test_rejects_absolute_local_artifact_path(self):
        event = build_event(
            run_id="daily-2026-06-23",
            run_date="2026-06-23",
            agent_id="ranking",
            status="ok",
            decision="pass",
            artifact_paths=["/Users/mattkuo/TOP10new/artifacts/ranking.csv"],
        )

        errors = validate_event(event, self.manifest)
        self.assertTrue(any("repo-relative" in error for error in errors))

    def test_write_event_and_rollup(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            event = build_event(
                run_id="external-review-2026-06-23",
                run_date="2026-06-23",
                agent_id="external_review_harness",
                status="ok",
                decision="pass",
                artifact_paths=["artifacts/external_review/2026-06-23/review_packet_2026-06-23.json"],
            )
            event_path = write_agent_event(event, artifacts_dir=artifacts)

            self.assertTrue(event_path.exists())
            self.assertTrue((artifacts / "harness_status" / "2026-06-23" / "latest_run_id.txt").exists())
            jsonl = artifacts / "harness_status" / "2026-06-23" / "external-review-2026-06-23" / "events.jsonl"
            self.assertEqual(len(jsonl.read_text(encoding="utf-8").splitlines()), 1)

            rollup = build_rollup(artifacts, "2026-06-23", "external-review-2026-06-23", self.manifest)
            expected_agent_count = len(self.manifest.get("agents", []))
            self.assertEqual(rollup["schema_version"], "top10-agent-status-rollup.v1")
            self.assertEqual(rollup["summary"]["agent_count"], expected_agent_count)
            self.assertEqual(rollup["summary"]["formal_task_count"], expected_agent_count)
            self.assertEqual(rollup["summary"]["event_count"], 1)
            self.assertEqual(len(rollup["formal_tasks"]), expected_agent_count)
            self.assertTrue(all(task["task_id"].startswith("TOP10-HARNESS-") for task in rollup["formal_tasks"]))
            self.assertTrue(all(edge["connected"] for edge in rollup["flow_edges"]))
            row = next(item for item in rollup["agents"] if item["agent_id"] == "external_review_harness")
            self.assertEqual(row["status"], "ok")
            task = next(item for item in rollup["formal_tasks"] if item["agent_id"] == "external_review_harness")
            self.assertEqual(task["status"], "ok")
            self.assertFalse(task["missing"])
            fog_task = next(item for item in rollup["formal_tasks"] if item["agent_id"] == "fog_map")
            self.assertEqual(fog_task["index"], 12)
            self.assertEqual(fog_task["status"], "pending")
            research_task = next(item for item in rollup["formal_tasks"] if item["agent_id"] == "research_worker")
            self.assertEqual(research_task["index"], 13)
            self.assertEqual(research_task["status"], "pending")

            payload = json.loads(event_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["agent_id"], "external_review_harness")

    def test_fog_map_is_a_formal_agent(self):
        event = build_event(
            run_id="daily-2026-06-23",
            run_date="2026-06-23",
            agent_id="fog_map",
            status="ok",
            decision="pass",
            input_refs=["artifacts/external_review/2026-06-23/external_review_summary_2026-06-23.json"],
            artifact_paths=[
                "artifacts/research_map/research_fog_map_latest.json",
                "artifacts/research_map/index.html",
            ],
        )

        self.assertEqual(validate_event(event, self.manifest), [])

    def test_research_worker_is_a_formal_agent(self):
        event = build_event(
            run_id="daily-2026-06-23",
            run_date="2026-06-23",
            agent_id="research_worker",
            status="ok",
            decision="pass",
            input_refs=["artifacts/research_map/research_fog_map_latest.json"],
            artifact_paths=[
                "artifacts/autonomous_research/autonomous_research_daily_quota_2026-06-23.json",
                "artifacts/autonomous_research/run_history.jsonl",
            ],
        )

        self.assertEqual(validate_event(event, self.manifest), [])


if __name__ == "__main__":
    unittest.main()
