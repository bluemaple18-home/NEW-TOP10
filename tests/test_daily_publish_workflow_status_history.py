from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verify_daily_publish_workflow as verifier


class DailyPublishWorkflowStatusHistoryTest(unittest.TestCase):
    def test_main_with_date_uses_historical_snapshot_fixture(self) -> None:
        run_date = "2026-07-09"
        with tempfile.TemporaryDirectory() as tmp:
            artifacts_dir = Path(tmp) / "artifacts"
            artifacts_dir.mkdir()
            output_path = Path(tmp) / "verification.json"
            ranking_path = artifacts_dir / f"ranking_{run_date}.csv"
            report_path = artifacts_dir / f"daily_report_{run_date}.json"
            payload_path = artifacts_dir / f"clawd_publish_payload_{run_date}.json"
            message_path = artifacts_dir / f"clawd_publish_message_{run_date}.md"
            ranking_path.write_text("stock_id\n2330\n", encoding="utf-8")
            self._write_json(report_path, {"run_date": run_date})
            self._write_json(
                payload_path,
                {
                    "ranking_date": run_date,
                    "delivery": {"status": "READY_FOR_CLAWD"},
                },
            )
            message_path.write_text(f"# NEW-TOP10 {run_date}\n", encoding="utf-8")
            self._write_json(
                artifacts_dir / "automation_status.json",
                {"run_date": "2026-07-12", "status": "SKIPPED"},
            )
            self._write_json(
                artifacts_dir / f"automation_status_{run_date}.json",
                {
                    "run_date": run_date,
                    "status": "OK",
                    "metadata": {
                        "ranking_artifact": str(ranking_path),
                        "daily_report_artifact": str(report_path),
                        "clawd_publish_payload": str(payload_path),
                        "clawd_publish_message": str(message_path),
                    },
                },
            )

            with (
                patch.object(verifier, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(
                    sys,
                    "argv",
                    ["verify_daily_publish_workflow.py", "--date", run_date, "--output", str(output_path)],
                ),
            ):
                exit_code = verifier.main()

            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "OK")
            self.assertEqual(
                result["details"]["automation_status"]["path"],
                str(artifacts_dir / f"automation_status_{run_date}.json"),
            )

    def test_status_source_table(self) -> None:
        cases = [
            {
                "name": "same_day_latest",
                "requested_date": None,
                "latest": {"run_date": "2026-07-13", "status": "OK"},
                "snapshots": {},
                "expected_date": "2026-07-13",
                "expected_status": "OK",
                "expected_name": "automation_status.json",
            },
            {
                "name": "historical_dated",
                "requested_date": "2026-07-09",
                "latest": {"run_date": "2026-07-11", "status": "OK"},
                "snapshots": {"2026-07-09": "OK"},
                "expected_date": "2026-07-09",
                "expected_status": "OK",
                "expected_name": "automation_status_2026-07-09.json",
            },
            {
                "name": "weekend_overwrite",
                "requested_date": "2026-07-09",
                "latest": {"run_date": "2026-07-12", "status": "SKIPPED"},
                "snapshots": {"2026-07-09": "OK"},
                "expected_date": "2026-07-09",
                "expected_status": "OK",
                "expected_name": "automation_status_2026-07-09.json",
            },
            {
                "name": "failed_snapshot",
                "requested_date": "2026-07-08",
                "latest": {"run_date": "2026-07-13", "status": "OK"},
                "snapshots": {"2026-07-08": "FAILED"},
                "expected_date": "2026-07-08",
                "expected_status": "FAILED",
                "expected_name": "automation_status_2026-07-08.json",
            },
            {
                "name": "skipped_snapshot",
                "requested_date": "2026-07-12",
                "latest": {"run_date": "2026-07-13", "status": "OK"},
                "snapshots": {"2026-07-12": "SKIPPED"},
                "expected_date": "2026-07-12",
                "expected_status": "SKIPPED",
                "expected_name": "automation_status_2026-07-12.json",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]), tempfile.TemporaryDirectory() as tmp:
                original_artifacts_dir = verifier.ARTIFACTS_DIR
                try:
                    verifier.ARTIFACTS_DIR = Path(tmp)
                    self._write_json(Path(tmp) / "automation_status.json", case["latest"])
                    for run_date, status in case["snapshots"].items():
                        self._write_json(
                            Path(tmp) / f"automation_status_{run_date}.json",
                            {"run_date": run_date, "status": status},
                        )

                    errors: list[str] = []
                    payload, source_path = verifier.load_daily_status(case["requested_date"], errors)

                    self.assertEqual(errors, [])
                    self.assertEqual(payload["run_date"], case["expected_date"])
                    self.assertEqual(payload["status"], case["expected_status"])
                    self.assertEqual(source_path.name, case["expected_name"])
                finally:
                    verifier.ARTIFACTS_DIR = original_artifacts_dir

    def test_missing_historical_snapshot_does_not_fall_back_to_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_artifacts_dir = verifier.ARTIFACTS_DIR
            try:
                verifier.ARTIFACTS_DIR = Path(tmp)
                self._write_json(
                    Path(tmp) / "automation_status.json",
                    {"run_date": "2026-07-12", "status": "SKIPPED"},
                )

                errors: list[str] = []
                payload, source_path = verifier.load_daily_status("2026-07-09", errors)

                self.assertEqual(payload, {})
                self.assertEqual(source_path.name, "automation_status_2026-07-09.json")
                self.assertTrue(any("historical status unavailable" in error for error in errors))
            finally:
                verifier.ARTIFACTS_DIR = original_artifacts_dir

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
