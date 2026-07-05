from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import scripts.verify_external_review_summary as summary_verifier
from scripts.build_external_review_summary import build_summary, load_reviews
from scripts.external_review_provider_contract import provider_artifact_errors
from scripts.verify_external_review_summary import validate


class ExternalReviewSummaryContractTest(unittest.TestCase):
    def test_summary_does_not_count_short_failed_chatgpt_raw_as_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp) / "2026-06-30"
            review_dir.mkdir(parents=True, exist_ok=True)
            write_provider_artifacts(review_dir, "chatgpt", "2026-06-30", raw_text="我", collect_ok=False)
            write_provider_artifacts(review_dir, "gemini", "2026-06-30", raw_text=long_raw("gemini"), collect_ok=True)

            reviews = load_reviews(review_dir, "2026-06-30")
            summary = build_summary("2026-06-30", reviews)

            chatgpt = next(item for item in summary["providers"] if item["provider"] == "chatgpt")
            self.assertFalse(chatgpt["valid"])
            self.assertIn("raw_too_short", chatgpt["reason"])
            self.assertIn("collect_status_not_ok", chatgpt["reason"])
            self.assertEqual(summary["valid_provider_count"], 1)
            self.assertEqual(summary["safety"]["invalid_providers"], ["chatgpt"])

    def test_summary_verifier_rejects_valid_true_when_raw_contract_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp) / "2026-06-30"
            review_dir.mkdir(parents=True, exist_ok=True)
            write_provider_artifacts(review_dir, "chatgpt", "2026-06-30", raw_text="我", collect_ok=False)
            summary = sample_summary(review_dir)

            errors = validate(summary, review_dir)

            self.assertTrue(any("providers[0].valid: true but artifacts invalid" in error for error in errors))

    def test_provider_contract_rejects_collect_status_provider_or_date_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp) / "2026-06-30"
            review_dir.mkdir(parents=True, exist_ok=True)
            write_provider_artifacts(review_dir, "chatgpt", "2026-06-30", raw_text=long_raw("chatgpt"), collect_ok=True)
            status_path = review_dir / "chatgpt_collect_status_2026-06-30.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["provider"] = "gemini"
            status["review_date"] = "2026-06-29"
            status_path.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")

            errors = provider_artifact_errors(
                provider="chatgpt",
                review_date="2026-06-30",
                raw_path=review_dir / "chatgpt_raw_2026-06-30.txt",
                collect_status_path=status_path,
            )

            self.assertIn("collect_status_provider_mismatch:gemini!=chatgpt", errors)
            self.assertIn("collect_status_review_date_mismatch:2026-06-29!=2026-06-30", errors)

    def test_summary_verifier_rejects_response_provider_or_date_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp) / "2026-06-30"
            review_dir.mkdir(parents=True, exist_ok=True)
            write_provider_artifacts(review_dir, "chatgpt", "2026-06-30", raw_text=long_raw("chatgpt"), collect_ok=True)
            response_path = review_dir / "chatgpt_response_2026-06-30.json"
            response_path.write_text(
                json.dumps(sample_response("gemini", "2026-06-29"), ensure_ascii=False),
                encoding="utf-8",
            )
            summary = sample_summary(review_dir)

            errors = validate(summary, review_dir)

            self.assertTrue(any("response_provider_mismatch:gemini!=chatgpt" in error for error in errors))
            self.assertTrue(any("response_review_date_mismatch:2026-06-29!=2026-06-30" in error for error in errors))

    def test_summary_verifier_rejects_missing_response_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp) / "2026-06-30"
            review_dir.mkdir(parents=True, exist_ok=True)
            write_provider_artifacts(review_dir, "chatgpt", "2026-06-30", raw_text=long_raw("chatgpt"), collect_ok=True)
            (review_dir / "chatgpt_response_2026-06-30.json").unlink()
            summary = sample_summary(review_dir)

            errors = validate(summary, review_dir)

            self.assertTrue(any("response_missing" in error for error in errors))

    def test_summary_verifier_resolves_repo_relative_paths_without_cwd_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as cwd_tmp:
            old_cwd = Path.cwd()
            old_project_root = summary_verifier.PROJECT_ROOT
            try:
                repo_root = Path(repo_tmp)
                summary_verifier.PROJECT_ROOT = repo_root
                review_dir = repo_root / "artifacts" / "external_review" / "2026-06-30"
                review_dir.mkdir(parents=True, exist_ok=True)
                write_provider_artifacts(review_dir, "chatgpt", "2026-06-30", raw_text=long_raw("chatgpt"), collect_ok=True)
                summary = sample_summary(review_dir)
                summary["providers"][0]["path"] = "artifacts/external_review/2026-06-30/chatgpt_response_2026-06-30.json"
                summary["providers"][0]["raw_path"] = "artifacts/external_review/2026-06-30/chatgpt_raw_2026-06-30.txt"
                summary["providers"][0]["collect_status_path"] = (
                    "artifacts/external_review/2026-06-30/chatgpt_collect_status_2026-06-30.json"
                )
                os.chdir(cwd_tmp)

                errors = validate(summary, review_dir)
            finally:
                os.chdir(old_cwd)
                summary_verifier.PROJECT_ROOT = old_project_root

            self.assertEqual(errors, [])


def write_provider_artifacts(review_dir: Path, provider: str, review_date: str, *, raw_text: str, collect_ok: bool) -> None:
    raw_path = review_dir / f"{provider}_raw_{review_date}.txt"
    response_path = review_dir / f"{provider}_response_{review_date}.json"
    status_path = review_dir / f"{provider}_collect_status_{review_date}.json"
    raw_path.write_text(raw_text + "\n", encoding="utf-8")
    response_path.write_text(json.dumps(sample_response(provider, review_date), ensure_ascii=False), encoding="utf-8")
    status_path.write_text(
        json.dumps(
            {
                "ok": collect_ok,
                "provider": provider,
                "review_date": review_date,
                "reason": "normalized_contract_ok" if collect_ok else "formal_raw_too_short_or_smoke",
                "raw_chars": len(raw_text),
                "smoke_marker_detected": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def long_raw(provider: str) -> str:
    return (f"{provider} 正式 reviewer 回覆，包含盤面、族群、風險與隔日觀察。" * 40)[:900]


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


def sample_summary(review_dir: Path) -> dict:
    raw_path = review_dir / "chatgpt_raw_2026-06-30.txt"
    status_path = review_dir / "chatgpt_collect_status_2026-06-30.json"
    response_path = review_dir / "chatgpt_response_2026-06-30.json"
    return {
        "schema_version": "external-review-summary.v1",
        "review_date": "2026-06-30",
        "providers": [
            {
                "provider": "chatgpt",
                "valid": True,
                "reason": "ok",
                "path": str(response_path),
                "raw_path": str(raw_path),
                "collect_status_path": str(status_path),
            }
        ],
        "valid_provider_count": 1,
        "consensus": [],
        "disagreements": [],
        "today_misses": [],
        "tomorrow_watch": {"continue": [], "avoid_chasing": [], "watch_for_reversal": [], "theme_candidates": []},
        "research_hypotheses": [],
        "safety": {
            "needs_human_review": False,
            "invalid_providers": [],
            "algorithm_requested": False,
            "contains_algorithm_claim": False,
        },
        "promotion_boundary": {
            "external_review_is_research_only": True,
            "promotion_ready": False,
            "may_change_ranking_or_model": False,
        },
    }


if __name__ == "__main__":
    unittest.main()
