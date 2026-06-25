from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts.run_external_review_host_runner import CommandResult, provider_preflight_reason


class ExternalReviewProviderPreflightTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
