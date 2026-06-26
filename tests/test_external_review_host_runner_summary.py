from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.run_external_review_host_runner import write_host_summary
from scripts.verify_external_review_host_runner import validate_summary


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
