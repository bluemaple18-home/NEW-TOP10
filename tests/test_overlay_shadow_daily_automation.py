"""Overlay append-only shadow daily automation wiring tests。"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.run_automation import AutomationRunner


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


if __name__ == "__main__":
    unittest.main()
