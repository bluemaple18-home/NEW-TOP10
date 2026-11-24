from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import scripts.run_automation as automation


class AutomationStatusContractTest(unittest.TestCase):
    def test_daily_missing_market_reference_stops_before_etl(self) -> None:
        """必要市場參考檔缺失時，Daily 應在 ETL 之前明確失敗。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = automation.AutomationRunner(mode="daily", dry_run=True)
            runner.runtime_paths = automation.RuntimePaths(root, root, root)
            runner._record_model_existence = lambda: None
            with self.assertRaisesRegex(RuntimeError, "市場參考檔缺失"):
                runner._daily_preflight()
            self.assertFalse(any(step.name == "etl" for step in runner.status.steps))

            reference = root / "data" / "reference" / "tradable_universe.csv"
            reference.parent.mkdir(parents=True)
            reference.write_text(
                "stock_id,market_type,is_active,is_etf\n"
                "2330,twse,true,false\n"
                "6488,tpex,true,false\n",
                encoding="utf-8",
            )
            runner._record_data_freshness = lambda *args, **kwargs: None
            runner._daily_preflight()
            self.assertTrue(any(step.name == "daily.market_reference" for step in runner.status.steps))

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

    def test_daily_keeps_identical_canonical_and_dated_statuses(self) -> None:
        for status in ("OK", "FAILED", "SKIPPED"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                original_status_path = automation.STATUS_PATH
                original_project_root = automation.PROJECT_ROOT
                try:
                    automation.PROJECT_ROOT = Path(tmp)
                    automation.STATUS_PATH = Path(tmp) / "artifacts" / "automation_status.json"
                    runner = automation.AutomationRunner(mode="daily", run_date="2026-06-25")
                    runner._record_step("daily.smoke", status)
                    runner.status.status = status
                    runner._write_status()

                    dated_path = automation.STATUS_PATH.with_name("automation_status_2026-06-25.json")
                    canonical_text = automation.STATUS_PATH.read_text(encoding="utf-8")
                    dated_text = dated_path.read_text(encoding="utf-8")
                    canonical_payload = json.loads(canonical_text)
                    self.assertEqual(canonical_text, dated_text)
                    self.assertEqual(canonical_payload["mode"], "daily")
                    self.assertEqual(canonical_payload["run_date"], "2026-06-25")
                    self.assertEqual(canonical_payload["status"], status)
                    self.assertEqual(list(automation.STATUS_PATH.parent.glob(".*.tmp")), [])
                finally:
                    automation.STATUS_PATH = original_status_path
                    automation.PROJECT_ROOT = original_project_root


if __name__ == "__main__":
    unittest.main()
