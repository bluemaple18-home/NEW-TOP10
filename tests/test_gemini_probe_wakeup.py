"""Gemini 冷分頁的離線事件順序與 fail-closed 契約。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts import run_external_review_host_runner as runner
from scripts import preflight_external_review_providers as preflight


ROOT = Path(__file__).resolve().parents[1]
FAKE = r'''
import json, os, sys
from pathlib import Path
source = sys.stdin.read() if sys.argv[1] == "-" else "\n".join(sys.argv[1:])
if sys.argv[1] == "-":
    assert sys.argv[2] == os.environ["TOP10_GEMINI_BROWSER_APP"]
    assert 'set browserName to item 1 of argv' in source
    assert sys.argv[3] == "https://gemini.google.com/app/ea58b54eef550ded"
log = Path(os.environ["FAKE_LOG"])
for phase in ("activate", "ready", "execute"):
    if "-- phase: " + phase in source:
        (log.parent / (phase + ".applescript")).write_text(source)
events = json.loads(log.read_text()) if log.exists() else []
scenario = os.environ.get("FAKE_SCENARIO", "cold")
def fail(message):
    log.write_text(json.dumps(events))
    print(message, file=sys.stderr)
    sys.exit(1)
if "-- phase: activate" in source:
    assert "execute" not in source
    assert "activate" in source and "set active tab index" in source
    events.append("activate")
    assert "if matches is not 1 then error" in source
    assert "if URL of t is targetURL" in source
    if scenario == "activate_timeout":
        fail("AppleEvent timed out (-1712)")
    if scenario == "ambiguous":
        fail("Gemini exact target missing or ambiguous")
    print("41\t73")
elif "-- phase: ready" in source:
    assert events and events[0] == "activate"
    assert sys.argv[4:6] == ["41", "73"]
    assert "loading of t" in source and "execute" not in source
    assert "window id (item 3" in source and "whose id is (item 4" in source
    assert "if URL of t is not targetURL then error" in source
    if scenario == "ready_timeout":
        events.append("loading")
        fail("AppleEvent timed out (-1712)")
    if scenario == "ready_hang":
        import time
        events.append("loading")
        log.write_text(json.dumps(events))
        time.sleep(30)
    if scenario == "identity_changed":
        fail("Gemini target URL changed")
    if scenario == "loading_forever":
        events.append("loading")
        log.write_text(json.dumps(events))
        print("true")
        sys.exit(0)
    events.append("loading" if "loading" not in events else "ready")
    print("true" if events[-1] == "loading" else "false")
else:
    events.append("execute")
    log.write_text(json.dumps(events))
    if "ready" not in events:
        print("JavaScript AppleEvent timed out (-1712)", file=sys.stderr)
        sys.exit(1)
    assert sys.argv[4:6] == ["41", "73"]
    assert "if loading of t then error" in source
    if scenario == "execute_timeout":
        fail("JavaScript AppleEvent timed out (-1712)")
    if scenario == "loading_again":
        fail("Gemini target is still loading")
    print(json.dumps({"ok": True, "hasComposer": True, "url": "https://gemini.google.com/app/ea58b54eef550ded"}))
log.write_text(json.dumps(events))
'''


class GeminiProbeWakeupTest(unittest.TestCase):
    def run_probe(self, scenario="cold", browser="Google Chrome", native_compile=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fake = root / "osascript"
            fake.write_text(f"#!{sys.executable}\n" + FAKE)
            fake.chmod(0o755)
            result = subprocess.run(
                ["bash", "scripts/review_gemini_chrome.sh", "probe"],
                cwd=ROOT,
                env=os.environ | {
                    "PATH": str(root) + os.pathsep + os.environ["PATH"],
                    "FAKE_LOG": str(root / "events.json"),
                    "FAKE_SCENARIO": scenario,
                    "TOP10_GEMINI_BROWSER_APP": browser,
                    "TOP10_GEMINI_URL_PART": "gemini.google.com/app/ea58b54eef550ded",
                    "TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT": str(root),
                },
                text=True, capture_output=True, timeout=25,
            )
            if native_compile:
                self.assertEqual(0, result.returncode, result.stderr)
                for phase in ("activate", "ready", "execute"):
                    with self.subTest(phase=phase):
                        # 編譯實際傳給 fake 的完整事件；只替換字典位置，絕不執行。
                        source = (root / (phase + ".applescript")).read_text()
                        source = source.replace(
                            'using terms from application "Google Chrome"',
                            'using terms from application "/Applications/Google Chrome.app"',
                        )
                        compiled = subprocess.run(
                            ["/usr/bin/osacompile", "-o", str(root / (phase + ".scpt"))],
                            input=source, text=True, capture_output=True, timeout=20,
                        )
                        self.assertEqual(0, compiled.returncode, compiled.stderr)
                        self.assertTrue((root / (phase + ".scpt")).is_file())
            return result, json.loads((root / "events.json").read_text())

    @unittest.skipUnless(
        sys.platform == "darwin"
        and Path("/usr/bin/osacompile").is_file()
        and Path("/Applications/Google Chrome.app").is_dir(),
        "native compile 需要 Darwin、osacompile 與 Chrome 字典；此環境未驗證",
    )
    def test_native_compile_all_probe_phases(self):
        self.run_probe(native_compile=True)

    def test_cold_tab_waits_before_execute(self):
        result, events = self.run_probe()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("activate", events[0])
        self.assertLess(events.index("loading"), events.index("ready"))
        self.assertLess(events.index("ready"), events.index("execute"))
        self.assertEqual(1, events.count("execute"))

    def test_fail_closed_and_receipt(self):
        for scenario, phase, reason in (
            ("activate_timeout", "activate", "probe_timeout"),
            ("ambiguous", "activate", "probe_command_failed"),
            ("ready_timeout", "ready", "probe_timeout"),
            ("ready_hang", "ready", "probe_timeout"),
            ("identity_changed", "ready", "probe_command_failed"),
            ("loading_forever", "ready", "probe_timeout"),
            ("execute_timeout", "execute", "probe_timeout"),
            ("loading_again", "execute", "probe_command_failed"),
        ):
            with self.subTest(scenario=scenario):
                result, events = self.run_probe(scenario)
                self.assertNotEqual(0, result.returncode)
                payload = json.loads(result.stdout.splitlines()[0])
                self.assertFalse(payload["ok"])
                self.assertEqual(phase, payload["phase"])
                self.assertEqual(reason, payload["reason"])
                if phase != "execute":
                    self.assertNotIn("execute", events)
                if phase != "activate":
                    self.assertEqual(("41", "73"), (payload["window_id"], payload["tab_id"]))
                command = runner.CommandResult(["fake"], result.returncode, result.stdout, result.stderr)
                with patch.object(runner, "run_command", return_value=command):
                    check = runner.run_provider_preflight(provider="gemini", command_template="fake")
                receipt = preflight.normalize_provider_check("gemini", check)
                self.assertEqual("BLOCKED", receipt["status"])
                self.assertEqual(reason, receipt["blocker"]["code"])
                self.assertEqual(phase, receipt["evidence"]["phase"])
                self.assertEqual(payload["error"], receipt["evidence"]["error"])
                if reason == "probe_timeout":
                    self.assertEqual("provider_timeout", receipt["blocker"]["kind"])

    def test_browser_argument_is_data(self):
        result, _ = self.run_probe(browser='Chrome " quoted \\ name')
        self.assertEqual(0, result.returncode, result.stderr)

    def test_legacy_timeout_is_not_readiness_or_session_failure(self):
        result = runner.CommandResult(["fake"], 1, "", "AppleEvent timed out (-1712)")
        self.assertEqual("probe_timeout", runner.provider_preflight_reason(provider="gemini", result=result, payload={}))
