"""驗證 daily publish wrapper guard 的公開 CLI 回歸行為。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = PROJECT_ROOT / "scripts" / "verify_daily_publish_wrapper_guards.py"


class DailyPublishWrapperGuardsCliTest(unittest.TestCase):
    def test_cli_covers_fake_dependencies(self) -> None:
        """fake event／ops 依賴須可觀測，且不得改變 send 的失敗碼。"""
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "daily_publish_wrapper_guards.json"
            completed = subprocess.run(
                [sys.executable, str(GUARD_SCRIPT), "--output", str(output)],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            cases = {case["name"]: case for case in payload["cases"]}

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(payload["summary"]["failed_count"], 0)
        self.assertEqual(cases["send_failure_fails_publish"]["wrapper_exit"], 7)
        self.assertTrue(all(check["ok"] for case in cases.values() for check in case["checks"]))
