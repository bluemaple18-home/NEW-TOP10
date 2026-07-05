from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.run_external_review_host_runner import run_provider, write_host_summary
from scripts.verify_external_review_host_runner import validate_status, validate_summary


class ExternalReviewHostRunnerSummaryTest(unittest.TestCase):
    def test_write_host_summary_derives_validity_from_external_provider_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "host_runner_summary.json"
            external_summary = sample_external_summary()
            external_summary["safety"]["invalid_providers"] = ["chatgpt"]

            write_host_summary(summary_path, sample_status("2026-06-25"), external_summary)

            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["valid_provider_count"], 2)
            self.assertEqual(payload["safety"]["invalid_providers"], [])
            self.assertTrue(payload["providers"][0]["valid"])
            self.assertTrue(payload["providers"][1]["valid"])

    def test_validate_summary_rejects_stale_external_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            external_path = Path(tmp) / "external_review_summary_2026-06-25.json"
            external_path.write_text(json.dumps(sample_external_summary(), ensure_ascii=False), encoding="utf-8")
            stale_summary = {
                "schema_version": "external-review-host-runner-summary.v1",
                "run_date": "2026-06-25",
                "status": "OK",
                "external_review_summary_path": str(external_path),
                "providers": [
                    {"provider": "chatgpt", "status": "OK", "valid": False},
                    {"provider": "gemini", "status": "OK", "valid": True},
                ],
                "valid_provider_count": 1,
                "safety": {"needs_human_review": True, "invalid_providers": ["chatgpt"]},
                "promotion_boundary": sample_external_summary()["promotion_boundary"],
                "notes": [],
            }

            errors = validate_summary(stale_summary, {"run_date": "2026-06-25", "status": "OK"})

            self.assertTrue(any("summary.valid_provider_count" in error for error in errors))
            self.assertTrue(any("summary.safety.invalid_providers" in error for error in errors))
            self.assertTrue(any("summary.providers[chatgpt].valid" in error for error in errors))

    def test_run_provider_rejects_failed_collect_status_even_when_raw_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts"
            review_dir = artifacts / "external_review" / "2026-06-30"
            review_dir.mkdir(parents=True, exist_ok=True)
            packet_path = review_dir / "review_packet_2026-06-30.json"
            packet_path.write_text(json.dumps(sample_packet(), ensure_ascii=False), encoding="utf-8")
            (review_dir / "chatgpt_raw_2026-06-30.txt").write_text("我\n", encoding="utf-8")
            (review_dir / "chatgpt_collect_status_2026-06-30.json").write_text(
                json.dumps(
                    {
                        "ok": False,
                        "reason": "formal_raw_too_short_or_smoke",
                        "raw_chars": 1,
                        "smoke_marker_detected": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            state = run_provider(
                provider="chatgpt",
                run_date="2026-06-30",
                packet_path=packet_path,
                artifacts_dir=artifacts,
                skip_submit=True,
                provider_mode="browser",
                dry_run_provider_api=False,
                command_template="unused",
            )

            self.assertEqual(state["status"], "FAILED")
            self.assertTrue(any("raw_too_short" in note for note in state["notes"]))
            self.assertTrue(any("collect_status_not_ok" in note for note in state["notes"]))

    def test_validate_status_rejects_ok_provider_with_failed_collect_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = root / "external_review" / "2026-06-30"
            review_dir.mkdir(parents=True, exist_ok=True)
            raw_path = review_dir / "chatgpt_raw_2026-06-30.txt"
            response_path = review_dir / "chatgpt_response_2026-06-30.json"
            status_path = review_dir / "chatgpt_collect_status_2026-06-30.json"
            raw_path.write_text("我\n", encoding="utf-8")
            response_path.write_text(json.dumps(sample_response("chatgpt", "2026-06-30"), ensure_ascii=False), encoding="utf-8")
            status_path.write_text(
                json.dumps({"ok": False, "reason": "formal_raw_too_short_or_smoke", "raw_chars": 1}, ensure_ascii=False),
                encoding="utf-8",
            )
            host_status_path = root / "host_runner_status_2026-06-30.json"
            payload = sample_status("2026-06-30")
            payload["host_runner_status_path"] = str(host_status_path)
            payload["daily_status_ok"] = True
            payload["packet_verified"] = True
            payload["manifest_refused"] = True
            payload["summary_verified"] = True
            payload["chatgpt"].update(
                {
                    "raw_path": str(raw_path),
                    "response_path": str(response_path),
                    "collect_status_path": str(status_path),
                    "status": "OK",
                }
            )

            errors = validate_status(payload, host_status_path, require_success=False)

            self.assertTrue(any("chatgpt.status: OK but artifacts invalid" in error for error in errors))


def sample_status(run_date: str) -> dict:
    return {
        "run_date": run_date,
        "status": "OK",
        "host_runner_status_path": f"artifacts/host_runner/{run_date}/host_runner_status_{run_date}.json",
        "summary_path": f"artifacts/external_review/{run_date}/external_review_summary_{run_date}.json",
        "chatgpt": {"status": "OK", "raw_path": "chatgpt_raw.txt", "response_path": "chatgpt_response.json", "notes": []},
        "gemini": {"status": "OK", "raw_path": "gemini_raw.txt", "response_path": "gemini_response.json", "notes": []},
        "notes": [],
    }


def sample_packet() -> dict:
    return {
        "schema_version": "external-review-packet.v1",
        "sendable": True,
        "packet_date": "2026-06-30",
        "market": "TW",
        "market_overview": {"top_count": 10},
        "outcome_status": {},
        "recommendations": [{"rank": 1, "stock_id": "2330", "stock_name": "台積電"}],
    }


def sample_response(provider: str, review_date: str) -> dict:
    return {
        "schema_version": "external-review.v1",
        "provider": provider,
        "review_date": review_date,
        "market": "TW",
        "overall": {"score": 70, "verdict": "good", "confidence": 0.7, "summary": "測試用 reviewer 摘要。"},
        "quality": {
            "mainstream_alignment": 3,
            "relative_strength": 3,
            "risk_control": 3,
            "timing_quality": 3,
            "theme_fit": 3,
        },
        "observations": [],
        "misses": [],
        "themes": {"strong": [], "weak": [], "watch": []},
        "tomorrow_watch": {"continue": [], "avoid_chasing": [], "watch_for_reversal": [], "theme_candidates": []},
        "research_hypotheses": [],
        "safety": {"algorithm_requested": False, "contains_algorithm_claim": False, "needs_human_review": False},
    }


def sample_external_summary() -> dict:
    return {
        "schema_version": "external-review-summary.v1",
        "review_date": "2026-06-25",
        "providers": [
            {"provider": "chatgpt", "valid": True, "reason": "ok"},
            {"provider": "gemini", "valid": True, "reason": "ok"},
        ],
        "valid_provider_count": 2,
        "safety": {
            "needs_human_review": True,
            "invalid_providers": [],
            "algorithm_requested": False,
            "contains_algorithm_claim": False,
        },
        "promotion_boundary": {
            "external_review_is_research_only": True,
            "promotion_ready": False,
            "may_change_ranking_or_model": False,
            "required_next_gate": "historical_replay_or_shadow_ranking_before_any_model_change",
        },
    }


if __name__ == "__main__":
    unittest.main()
