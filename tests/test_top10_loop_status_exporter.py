from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_top10_loop_status import build_summary, validate_summary


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class Top10LoopStatusExporterTest(unittest.TestCase):
    def test_exports_daily_rollup_as_primary_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            run_dir = artifacts / "harness_status" / "2026-07-01" / "daily-2026-07-01"
            write_json(
                run_dir / "rollup.json",
                {
                    "schema_version": "top10-agent-status-rollup.v1",
                    "run_date": "2026-07-01",
                    "run_id": "daily-2026-07-01",
                    "status": "ok",
                    "generated_at": "2026-07-01T09:58:46+00:00",
                    "summary": {"failed_count": 0, "missing_count": 0, "formal_task_attention_count": 0},
                    "agents": [
                        {
                            "agent_id": "ranking",
                            "status": "ok",
                            "failure_reason": None,
                            "next_action": None,
                        }
                    ],
                },
            )
            write_json(
                run_dir / "events" / "ranking.json",
                {
                    "agent_id": "ranking",
                    "finished_at": "2026-07-01T09:59:01+00:00",
                    "status": "ok",
                },
            )

            summary = build_summary(artifacts, run_date="2026-07-01")

            self.assertEqual(validate_summary(summary), [])
            self.assertEqual(summary["team_id"], "top10")
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["latest_run_id"], "daily-2026-07-01")
            self.assertEqual(summary["finished_at"], "2026-07-01T09:59:01+00:00")
            self.assertEqual(summary["blockers"], [])
            self.assertEqual(summary["refs"]["daily_rollup"], "artifacts/harness_status/2026-07-01/daily-2026-07-01/rollup.json")
            self.assertTrue(summary["metadata"]["exporter_is_read_only"])

    def test_fog_runs_do_not_override_daily_primary_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            daily = artifacts / "harness_status" / "2026-07-01" / "daily-2026-07-01"
            fog = artifacts / "harness_status" / "2026-07-01" / "fog-research-2026-07-01-010000-b1"
            write_json(
                daily / "rollup.json",
                {
                    "run_date": "2026-07-01",
                    "run_id": "daily-2026-07-01",
                    "status": "ok",
                    "generated_at": "2026-07-01T10:00:00+00:00",
                    "summary": {"failed_count": 0, "missing_count": 0, "formal_task_attention_count": 0},
                    "agents": [],
                },
            )
            write_json(
                fog / "rollup.json",
                {
                    "run_date": "2026-07-01",
                    "run_id": "fog-research-2026-07-01-010000-b1",
                    "status": "degraded",
                    "generated_at": "2026-07-01T10:05:00+00:00",
                    "summary": {"failed_count": 0, "missing_count": 12},
                    "agents": [],
                },
            )
            (artifacts / "harness_status" / "2026-07-01" / "latest_run_id.txt").write_text(
                "fog-research-2026-07-01-010000-b1\n",
                encoding="utf-8",
            )

            summary = build_summary(artifacts, run_date="2026-07-01")

            self.assertEqual(summary["latest_run_id"], "daily-2026-07-01")
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(len(summary["refs"]["research_rollups"]), 1)
            self.assertEqual(summary["refs"]["research_rollups"][0]["run_id"], "fog-research-2026-07-01-010000-b1")

    def test_missing_rollup_is_unknown_with_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_summary(Path(tmp), run_date="2026-07-01")

            self.assertEqual(validate_summary(summary), [])
            self.assertEqual(summary["status"], "unknown")
            self.assertIn("top10_harness_rollup_missing", summary["blockers"])

    def test_summary_rejects_local_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_summary(Path(tmp), run_date="2026-07-01")
            summary["refs"]["daily_rollup"] = "/Users/mattkuo/TOP10new/artifacts/harness_status/rollup.json"

            with self.assertRaisesRegex(ValueError, "local absolute"):
                validate_summary(summary)


if __name__ == "__main__":
    unittest.main()
