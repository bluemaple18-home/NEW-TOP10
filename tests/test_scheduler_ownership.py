"""驗證 daily scheduler 的單一 owner 防呆。"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.verify_scheduler_ownership import (
    EXPECTED_DAILY_START_CALENDAR,
    evaluate_ownership,
    validate_repo_daily_plist,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SchedulerOwnershipTests(unittest.TestCase):
    """文字 fixture 不依賴本機 launchctl 或 crontab 狀態。"""

    def test_launchd_only_is_go(self) -> None:
        report = evaluate_ownership('service = "com.new-top10.daily"', "")
        self.assertEqual("GO", report["status"])

    def test_cron_only_is_warning(self) -> None:
        report = evaluate_ownership("", "0 22 * * * cd /repo && bash scripts/run_daily.sh")
        self.assertEqual("WARNING", report["status"])

    def test_commented_cron_entry_is_not_an_owner(self) -> None:
        report = evaluate_ownership("", "# 0 22 * * * bash scripts/run_daily.sh")
        self.assertEqual("NO-GO", report["status"])

    def test_both_owners_are_no_go(self) -> None:
        report = evaluate_ownership("com.new-top10.daily", "bash scripts/run_daily_publish.sh")
        self.assertEqual("NO-GO", report["status"])

    def test_no_owner_is_no_go(self) -> None:
        report = evaluate_ownership("", "")
        self.assertEqual("NO-GO", report["status"])

    def test_legacy_cron_requires_explicit_override(self) -> None:
        completed = subprocess.run(
            ["bash", "scripts/setup_cron.sh"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("TOP10_ALLOW_LEGACY_CRON=1", completed.stdout)

    def test_legacy_override_shows_single_owner_warning(self) -> None:
        environment = os.environ | {"TOP10_ALLOW_LEGACY_CRON": "1"}
        completed = subprocess.run(
            ["bash", "scripts/setup_cron.sh"],
            cwd=PROJECT_ROOT,
            input="n\n",
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )
        self.assertEqual(0, completed.returncode)
        self.assertIn("正式 owner 仍為 launchd", completed.stdout)

    def test_repo_only_verifier_does_not_query_live_scheduler(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/verify_scheduler_ownership.py", "--repo-only"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("SCHEDULER_OWNERSHIP_GO", completed.stdout)

    def test_repo_daily_plist_is_weekday_only_at_1730(self) -> None:
        plist = PROJECT_ROOT / "scripts" / "com.new-top10.daily.plist"
        payload = plistlib.loads(plist.read_bytes())
        self.assertEqual([], validate_repo_daily_plist(payload))
        self.assertEqual(list(EXPECTED_DAILY_START_CALENDAR), payload["StartCalendarInterval"])

    def test_repo_daily_plist_rejects_wildcard_daily_calendar(self) -> None:
        payload = {
            "ProgramArguments": ["/bin/bash", "__PROJECT_DIR__/scripts/run_daily_publish.sh"],
            "StartCalendarInterval": {"Hour": 17, "Minute": 30},
        }
        errors = validate_repo_daily_plist(payload)
        self.assertIn("StartCalendarInterval must be an array for weekday-only scheduling", errors)
