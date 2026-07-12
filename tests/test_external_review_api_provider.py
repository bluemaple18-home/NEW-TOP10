from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.external_review_api_provider import build_dry_run_review
from scripts.normalize_external_review_response import normalize_payload
from scripts.verify_external_review_contract import validate
from scripts.run_external_review_host_runner import run_provider


class ExternalReviewApiProviderTest(unittest.TestCase):
    def test_dry_run_review_matches_external_review_contract(self) -> None:
        packet = sample_packet()
        payload = build_dry_run_review("chatgpt", "2026-06-24", packet)

        self.assertEqual(validate(payload), [])

    def test_dry_run_raw_normalizes_and_verifies(self) -> None:
        packet = sample_packet()
        raw_payload = build_dry_run_review("gemini", "2026-06-24", packet)
        normalized = normalize_payload(
            provider="gemini",
            review_date="2026-06-24",
            raw_payload=raw_payload,
            raw_text=json.dumps(raw_payload, ensure_ascii=False),
            packet=packet,
        )

        self.assertEqual(validate(normalized), [])

    def test_generic_reviewer_json_score_normalizes(self) -> None:
        packet = sample_packet()
        raw_payload = {
            "overall": {
                "score": 6.6,
                "confidence": "中等",
                "summary": "強勢動能選股，但需要防追高與停損過寬。",
            },
            "quality": {
                "mainstream_alignment": {"rating": "中上"},
                "relative_strength": {"rating": "高"},
                "risk_control": {"rating": "偏弱"},
                "timing_quality": {"rating": "中等"},
                "theme_fit": {"rating": "中上"},
            },
            "observations": [{"point": "動能強", "evidence": "2330 放量突破。"}],
            "misses": [{"issue": "追高風險", "detail": "2317 開高走低。"}],
            "research_hypotheses": [{"hypothesis": "測試強勢收盤隔日續航", "why": "避免追高。"}],
            "safety": {"manual_review_required": ["停損過寬需覆核"]},
        }
        normalized = normalize_payload(
            provider="chatgpt",
            review_date="2026-06-24",
            raw_payload=raw_payload,
            raw_text=json.dumps(raw_payload, ensure_ascii=False),
            packet=packet,
        )

        self.assertEqual(validate(normalized), [])
        self.assertEqual(normalized["overall"]["score"], 66)
        self.assertEqual(normalized["overall"]["verdict"], "good")
        self.assertTrue(normalized["safety"]["needs_human_review"])

    def test_chatgpt_overall_assessment_score_normalizes(self) -> None:
        packet = sample_packet()
        raw_payload = {
            "status": "review_complete",
            "provider": "chatgpt",
            "overall_assessment": {
                "score_0_to_10": 7.1,
                "confidence_0_to_1": 0.55,
                "summary": "中上偏強，但短線過熱與高價股集中風險明顯。",
            },
            "misses": [
                {
                    "issue": "把爆量強攻誤判為安全起漲",
                    "evidence": "隔日若未能續量站穩高點，可能只是短線情緒高潮。",
                }
            ],
        }
        normalized = normalize_payload(
            provider="chatgpt",
            review_date="2026-07-03",
            raw_payload=raw_payload,
            raw_text=json.dumps(raw_payload, ensure_ascii=False),
            packet=packet,
        )

        self.assertEqual(validate(normalized), [])
        self.assertEqual(normalized["overall"]["score"], 71)
        self.assertEqual(normalized["overall"]["verdict"], "good")
        self.assertEqual(normalized["overall"]["confidence"], 0.55)

    def test_host_runner_api_dry_run_provider_writes_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts"
            packet_path = artifacts / "external_review" / "2026-06-24" / "review_packet_2026-06-24.json"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text(json.dumps(sample_packet(), ensure_ascii=False), encoding="utf-8")

            state = run_provider(
                provider="chatgpt",
                run_date="2026-06-24",
                packet_path=packet_path,
                artifacts_dir=artifacts,
                skip_submit=False,
                provider_mode="api",
                dry_run_provider_api=True,
                command_template="unused",
            )

            self.assertEqual(state["status"], "OK")
            self.assertEqual(state["provider_mode"], "api")
            response_path = artifacts / "external_review" / "2026-06-24" / "chatgpt_response_2026-06-24.json"
            self.assertTrue(response_path.exists())
            response = json.loads(response_path.read_text(encoding="utf-8"))
            self.assertEqual(validate(response), [])


def sample_packet() -> dict:
    return {
        "schema_version": "external-review-packet.v1",
        "sendable": True,
        "packet_date": "2026-06-24",
        "market": "TW",
        "market_overview": {"market_regime": "trend", "top_count": 10},
        "outcome_status": {"same_day_ohlc_available": True},
        "recommendations": [
            {"rank": 1, "stock_id": "2330", "stock_name": "台積電"},
            {"rank": 2, "stock_id": "2317", "stock_name": "鴻海"},
        ],
    }


if __name__ == "__main__":
    unittest.main()
