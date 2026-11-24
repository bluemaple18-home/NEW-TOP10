"""驗證 daily publish wrapper guard 的公開 CLI 回歸行為。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import os
import signal
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = PROJECT_ROOT / "scripts" / "verify_daily_publish_wrapper_guards.py"
from scripts.verify_daily_publish_wrapper_guards import CATCH_UP_DATE, build_fake_project


class DailyPublishWrapperGuardsCliTest(unittest.TestCase):
    def test_receipt_preflight_runs_under_production_write_boundary(self) -> None:
        from scripts.storage_validation.boundary import owned_validation_paths, owned_write_contract

        root = Path(os.environ.get("TMP_ARTIFACT_ROOT", ""))
        self.assertTrue(root.is_absolute() and root.resolve(strict=True) == root,
                        "必須明示 canonical TMP_ARTIFACT_ROOT")
        contract = owned_write_contract(root)
        self.assertIsNotNone(contract, "必須由 --external-only --owned-root-writes-only lifecycle 啟動")
        self.assertEqual(owned_validation_paths(root), root)
        # fixture 與 parent 的唯一 native 寫入根完全相同，不接受較寬父目錄。
        evidence = root / "validation_evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "daily-wrapper-exact-owner-contract.json").write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        build_fake_project(root)
        (root / "tmp").mkdir(exist_ok=True)
        env = {**os.environ, "TOP10_RUN_DATE": CATCH_UP_DATE,
               "TMPDIR": str(root / "tmp")}
        result = subprocess.run(
            ["/bin/bash", str(root / "scripts" / "run_daily_publish.sh")],
            cwd=root, env=env, capture_output=True, text=True, check=False,
        )
        self.assertIn("開始收盤後 daily publish", result.stdout, result.stderr)

    def test_confirmed_send_recovers_event_without_regenerating_daily(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_fake_project(root)
            message = root / "artifacts" / f"clawd_publish_message_{CATCH_UP_DATE}.md"
            message.write_text("confirmed message\n", encoding="utf-8")
            receipt = root / "artifacts" / f"clawd_send_status_{CATCH_UP_DATE}.json"
            receipt.write_text(json.dumps({"status": "OK", "send_attempted": True,
                                           "dry_run": False}), encoding="utf-8")
            env = os.environ.copy()
            env["TOP10_RUN_DATE"] = CATCH_UP_DATE
            result = subprocess.run(["bash", str(root / "scripts" / "run_daily_publish.sh")],
                                    cwd=root, env=env, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(message.read_text(encoding="utf-8"), "confirmed message\n")
            self.assertFalse((root / "artifacts" / "automation_status.json").exists())
            event_args = json.loads((root / "artifacts" / "fake_event_args.json").read_text())
            self.assertIn("--recover-confirmed-send", event_args["args"])
            self.assertTrue((root / "artifacts" / "fake_ops_args.json").exists())

    def test_unresolved_send_preserves_message_before_daily_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_fake_project(root)
            message = root / "artifacts" / f"clawd_publish_message_{CATCH_UP_DATE}.md"
            message.write_text("original attempted message\n", encoding="utf-8")
            receipt = root / "artifacts" / f"clawd_send_status_{CATCH_UP_DATE}.json"
            receipt.write_text(json.dumps({"status": "DELIVERY_UNKNOWN", "send_attempted": True,
                                           "retry_allowed": False}), encoding="utf-8")
            env = os.environ.copy()
            env["TOP10_RUN_DATE"] = CATCH_UP_DATE
            result = subprocess.run(["bash", str(root / "scripts" / "run_daily_publish.sh")],
                                    cwd=root, env=env, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(message.read_text(encoding="utf-8"), "original attempted message\n")
            self.assertFalse((root / "artifacts" / "automation_status.json").exists())
            event_args = json.loads((root / "artifacts" / "fake_event_args.json").read_text())
            self.assertEqual(event_args["args"][event_args["args"].index("--status") + 1], "degraded")

    def test_untrusted_lock_environment_cannot_bypass_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_fake_project(root)
            env = os.environ.copy()
            env.update(TOP10_RUN_DATE=CATCH_UP_DATE, TOP10_PUBLISH_LOCK_HELD="1")
            env.pop("TOP10_PUBLISH_LOCK_FD", None)
            result = subprocess.run(["bash", str(root / "scripts" / "run_daily_publish.sh")],
                                    cwd=root, env=env, capture_output=True, check=False)
            self.assertEqual(result.returncode, 75)
            self.assertFalse((root / "artifacts" / "automation_status.json").exists())

    def test_parent_termination_keeps_lock_until_daily_child_exits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_fake_project(root)
            command = ["bash", str(root / "scripts" / "run_daily_publish.sh")]
            env = os.environ.copy()
            env.update(TOP10_RUN_DATE=CATCH_UP_DATE, FAKE_DAILY_SLEEP="2")
            first = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                marker = root / "artifacts" / "fake_daily_sleeping"
                deadline = time.monotonic() + 3
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists())
                first_daily_pid = int(marker.read_text())
                os.kill(first.pid, signal.SIGTERM)
                first.communicate(timeout=3)
                with self.assertRaises(ProcessLookupError):
                    os.kill(first_daily_pid, 0)
                second = subprocess.run(command, cwd=root, env=env, capture_output=True, check=False)
                self.assertEqual(second.returncode, 0)
            finally:
                if first.poll() is None:
                    first.terminate()
                    first.communicate(timeout=3)

    def test_concurrent_daily_wrapper_is_rejected_before_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_fake_project(root)
            command = ["bash", str(root / "scripts" / "run_daily_publish.sh")]
            env = os.environ.copy()
            env.update(TOP10_RUN_DATE=CATCH_UP_DATE, FAKE_DAILY_SLEEP="1")
            first = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                log = root / "logs"
                deadline = time.monotonic() + 3
                while not list(log.glob("daily_publish_*.log")) and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(list(log.glob("daily_publish_*.log")))
                second = subprocess.run(command, cwd=root, env=env, capture_output=True, check=False)
                self.assertNotEqual(second.returncode, 0)
                self.assertIn(b"overlap blocked", second.stderr)
            finally:
                first.communicate(timeout=10)
    def test_cli_covers_fake_dependencies(self) -> None:
        """fake event／ops 依賴須可觀測，且不得改變 send 的失敗碼。"""
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "daily_publish_wrapper_guards.json"
            completed = subprocess.run(
                [sys.executable, "-I", "-B", "-c",
                 "import runpy,sys,tempfile; from pathlib import Path; "
                 "tempfile.tempdir=str(Path(sys.argv[-1]).parent); sys.argv=sys.argv[1:]; "
                 "runpy.run_path(sys.argv[0],run_name='__main__')",
                 str(GUARD_SCRIPT), "--output", str(output)],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            details = output.read_text(encoding="utf-8") if output.exists() else "missing output"
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr + details)
            payload = json.loads(output.read_text(encoding="utf-8"))
            cases = {case["name"]: case for case in payload["cases"]}

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(payload["summary"]["failed_count"], 0)
        self.assertEqual(cases["send_failure_fails_publish"]["wrapper_exit"], 7)
        self.assertEqual(cases["delivery_unknown_marks_degraded"]["wrapper_exit"], 7)
        self.assertTrue(all(check["ok"] for case in cases.values() for check in case["checks"]))
