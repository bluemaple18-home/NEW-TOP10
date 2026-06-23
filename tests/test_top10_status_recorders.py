from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.record_top10_daily_status_events import build_daily_events
from scripts.top10_agent_status import read_manifest, validate_event, write_agent_event


class Top10StatusRecorderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = read_manifest(Path("docs/architecture/top10_harness_team.dashboard.json"))

    def test_daily_status_builds_harness_events_without_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            status_path = artifacts / "automation_status.json"
            status = sample_automation_status(artifacts)
            status_path.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")

            events = build_daily_events(
                status=status,
                status_path=status_path,
                artifacts_dir=artifacts,
                run_date="2026-06-23",
                run_id="daily-2026-06-23",
            )

            self.assertEqual(
                [event["agent_id"] for event in events],
                [
                    "harness_runner",
                    "preflight",
                    "data_etl",
                    "data_quality_gate",
                    "ranking",
                    "anomaly_circuit_breaker",
                    "outcome_tracker",
                    "ops_reporter",
                ],
            )
            for event in events:
                self.assertEqual(validate_event(event, self.manifest), [])
                for key in ("input_refs", "artifact_paths"):
                    self.assertFalse(any(str(item).startswith("/Users/") for item in event[key]))
                    self.assertFalse(any(str(item).startswith("/private/") for item in event[key]))

            ranking = next(event for event in events if event["agent_id"] == "ranking")
            self.assertEqual(ranking["status"], "ok")
            self.assertEqual(ranking["decision"], "pass")
            ops = next(event for event in events if event["agent_id"] == "ops_reporter")
            self.assertEqual(ops["discord_channel"], "ops_progress_channel")

    def test_daily_events_can_be_written_and_rolled_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            status_path = artifacts / "automation_status.json"
            status = sample_automation_status(artifacts)
            for event in build_daily_events(
                status=status,
                status_path=status_path,
                artifacts_dir=artifacts,
                run_date="2026-06-23",
                run_id="daily-2026-06-23",
            ):
                write_agent_event(event, artifacts_dir=artifacts)

            event_path = artifacts / "harness_status" / "2026-06-23" / "daily-2026-06-23" / "events" / "ranking.json"
            self.assertTrue(event_path.exists())
            payload = json.loads(event_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["agent_id"], "ranking")


def sample_automation_status(artifacts: Path) -> dict:
    started = "2026-06-23T12:00:00+00:00"
    finished = "2026-06-23T12:10:00+00:00"
    ranking = artifacts / "ranking_2026-06-23.csv"
    decision_quality = artifacts / "decision_quality_2026-06-23.json"
    market_context = artifacts / "market_context_2026-06-23.json"
    return {
        "schema_version": "automation-status.v1",
        "run_date": "2026-06-23",
        "mode": "daily",
        "status": "OK",
        "dry_run": False,
        "started_at": started,
        "finished_at": finished,
        "errors": [],
        "steps": [
            step("resource_guard.daily", "OK"),
            step("daily.schema", "OK"),
            step("daily.run_date", "OK"),
            step("model.exists", "OK"),
            step("data.freshness.preflight", "OK"),
            step("etl", "OK"),
            step("data.validate", "OK"),
            step("data.freshness.after_etl", "OK"),
            step("ranking", "OK"),
            step("ranking.artifact", "OK", str(ranking)),
            step("candidate.persistence", "OK"),
            step("weekly.snapshot", "OK"),
            step("market.context", "OK"),
            step("decision.quality", "OK"),
            step("decision.quality.artifact", "OK", str(decision_quality)),
            step("daily.postcheck", "SKIPPED"),
        ],
        "metadata": {
            "ranking_artifact": str(ranking),
            "decision_quality_artifact": str(decision_quality),
            "market_context_artifact": str(market_context),
            "data_freshness": {
                "datasets": {
                    "features.parquet": {
                        "path": str(artifacts / "data" / "clean" / "features.parquet"),
                        "latest_date": "2026-06-23",
                    }
                }
            },
        },
    }


def step(name: str, status: str, message: str | None = None) -> dict:
    return {
        "name": name,
        "status": status,
        "message": message,
        "started_at": "2026-06-23T12:00:00+00:00",
        "finished_at": "2026-06-23T12:00:01+00:00",
        "exit_code": 0 if status == "OK" else None,
    }


if __name__ == "__main__":
    unittest.main()
