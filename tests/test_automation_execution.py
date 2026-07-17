from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from app.automation.execution import execute_command, normalize_command


class AutomationExecutionTest(unittest.TestCase):
    def test_normalize_python_uses_current_interpreter(self) -> None:
        self.assertEqual(
            normalize_command(["python", "-m", "app.pipeline_cli"], python_executable="/venv/python"),
            ["/venv/python", "-m", "app.pipeline_cli"],
        )

    def test_dry_run_never_calls_subprocess(self) -> None:
        def forbidden(*args, **kwargs):
            raise AssertionError("dry-run 不得執行 subprocess")

        times = iter(["start", "finish"])
        outcome = execute_command(
            ["python", "job.py"],
            python_executable="/venv/python",
            dry_run=True,
            cwd=Path("/tmp"),
            env={},
            now=lambda: next(times),
            runner=forbidden,
        )
        self.assertEqual(outcome.status, "DRY_RUN")
        self.assertIsNone(outcome.exit_code)

    def test_failure_is_data_for_caller_to_apply_policy(self) -> None:
        calls = []

        def failed(command, *, cwd, env):
            calls.append((command, cwd, env))
            return subprocess.CompletedProcess(command, 7)

        times = iter(["start", "finish"])
        outcome = execute_command(
            ["tool", "arg"],
            python_executable="/venv/python",
            dry_run=False,
            cwd=Path("/repo"),
            env={"KEY": "value"},
            now=lambda: next(times),
            runner=failed,
        )
        self.assertEqual(outcome.status, "FAILED")
        self.assertEqual(outcome.exit_code, 7)
        self.assertEqual(calls[0][0], ["tool", "arg"])


if __name__ == "__main__":
    unittest.main()
