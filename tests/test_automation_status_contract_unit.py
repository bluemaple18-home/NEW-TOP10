from __future__ import annotations

import unittest
from dataclasses import asdict
from pathlib import Path

import scripts.run_automation as automation
from app.automation import status_contract


class AutomationStatusContractUnitTest(unittest.TestCase):
    def test_status_output_path_table(self) -> None:
        canonical = Path("/tmp/artifacts/automation_status.json")
        cases = [
            ("daily", False, "automation_status.json"),
            ("monitor", False, "monitor_automation_status.json"),
            ("retrain", False, "retrain_automation_status.json"),
            ("reference", False, "reference_automation_status.json"),
            ("daily", True, "automation_status_dry_run.json"),
            ("monitor", True, "automation_status_dry_run.json"),
        ]

        for mode, dry_run, expected_name in cases:
            with self.subTest(mode=mode, dry_run=dry_run):
                self.assertEqual(
                    status_contract.status_output_path(canonical, mode=mode, dry_run=dry_run),
                    canonical.with_name(expected_name),
                )

    def test_runner_keeps_public_contract_imports(self) -> None:
        self.assertIs(automation.StepResult, status_contract.StepResult)
        self.assertIs(automation.AutomationStatus, status_contract.AutomationStatus)
        self.assertEqual(automation.STATUS_SCHEMA_VERSION, "daily-run-status.v1")

    def test_dataclass_payload_golden_is_unchanged(self) -> None:
        status = status_contract.AutomationStatus(
            schema_version="daily-run-status.v1",
            mode="daily",
            status="OK",
            dry_run=False,
            started_at="2026-07-13T00:00:00+00:00",
            run_date="2026-07-13",
            finished_at="2026-07-13T00:01:00+00:00",
            steps=[
                status_contract.StepResult(
                    name="daily.smoke",
                    status="OK",
                    command=["python", "smoke.py"],
                    message="done",
                    started_at="2026-07-13T00:00:10+00:00",
                    finished_at="2026-07-13T00:00:11+00:00",
                    exit_code=0,
                )
            ],
            metadata={"trigger": "manual"},
        )

        self.assertEqual(
            asdict(status),
            {
                "schema_version": "daily-run-status.v1",
                "mode": "daily",
                "status": "OK",
                "dry_run": False,
                "started_at": "2026-07-13T00:00:00+00:00",
                "run_date": "2026-07-13",
                "finished_at": "2026-07-13T00:01:00+00:00",
                "skip_reason": None,
                "steps": [
                    {
                        "name": "daily.smoke",
                        "status": "OK",
                        "command": ["python", "smoke.py"],
                        "message": "done",
                        "started_at": "2026-07-13T00:00:10+00:00",
                        "finished_at": "2026-07-13T00:00:11+00:00",
                        "exit_code": 0,
                    }
                ],
                "errors": [],
                "metadata": {"trigger": "manual"},
            },
        )

    def test_summary_projection_matches_legacy_golden_and_key_order(self) -> None:
        source = {
            "status": "OK",
            "started_at": "2026-07-13T00:00:00+00:00",
            "finished_at": "2026-07-13T00:01:00+00:00",
            "skip_reason": None,
            "errors": [],
            "steps": [
                {
                    "name": "daily.smoke",
                    "status": "OK",
                    "command": None,
                    "message": "done",
                    "started_at": "a",
                    "finished_at": "b",
                    "exit_code": 0,
                }
            ],
            "metadata": {"trigger": "manual"},
        }
        expected = {
            "schema_version": "daily-run-status.v1",
            "run_date": "2026-07-13",
            "mode": "daily",
            "status": "OK",
            "dry_run": False,
            "skip_reason": None,
            "started_at": "2026-07-13T00:00:00+00:00",
            "finished_at": "2026-07-13T00:01:00+00:00",
            "errors": [],
            "step_summary": [
                {
                    "name": "daily.smoke",
                    "status": "OK",
                    "message": "done",
                    "exit_code": 0,
                }
            ],
            "metadata": {"trigger": "manual"},
        }

        actual = status_contract.automation_summary_payload(
            source,
            run_date="2026-07-13",
            mode="daily",
            dry_run=False,
        )

        self.assertEqual(actual, expected)
        self.assertEqual(list(actual), list(expected))
        self.assertEqual(list(actual["step_summary"][0]), list(expected["step_summary"][0]))


if __name__ == "__main__":
    unittest.main()
