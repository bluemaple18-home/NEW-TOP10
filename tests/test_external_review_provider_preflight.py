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
    CHATGPT_URL_PART = "chatgpt.com/g/g-p-6a27bb719e708191bd6eefae64c7c08c-gu-piao/c/6a27bb97-8f80-8324-ab52-3f861a006ee3"

    def probe_config(self, script_name: str, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            return subprocess.run(
                ["bash", f"scripts/{script_name}", "--print-probe-config"],
                cwd=Path(__file__).resolve().parents[1],
                env=os.environ | {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": str(Path(tmp).resolve()),
                                  "TOP10_CHATGPT_EXPECTED_ACCOUNT": "Fixture User Plus",
                                  "TOP10_GEMINI_EXPECTED_ACCOUNT": "fixture@example.invalid",
                                  "TOP10_DAILY_PYTHON": sys.executable} | (environment or {}),
                text=True, capture_output=True, check=False,
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

    def test_chatgpt_default_marker_is_consistent_and_environment_overridable(self) -> None:
        default_probe = self.probe_config("review_chatgpt_chrome.sh")
        self.assertEqual(0, default_probe.returncode, default_probe.stdout + default_probe.stderr)
        self.assertEqual("https://" + self.CHATGPT_URL_PART, json.loads(default_probe.stdout)["target_url_part"])
        override = "chatgpt.com/g/custom/c/override"
        result = self.probe_config("review_chatgpt_chrome.sh", {"TOP10_CHATGPT_URL_PART": override})
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("https://" + override, json.loads(result.stdout)["target_url_part"])


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

    def test_browser_probe_requires_explicit_existing_output_root(self) -> None:
        for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
            completed = self.probe_config(script_name, {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": ""})
            self.assertNotEqual(0, completed.returncode)
            self.assertFalse(json.loads(completed.stdout)["ok"])
            self.assertIn("canonical", json.loads(completed.stdout)["reason"])


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
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("canonical", json.loads(completed.stdout)["reason"])


    def test_browser_probe_rejects_output_root_with_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            traversal_root = f"{Path(tmp).resolve()}/.."
            for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
                completed = self.probe_config(
                    script_name,
                    {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": traversal_root},
                )
                self.assertNotEqual(0, completed.returncode)
                self.assertIn("canonical", json.loads(completed.stdout)["reason"])


    def test_retired_javascript_materialization_options_fail_before_browser_access(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve()
            for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
                for option in ("--materialize-probe-js-test-only", "--materialize-collect-js-test-only"):
                    completed = subprocess.run(
                        ["bash", f"scripts/{script_name}", option], cwd=repo_root,
                        env=os.environ | {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": str(output)},
                        text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(2, completed.returncode, completed.stdout + completed.stderr)
                    self.assertIn("unrecognized arguments", completed.stderr)
            self.assertEqual([], list(output.iterdir()))


    # Owner 已明示恢復 AppleScript；移除綁死 MCP 實作名稱的靜態測試。

    # 同 marker、錯 user、packet mismatch 與結果未知只收件的可執行回歸，
    # 已轉到 test_external_review_mcp_adapter.mjs 的原生 adapter seam。





if __name__ == "__main__":
    unittest.main()
