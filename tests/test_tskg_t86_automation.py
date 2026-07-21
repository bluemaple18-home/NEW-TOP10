"""TSKG T86 daily automation wiring tests。"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.run_automation import AutomationRunner


class TskgT86AutomationTests(unittest.TestCase):
    def test_dry_run_reuses_t86_artifact_for_market_context(self) -> None:
        runner = AutomationRunner(mode="daily", dry_run=True)
        runner._latest_feature_date = lambda: "2026-07-17"  # type: ignore[method-assign]

        t86_path = runner._run_tskg_t86({"tskg_t86_enabled": True})
        runner._run_market_context({"market_context_enabled": True}, t86_path)

        steps = {step.name: step for step in runner.status.steps}
        self.assertEqual(steps["tskg.t86"].status, "DRY_RUN")
        self.assertIn("scripts/fetch_tskg_t86.py", steps["tskg.t86"].command or [])
        self.assertEqual(steps["market.context"].status, "DRY_RUN")
        command = steps["market.context"].command or []
        self.assertIn("--twse-t86-input", command)
        self.assertEqual(command[command.index("--twse-t86-input") + 1], str(t86_path))

    def test_disabled_t86_does_not_change_market_context_command(self) -> None:
        runner = AutomationRunner(mode="daily", dry_run=True)
        runner._latest_feature_date = lambda: "2026-07-17"  # type: ignore[method-assign]

        t86_path = runner._run_tskg_t86({"tskg_t86_enabled": False})
        runner._run_market_context({"market_context_enabled": True}, t86_path)

        self.assertIsNone(t86_path)
        command = next(
            step.command for step in runner.status.steps if step.name == "market.context"
        ) or []
        self.assertNotIn("--twse-t86-input", command)

    def test_failed_fetch_does_not_reuse_invalid_existing_snapshot(self) -> None:
        runner = AutomationRunner(mode="daily", dry_run=False)
        runner._latest_feature_date = lambda: "2026-07-17"  # type: ignore[method-assign]

        def fail_command(*args, **kwargs) -> None:
            runner._record_step("tskg.t86", "FAILED", message="synthetic failure")

        runner._run_command = fail_command  # type: ignore[method-assign]
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            artifact = project_root / "artifacts/tskg/t86/twse_t86_2026-07-17.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("{invalid", encoding="utf-8")

            with patch("scripts.run_automation.PROJECT_ROOT", project_root):
                result = runner._run_tskg_t86({"tskg_t86_enabled": True})

        self.assertIsNone(result)
        self.assertEqual(runner.status.steps[-1].name, "tskg.t86.artifact")
        self.assertEqual(runner.status.steps[-1].status, "FAILED")


if __name__ == "__main__":
    unittest.main()
