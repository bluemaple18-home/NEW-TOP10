from __future__ import annotations

import base64
import json
import os
import plistlib
import shutil
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
    CHATGPT_URL_PART = "chatgpt.com/g/g-p-6a27bb719e708191bd6eefae64c7c08c/c/6a27bb97-8f80-8324-ab52-3f861a006ee3"

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

    def test_chatgpt_default_marker_is_consistent_and_environment_overridable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        default_expression = f'${{TOP10_CHATGPT_URL_PART:-{self.CHATGPT_URL_PART}}}'
        for relative_path in (
            "scripts/review_chatgpt_chrome.sh",
            "scripts/run_external_review_provider_preflight.sh",
            "scripts/run_external_review_host_runner.sh",
        ):
            contents = (repo_root / relative_path).read_text(encoding="utf-8")
            self.assertIn(default_expression, contents)
            self.assertNotIn("6a1ff7db268881918957ff493f2a915b", contents)

        adapter_contents = (repo_root / "scripts/review_chatgpt_chrome.sh").read_text(encoding="utf-8")
        override = "chatgpt.com/g/custom/c/override"
        self.assertIn(f'URL_PART="${{TOP10_CHATGPT_URL_PART:-{self.CHATGPT_URL_PART}}}"', adapter_contents)
        default_probe = self.probe_config("review_chatgpt_chrome.sh")
        self.assertEqual(self.CHATGPT_URL_PART, json.loads(default_probe.stdout)["target_url_part"])
        override_probe = self.probe_config("review_chatgpt_chrome.sh", {"TOP10_CHATGPT_URL_PART": override})
        self.assertEqual(override, json.loads(override_probe.stdout)["target_url_part"])

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

    def test_materialize_probe_js_test_seam_writes_only_to_override_root_without_sending(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        def files_under(path: Path) -> set[Path]:
            return {entry.relative_to(path) for entry in path.rglob("*") if entry.is_file()}

        with tempfile.TemporaryDirectory() as output_tmp, tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(output_tmp).resolve()
            tmp_root = Path(tmpdir).resolve()
            source_before = files_under(repo_root)
            tmp_before = files_under(tmp_root)
            for script_name, expected_markers in (
                ("review_chatgpt_chrome.sh", ["mode: \"probe\"", "hasSendButton"]),
                (
                    "review_gemini_chrome.sh",
                    [
                        "expectedTitle = decode",
                        base64.b64encode("盤後選股檢討報告".encode()).decode(),
                        base64.b64encode("風17 一年".encode()).decode(),
                        base64.b64encode("Pro".encode()).decode(),
                    ],
                ),
            ):
                completed = subprocess.run(
                    ["bash", f"scripts/{script_name}", "--materialize-probe-js-test-only"],
                    cwd=repo_root,
                    env=os.environ
                    | {
                        "TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": str(output_root),
                        "TMPDIR": str(tmp_root),
                        "TOP10_GEMINI_EXPECTED_TITLE": "盤後選股檢討報告",
                        "TOP10_GEMINI_EXPECTED_ACCOUNT": "風17 一年",
                        "TOP10_GEMINI_EXPECTED_PLAN": "Pro",
                    },
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                payload = json.loads(completed.stdout)
                js_file = Path(payload["js_file"])
                self.assertTrue(js_file.is_file())
                self.assertEqual(output_root, js_file.parent)
                self.assertEqual("probe_only", payload["mode"])
                self.assertIs(False, payload["review_packet_sent"])
                contents = js_file.read_text(encoding="utf-8")
                for marker in expected_markers:
                    self.assertIn(marker, contents)
                script_text = (repo_root / "scripts" / script_name).read_text(encoding="utf-8")
                marker = "  cat > \"$JS_FILE\" <<'JS'\n"
                start = script_text.index(marker, script_text.index("write_probe_js()")) + len(marker)
                default_contents = script_text[start : script_text.index("\nJS\n", start)] + "\n"
                default_contents = (
                    default_contents.replace("__EXPECTED_TITLE_B64__", base64.b64encode("盤後選股檢討報告".encode()).decode())
                    .replace("__EXPECTED_ACCOUNT_B64__", base64.b64encode("風17 一年".encode()).decode())
                    .replace("__EXPECTED_PLAN_B64__", base64.b64encode("Pro".encode()).decode())
                )
                self.assertEqual(default_contents, contents)

            self.assertEqual(source_before, files_under(repo_root))
            self.assertEqual(tmp_before, files_under(tmp_root))

    def test_materialize_probe_js_test_seam_requires_controlled_output_root(self) -> None:
        for script_name in ("review_chatgpt_chrome.sh", "review_gemini_chrome.sh"):
            completed = subprocess.run(
                ["bash", f"scripts/{script_name}", "--materialize-probe-js-test-only"],
                cwd=Path(__file__).resolve().parents[1],
                env=os.environ,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(64, completed.returncode)
            self.assertIn("requires TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT", completed.stderr)

    def test_chatgpt_collect_js_correlates_prompt_before_accepting_assistant(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is required to execute the browser collector JavaScript")

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as output_tmp:
            completed = subprocess.run(
                [
                    "bash",
                    "scripts/review_chatgpt_chrome.sh",
                    "--materialize-collect-js-test-only",
                    "--date",
                    "2026-08-03",
                ],
                cwd=repo_root,
                env=os.environ | {"TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": str(Path(output_tmp).resolve())},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            collect_js = Path(json.loads(completed.stdout)["js_file"]).read_text(encoding="utf-8")

        user_prompt = (
            "review_date=2026-08-03, provider=chatgpt, market=TW。 "
            '以下是已通過本地安全驗證的 review_packet 摘要：{"packet_date":"2026-08-03"}'
        )
        valid_assistant = '{"review":"' + ("完整回覆" * 220) + '"}'

        accepted = self.run_collect_js_fixture(
            collect_js,
            [
                {"role": "assistant", "text": "SPEC: Taiwan Stock Knowledge Graph (TSKG)\nold"},
                {"role": "user", "text": user_prompt},
                {"role": "assistant", "text": valid_assistant},
            ],
        )
        self.assertTrue(accepted["ok"])
        self.assertEqual(valid_assistant, accepted["raw_response"])
        self.assertEqual(1, accepted["correlation"]["selected_user_index"])
        self.assertEqual(2, accepted["correlation"]["selected_assistant_index"])

        prefix = self.run_collect_js_fixture(
            collect_js,
            [
                {"role": "user", "text": user_prompt},
                {"role": "assistant", "text": '{"review'},
            ],
        )
        self.assertFalse(prefix["ok"])
        self.assertEqual("", prefix["raw_response"])
        self.assertEqual("assistant_response_too_short", prefix["correlation"]["rejection_reason"])

        stale = self.run_collect_js_fixture(
            collect_js,
            [
                {"role": "user", "text": user_prompt},
                {"role": "assistant", "text": "SPEC: Taiwan Stock Knowledge Graph (TSKG)\n" + ("舊內容" * 260)},
            ],
        )
        self.assertFalse(stale["ok"])
        self.assertEqual("stale_tskg_response", stale["correlation"]["rejection_reason"])

        missing_correlation = self.run_collect_js_fixture(
            collect_js,
            [
                {"role": "user", "text": "unrelated prompt"},
                {"role": "assistant", "text": valid_assistant},
            ],
        )
        self.assertFalse(missing_correlation["ok"])
        self.assertEqual("assistant_after_correlated_user_missing", missing_correlation["correlation"]["rejection_reason"])

    def run_collect_js_fixture(self, collect_js: str, messages: list[dict[str, str]]) -> dict[str, object]:
        harness = f"""
const messages = {json.dumps(messages, ensure_ascii=False)};
class FakeNode {{
  constructor(row, index) {{
    this.row = row;
    this.index = index;
    this.innerText = row.text;
    this.textContent = row.text;
    this.id = `message-${{index}}`;
  }}
  getAttribute(name) {{
    if (name === 'data-message-author-role') return this.row.role;
    if (name === 'aria-label') return `${{this.row.role}} message`;
    if (name === 'data-testid') return `conversation-turn-${{this.index}}`;
    return null;
  }}
  closest() {{ return this; }}
  getBoundingClientRect() {{ return {{ width: 100, height: 20 }}; }}
}}
const nodes = messages.map((row, index) => new FakeNode(row, index));
globalThis.document = {{
  title: '股票 - 台股波段推薦分析',
  body: {{ innerText: messages.map((row) => row.text).join('\\n') }},
  querySelectorAll(selector) {{
    if (selector === '[data-message-author-role]') return nodes;
    return [];
  }}
}};
globalThis.location = {{ href: 'https://chatgpt.com/g/example/c/test-conversation' }};
globalThis.getComputedStyle = () => ({{ display: 'block', visibility: 'visible' }});
const result = {collect_js};
console.log(result);
"""
        completed = subprocess.run(["node", "-e", harness], text=True, capture_output=True, check=False)
        self.assertEqual(0, completed.returncode, completed.stderr)
        return json.loads(completed.stdout)


if __name__ == "__main__":
    unittest.main()
