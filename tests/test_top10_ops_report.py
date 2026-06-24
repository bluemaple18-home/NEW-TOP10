from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_top10_ops_progress_message import render_ops_message
from scripts.send_top10_ops_report import write_ops_event


class Top10OpsReportTest(unittest.TestCase):
    def test_render_ops_message_includes_blocker_and_external_disagreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            rollup_path = artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "rollup.json"
            rollup_path.parent.mkdir(parents=True, exist_ok=True)
            rollup = sample_rollup()
            external = {
                "valid_provider_count": 2,
                "disagreements": [{"title": "2330 only flagged by gemini", "detail": "risk view opposite"}],
                "today_misses": [{"stock_id": "2317", "reason": "AI thinks setup is stronger than our list"}],
                "safety": {"needs_human_review": True},
            }

            message = render_ops_message(rollup, external, rollup_path=rollup_path, artifacts_dir=artifacts)

            self.assertIn("TOP10 工作進度 2026-06-24", message)
            self.assertIn("Blocker", message)
            self.assertIn("data_quality_gate", message)
            self.assertIn("2330 only flagged by gemini", message)
            self.assertIn("2317", message)
            self.assertIn("不能直接改 ranking", message)

    def test_write_ops_event_updates_rollup(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            event_dir = artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "events"
            event_dir.mkdir(parents=True, exist_ok=True)
            status = {
                "generated_at": "2026-06-24T12:00:00+00:00",
                "run_date": "2026-06-24",
                "run_id": "daily-2026-06-24",
                "status": "OK",
                "message_path": "ops_progress_message_2026-06-24.md",
                "rollup_path": "harness_status/2026-06-24/daily-2026-06-24/rollup.json",
                "output_path": "ops_progress_send_status_2026-06-24.json",
                "dry_run": False,
                "send_attempted": True,
                "exit_code": 0,
                "errors": [],
            }

            write_ops_event(status, artifacts_dir=artifacts, manifest_path=Path("docs/architecture/top10_harness_team.dashboard.json"))

            event_path = event_dir / "ops_reporter.json"
            self.assertTrue(event_path.exists())
            event = json.loads(event_path.read_text(encoding="utf-8"))
            self.assertEqual(event["agent_id"], "ops_reporter")
            self.assertEqual(event["status"], "ok")
            self.assertEqual(event["discord_channel"], "ops_progress_channel")
            latest = artifacts / "harness_status" / "2026-06-24" / "latest_rollup.json"
            self.assertTrue(latest.exists())


def sample_rollup() -> dict:
    return {
        "run_date": "2026-06-24",
        "run_id": "daily-2026-06-24",
        "status": "failed",
        "summary": {
            "agent_count": 12,
            "event_count": 8,
            "failed_count": 1,
            "warning_count": 1,
            "missing_count": 3,
        },
        "agents": [
            {
                "agent_id": "data_quality_gate",
                "label": "data_quality_gate",
                "status": "failed",
                "failure_reason": "coverage below threshold",
                "next_action": "do not publish ranking until data is repaired",
            },
            {
                "agent_id": "external_review_harness",
                "label": "external_review_harness",
                "status": "pending",
                "next_action": "wait for daily OK before external review",
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
