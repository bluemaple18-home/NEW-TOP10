from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.build_top10_agent_status_rollup import build_rollup
from scripts.top10_agent_status import build_event, read_manifest, rollup_lock, validate_event, write_agent_event


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

    def test_newer_harness_run_promotes_latest_without_old_run_reclaim(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)

            def record(run_id: str, started_at: str) -> None:
                event = build_event(
                    run_id=run_id, run_date="2026-10-15", agent_id="harness_runner",
                    status="ok", decision="pass", started_at=started_at,
                    finished_at="2026-10-15T09:00:00+00:00",
                )
                write_agent_event(event, artifacts_dir=artifacts)

            record("daily-old", "2026-10-15T07:00:00+00:00")
            record("daily-new", "2026-10-15T08:00:00+00:00")
            latest = artifacts / "harness_status" / "2026-10-15" / "latest_run_id.txt"
            self.assertEqual(latest.read_text().strip(), "daily-new")
            record("daily-old", "2026-10-15T07:00:00+00:00")
            self.assertEqual(latest.read_text().strip(), "daily-new")

    def test_daily_harness_replaces_research_only_latest_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            research = build_event(
                run_id="fog-research-first", run_date=date, agent_id="research_worker",
                status="ok", decision="pass", started_at="2026-10-15T07:00:00+00:00",
            )
            write_agent_event(research, artifacts_dir=artifacts)
            latest = artifacts / "harness_status" / date / "latest_run_id.txt"
            self.assertEqual(latest.read_text().strip(), "fog-research-first")
            daily = build_event(
                run_id="daily-after-fog", run_date=date, agent_id="harness_runner",
                status="ok", decision="pass", started_at="2026-10-15T08:00:00+00:00",
            )
            write_agent_event(daily, artifacts_dir=artifacts)
            self.assertEqual(latest.read_text().strip(), "daily-after-fog")

    def test_daily_harness_replaces_research_owner_with_later_ops_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            for agent_id, started in (("research_worker", "2026-10-15T07:00:00+00:00"),
                                      ("ops_reporter", "2026-10-15T09:00:00+00:00")):
                write_agent_event(build_event(
                    run_id="fog-research-first", run_date=date, agent_id=agent_id,
                    status="ok", decision="pass", started_at=started,
                ), artifacts_dir=artifacts)
            latest = artifacts / "harness_status" / date / "latest_run_id.txt"
            write_agent_event(build_event(
                run_id="daily-after-fog", run_date=date, agent_id="harness_runner",
                status="ok", decision="pass", started_at="2026-10-15T08:00:00+00:00",
            ), artifacts_dir=artifacts)
            self.assertEqual(latest.read_text().strip(), "daily-after-fog")

    def test_early_daily_failure_can_own_latest_for_ops_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            write_agent_event(build_event(
                run_id=f"daily-{date}", run_date=date, agent_id="daily_push",
                status="skipped", decision="stop",
                failure_reason="daily failed before publish; exit_code=1",
            ), artifacts_dir=artifacts)
            latest = artifacts / "harness_status" / date / "latest_run_id.txt"
            self.assertEqual(latest.read_text().strip(), f"daily-{date}")

    def test_early_daily_failure_replaces_earlier_fog_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            write_agent_event(build_event(
                run_id="fog-first", run_date=date, agent_id="research_worker",
                status="ok", decision="pass", started_at="2026-10-15T07:00:00+00:00",
            ), artifacts_dir=artifacts)
            write_agent_event(build_event(
                run_id=f"daily-{date}", run_date=date, agent_id="daily_push",
                status="skipped", decision="stop", started_at="2026-10-15T08:00:00+00:00",
                failure_reason="daily failed before publish; exit_code=1",
            ), artifacts_dir=artifacts)
            latest = artifacts / "harness_status" / date / "latest_run_id.txt"
            self.assertEqual(latest.read_text().strip(), f"daily-{date}")

    def test_missing_owner_event_cannot_be_replaced_by_unknown_older_harness(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            latest = artifacts / "harness_status" / date / "latest_run_id.txt"
            latest.parent.mkdir(parents=True)
            latest.write_text("daily-new\n")
            write_agent_event(build_event(
                run_id="daily-old", run_date=date, agent_id="harness_runner",
                status="ok", decision="pass", started_at="2026-10-15T07:00:00+00:00",
            ), artifacts_dir=artifacts)
            self.assertEqual(latest.read_text().strip(), "daily-new")

    def test_independent_owner_writer_waits_for_date_rollup_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            event = build_event(run_id="fog-first", run_date=date, agent_id="research_worker",
                                status="ok", decision="pass")
            ready = artifacts / "child-ready"
            command = (
                "import json,sys\nfrom pathlib import Path\n"
                "from scripts.top10_agent_status import write_agent_event\n"
                "Path(sys.argv[2]).touch()\n"
                "write_agent_event(json.loads(sys.argv[3]), artifacts_dir=Path(sys.argv[1]))\n"
            )
            with rollup_lock(artifacts, date, "daily-owner"):
                child = subprocess.Popen([sys.executable, "-c", command, str(artifacts),
                                          str(ready), json.dumps(event)],
                                         cwd=Path(__file__).resolve().parents[1])
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.exists())
                time.sleep(0.1)
                self.assertIsNone(child.poll())
            self.assertEqual(child.wait(timeout=5), 0)

    def test_harness_replaces_legacy_delivery_only_latest_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            old_event = build_event(
                run_id="daily-old", run_date=date, agent_id="daily_push",
                status="degraded", decision="stop",
                started_at="2026-10-15T07:00:00+00:00",
            )
            write_agent_event(old_event, artifacts_dir=artifacts)
            latest = artifacts / "harness_status" / date / "latest_run_id.txt"
            self.assertFalse(latest.exists())
            latest.write_text("daily-old\n", encoding="utf-8")
            new_event = build_event(
                run_id="daily-new", run_date=date, agent_id="harness_runner",
                status="ok", decision="pass", started_at="2026-10-15T08:00:00+00:00",
            )
            write_agent_event(new_event, artifacts_dir=artifacts)
            self.assertEqual(latest.read_text().strip(), "daily-new")

    def test_older_harness_cannot_displace_delivery_only_latest_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            date = "2026-10-15"
            delivery = build_event(
                run_id="daily-new", run_date=date, agent_id="daily_push",
                status="degraded", decision="stop",
                started_at="2026-10-15T08:00:00+00:00",
            )
            write_agent_event(delivery, artifacts_dir=artifacts)
            latest = artifacts / "harness_status" / date / "latest_run_id.txt"
            latest.write_text("daily-new\n", encoding="utf-8")
            older = build_event(
                run_id="daily-old", run_date=date, agent_id="harness_runner",
                status="ok", decision="pass", started_at="2026-10-15T07:00:00+00:00",
            )
            write_agent_event(older, artifacts_dir=artifacts)
            self.assertEqual(latest.read_text().strip(), "daily-new")

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
