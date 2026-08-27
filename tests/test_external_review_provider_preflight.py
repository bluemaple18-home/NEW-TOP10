from __future__ import annotations

import json
import os
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts import preflight_external_review_providers as preflight
from scripts.run_external_review_host_runner import CommandResult, provider_preflight_reason, provider_probe_command


class ExternalReviewProviderPreflightTest(unittest.TestCase):
    def probe_config(self, script_name: str, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", f"scripts/{script_name}", "--print-probe-config"],
            cwd=Path(__file__).resolve().parents[1],
            env=os.environ | (environment or {}),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_chatgpt_session_expired_is_blocked_before_submit(self) -> None:
        reason = provider_preflight_reason(
            provider="chatgpt",
            result=CommandResult(command=["probe"], exit_code=0, stdout="", stderr=""),
            payload={
                "ok": True,
                "hasComposer": True,
                "url": "https://chatgpt.com/g/x/c/y",
                "bodySample": "你的工作階段已過期 請重新登入以繼續使用應用程式。",
            },
        )

        self.assertEqual(reason, "session_expired")

    def test_gemini_requires_exact_conversation_id(self) -> None:
        reason = provider_preflight_reason(
            provider="gemini",
            result=CommandResult(command=["probe"], exit_code=0, stdout="", stderr=""),
            payload={
                "ok": True,
                "hasComposer": True,
                "url": "https://gemini.google.com/app",
                "bodySample": "ready",
            },
        )

        self.assertEqual(reason, "gemini_conversation_id_missing")

    def test_gemini_exact_conversation_id_passes(self) -> None:
        reason = provider_preflight_reason(
            provider="gemini",
            result=CommandResult(command=["probe"], exit_code=0, stdout="", stderr=""),
            payload={
                "ok": True,
                "hasComposer": True,
                "url": "https://gemini.google.com/app/ea58b54eef550ded?hl=zh-TW",
                "bodySample": "ready",
            },
        )

        self.assertIsNone(reason)

    def test_preflight_emits_structured_blocked_without_a_review_packet(self) -> None:
        results = {
            "chatgpt": {
                "status": "FAILED",
                "reason": "probe_command_failed",
                "command": ["bash", "scripts/review_chatgpt_chrome.sh", "probe"],
                "exit_code": 1,
                "url": None,
                "title": None,
                "has_composer": None,
                "has_send_button": None,
                "stderr_tail": "Not authorized to send Apple events to Google Chrome.",
            },
            "gemini": {
                "status": "FAILED",
                "reason": "session_expired",
                "command": ["bash", "scripts/review_gemini_chrome.sh", "probe"],
                "exit_code": 0,
                "url": "https://gemini.google.com/app/example",
                "title": "Gemini",
                "has_composer": True,
                "has_send_button": True,
                "stderr_tail": "",
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "preflight.json"
            with patch.object(preflight, "run_provider_preflight", side_effect=lambda **kwargs: results[kwargs["provider"]]):
                self.assertEqual(1, preflight.main(["--date", "2026-08-27", "--output", str(output)]))

            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual("BLOCKED", payload["status"])
        self.assertTrue(all(row["review_packet_sent"] is False for row in payload["checks"]))
        self.assertEqual("runtime_authority", payload["checks"][0]["blocker"]["kind"])
        self.assertEqual("provider_session", payload["checks"][1]["blocker"]["kind"])

    def test_preflight_emits_pass_only_when_each_provider_is_ready(self) -> None:
        ready = {
            "status": "OK",
            "reason": None,
            "command": ["bash", "provider", "probe"],
            "exit_code": 0,
            "url": "https://provider.example/conversation",
            "title": "provider",
            "has_composer": True,
            "has_send_button": True,
            "stderr_tail": "",
        }

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "preflight.json"
            with patch.object(preflight, "run_provider_preflight", return_value=ready):
                self.assertEqual(0, preflight.main(["--date", "2026-08-27", "--output", str(output)]))

            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual("PASS", payload["status"])
        self.assertEqual(["PASS", "PASS"], [row["status"] for row in payload["checks"]])

    def test_probe_command_removes_packet_arguments_before_calling_adapter(self) -> None:
        command = provider_probe_command(
            "bash scripts/review_chatgpt_chrome.sh --date {date} --packet {packet}"
        )

        self.assertEqual(["bash", "scripts/review_chatgpt_chrome.sh", "probe"], command)

    def test_source_plist_uses_guarded_1740_non_load_entrypoint(self) -> None:
        plist_path = Path(__file__).resolve().parents[1] / "scripts" / "com.new-top10.external-review-preflight.plist"
        payload = plistlib.loads(plist_path.read_bytes())

        self.assertEqual("com.new-top10.external-review-preflight", payload["Label"])
        self.assertEqual({"Hour": 17, "Minute": 40}, payload["StartCalendarInterval"])
        self.assertIs(False, payload["RunAtLoad"])
        self.assertEqual(
            [
                "/bin/bash",
                "__PROJECT_DIR__/scripts/run_with_storage_guard.sh",
                "external-review-preflight",
                "/bin/bash",
                "__PROJECT_DIR__/scripts/run_external_review_provider_preflight.sh",
            ],
            payload["ProgramArguments"],
        )

    def test_browser_probe_default_output_root_remains_project_artifacts(self) -> None:
        expected = str((Path(__file__).resolve().parents[1] / "artifacts" / "external_review").resolve())
        for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
            completed = self.probe_config(script_name)
            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(expected, payload["output_root"])
            self.assertEqual("probe_only", payload["mode"])
            self.assertIs(False, payload["review_packet_sent"])

    def test_browser_probe_uses_existing_sandbox_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = str(Path(tmp).resolve())
            for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
                completed = self.probe_config(
                    script_name,
                    {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": expected},
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertEqual(expected, payload["output_root"])
                self.assertIs(False, payload["review_packet_sent"])

    def test_browser_probe_rejects_nonexistent_output_root_before_provider_access(self) -> None:
        missing = str(Path(tempfile.gettempdir()) / "top10-missing-output-root")
        for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
            completed = self.probe_config(
                script_name,
                {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": missing},
            )
            self.assertEqual(64, completed.returncode)
            self.assertIn("existing absolute non-root directory", completed.stderr)

    def test_browser_probe_rejects_output_root_with_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            traversal_root = f"{Path(tmp).resolve()}/.."
            for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
                completed = self.probe_config(
                    script_name,
                    {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": traversal_root},
                )
                self.assertEqual(64, completed.returncode)
                self.assertIn("must not contain symlink or traversal", completed.stderr)


if __name__ == "__main__":
    unittest.main()
