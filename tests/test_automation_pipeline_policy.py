from __future__ import annotations

import unittest
from datetime import date

from app.automation.pipeline_policy import (
    apply_daily_default_pipeline_window,
    evaluate_resource_profile,
    pipeline_run_command,
    pipeline_window_override,
    resolve_resource_profile,
)


class AutomationPipelinePolicyTest(unittest.TestCase):
    def test_pipeline_window_and_command_table(self) -> None:
        cases = [
            {
                "name": "explicit_window",
                "start_date": "2026-01-01",
                "end_date": "2026-02-01",
                "lookback_days": 420,
                "today": date(2026, 5, 27),
                "expected_window": {"start_date": "2026-01-01", "end_date": "2026-02-01"},
            },
            {
                "name": "default_lookback",
                "start_date": None,
                "end_date": None,
                "lookback_days": 420,
                "today": date(2026, 5, 27),
                "expected_window": {"end_date": "2026-05-27", "start_date": "2025-04-02"},
            },
            {
                "name": "explicit_end_default_start",
                "start_date": None,
                "end_date": "2026-05-26",
                "lookback_days": 420,
                "today": date(2026, 5, 27),
                "expected_window": {"end_date": "2026-05-26", "start_date": "2025-04-01"},
            },
        ]

        for case in cases:
            with self.subTest(case["name"]):
                override = pipeline_window_override(
                    start_date=case["start_date"],
                    end_date=case["end_date"],
                )
                policy = apply_daily_default_pipeline_window(
                    override.as_dict(),
                    lookback_days_value=case["lookback_days"],
                    today=case["today"],
                )
                self.assertEqual(policy.as_dict(), case["expected_window"])
                expected_command = ["python", "-m", "app.pipeline_cli", "run"]
                if "start_date" in case["expected_window"]:
                    expected_command.extend(["--start-date", case["expected_window"]["start_date"]])
                if "end_date" in case["expected_window"]:
                    expected_command.extend(["--end-date", case["expected_window"]["end_date"]])
                self.assertEqual(pipeline_run_command(policy.as_dict()), tuple(expected_command))

    def test_resource_profile_guard_table(self) -> None:
        cases = [
            {
                "name": "local_safe_guard",
                "profile": "local_safe",
                "window": False,
                "expected": (True, True, True),
            },
            {
                "name": "local_safe_explicit_window",
                "profile": "local_safe",
                "window": True,
                "expected": (False, True, True),
            },
            {
                "name": "host_full",
                "profile": "host_full",
                "window": False,
                "expected": (False, False, False),
            },
        ]

        for case in cases:
            with self.subTest(case["name"]):
                policy = evaluate_resource_profile(
                    profile=case["profile"],
                    dry_run=False,
                    has_pipeline_window_override=case["window"],
                    allow_full_etl=False,
                    allow_heavy_retrain=False,
                    allow_heavy_monitor=False,
                )
                self.assertEqual(
                    (policy.block_daily, policy.block_retrain, policy.skip_heavy_monitor),
                    case["expected"],
                )

    def test_resource_profile_precedence_and_invalid_value(self) -> None:
        self.assertEqual(
            resolve_resource_profile(
                explicit_profile="HOST_FULL",
                env_profile="local_safe",
                config_profile="standard",
            ),
            "host_full",
        )
        with self.assertRaisesRegex(ValueError, "未知 resource profile：invalid"):
            resolve_resource_profile(
                explicit_profile=None,
                env_profile="invalid",
                config_profile="standard",
            )


if __name__ == "__main__":
    unittest.main()
