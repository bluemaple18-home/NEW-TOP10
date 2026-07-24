"""Overlay append-only shadow daily automation wiring tests。"""

from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.run_automation import AutomationRunner
from scripts import run_overlay_shadow_daily_monitor


class OverlayShadowDailyAutomationTests(unittest.TestCase):
    def test_enabled_dry_run_records_research_command(self) -> None:
        runner = AutomationRunner(mode="daily", dry_run=True)
        runner._run_overlay_append_only_shadow({"overlay_append_only_shadow_enabled": True})

        step = runner.status.steps[-1]
        self.assertEqual(step.name, "overlay_append_only.shadow")
        self.assertEqual(step.status, "DRY_RUN")
        self.assertIn("scripts/run_overlay_shadow_daily_monitor.py", step.command or [])

    def test_disabled_monitor_is_skipped(self) -> None:
        runner = AutomationRunner(mode="daily", dry_run=True)
        runner._run_overlay_append_only_shadow({"overlay_append_only_shadow_enabled": False})

        step = runner.status.steps[-1]
        self.assertEqual(step.name, "overlay_append_only.shadow")
        self.assertEqual(step.status, "SKIPPED")

    def test_monitor_failure_is_allow_failure_and_does_not_raise(self) -> None:
        runner = AutomationRunner(mode="daily", dry_run=False)
        captured: dict[str, object] = {}

        def fail_command(name, command, **kwargs) -> None:
            captured["allow_failure"] = kwargs.get("allow_failure")
            runner._record_step(name, "FAILED", message="synthetic research failure")

        runner._run_command = fail_command  # type: ignore[method-assign]
        with TemporaryDirectory() as tmpdir:
            with patch("scripts.run_automation.PROJECT_ROOT", Path(tmpdir)):
                runner._run_overlay_append_only_shadow({"overlay_append_only_shadow_enabled": True})

        self.assertIs(captured["allow_failure"], True)
        self.assertEqual(runner.status.steps[-1].name, "overlay_append_only.shadow.artifact")
        self.assertEqual(runner.status.steps[-1].status, "WARN")

    def test_component_failure_writes_partial_research_receipt(self) -> None:
        with TemporaryDirectory() as tmpdir:
            status_path = Path(tmpdir) / "status.json"
            args = SimpleNamespace(
                features="features.parquet",
                industry_map="industry.csv",
                regime_history="regime.json",
                regime_extension="extension.json",
                chip_config="chip.json",
                chip_ledger="chip-ledger.json",
                event_config="event.json",
                event_ledger="event-ledger.json",
                volume_climax_config="volume.json",
                volume_climax_ledger="volume-ledger.json",
                status_output=str(status_path),
            )
            component_results = [
                {"exit_code": 0, "result": {"status": "OK"}, "stderr_tail": []},
                {"exit_code": 0, "result": {"status": "OK"}, "stderr_tail": []},
                {"exit_code": 1, "result": None, "stderr_tail": ["corrupt ledger"]},
            ]
            with (
                patch.object(run_overlay_shadow_daily_monitor, "parse_args", return_value=args),
                patch.object(
                    run_overlay_shadow_daily_monitor,
                    "update_regime_history",
                    return_value={"status": "NO_NEW_REGIME_DATES"},
                ),
                patch.object(
                    run_overlay_shadow_daily_monitor,
                    "run_json_command",
                    side_effect=component_results,
                ),
            ):
                exit_code = run_overlay_shadow_daily_monitor.main()

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["status"], "PARTIAL")
            self.assertEqual(payload["failed_components"], ["volume_climax"])
            self.assertFalse(payload["promotion_allowed"])
            self.assertFalse(payload["changes_production_ranking"])


if __name__ == "__main__":
    unittest.main()
