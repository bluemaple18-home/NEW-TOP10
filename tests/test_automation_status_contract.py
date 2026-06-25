from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import scripts.run_automation as automation


class AutomationStatusContractTest(unittest.TestCase):
    def test_monitor_does_not_overwrite_daily_automation_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_status_path = automation.STATUS_PATH
            try:
                automation.STATUS_PATH = Path(tmp) / "artifacts" / "automation_status.json"
                runner = automation.AutomationRunner(mode="monitor", run_date="2026-06-25")
                runner._record_step("monitor.smoke", "OK")
                runner.status.status = "OK"
                runner._write_status()

                self.assertFalse(automation.STATUS_PATH.exists())
                monitor_path = automation.STATUS_PATH.with_name("monitor_automation_status.json")
                self.assertTrue(monitor_path.exists())
                payload = json.loads(monitor_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["mode"], "monitor")
                self.assertEqual(payload["status"], "OK")
            finally:
                automation.STATUS_PATH = original_status_path

    def test_daily_keeps_canonical_automation_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_status_path = automation.STATUS_PATH
            original_project_root = automation.PROJECT_ROOT
            try:
                automation.PROJECT_ROOT = Path(tmp)
                automation.STATUS_PATH = Path(tmp) / "artifacts" / "automation_status.json"
                runner = automation.AutomationRunner(mode="daily", run_date="2026-06-25")
                runner._record_step("daily.smoke", "OK")
                runner.status.status = "OK"
                runner._write_status()

                self.assertTrue(automation.STATUS_PATH.exists())
                payload = json.loads(automation.STATUS_PATH.read_text(encoding="utf-8"))
                self.assertEqual(payload["mode"], "daily")
                self.assertEqual(payload["run_date"], "2026-06-25")
            finally:
                automation.STATUS_PATH = original_status_path
                automation.PROJECT_ROOT = original_project_root


if __name__ == "__main__":
    unittest.main()
