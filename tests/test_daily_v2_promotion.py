from __future__ import annotations

import unittest
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from app.workflows.daily_v2_parity import build_daily_v2_parity_report_from_files
from app.workflows.daily_v2_promotion import (
    DailyV2PromotionError,
    build_daily_v2_promotion_decision,
    build_daily_v2_promotion_decision_from_files,
    verify_daily_v2_promotion_decision_from_files,
)


def parity(run_date: str, *, profile: str = "production-equivalent", status: str = "GO") -> dict:
    return {
        "schema_version": "top10.daily-v2.parity-report.v1",
        "status": status,
        "execution_outcome": "succeeded",
        "run_date": run_date,
        "contract": {"workflow_profile": profile},
        "production_switch": {"status": "GO" if profile == "production-equivalent" and status == "GO" else "NO-GO"},
    }


def governance(*, unknown: bool = False) -> dict:
    return {
        "schema_version": "top10.script-governance.v1",
        "strict": {"passed": True},
        "unknown_references": ([{"source": "app/pipeline/__init__.py"}] if unknown else []),
    }


def _write_evidence(root: Path, name: str, payload: dict) -> dict:
    path = root / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {"kind": name, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def acceptance(root: Path) -> dict:
    candidate = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    base = subprocess.run(["git", "rev-parse", "HEAD~1"], capture_output=True, text=True, check=True).stdout.strip()
    runner = {"id": "pytest", "version": "test"}
    evidence = [
        _write_evidence(
            root,
            "failure_injection",
            {
                "schema_version": "top10.daily-v2.failure-injection-evidence.v1",
                "base_sha": base,
                "candidate_sha": candidate,
                "runner": runner,
                "scenarios": {"timeout": "GO", "partial_output": "GO", "stale_input": "GO"},
            },
        ),
        _write_evidence(
            root,
            "persistent_resume",
            {
                "schema_version": "top10.daily-v2.resume-evidence.v1",
                "base_sha": base,
                "candidate_sha": candidate,
                "runner": runner,
                "status": "GO",
                "checkpointer_backend": "sqlite",
                "idempotency_keys": ["run:step:attempt"],
                "completed_outputs_preserved": True,
            },
        ),
        _write_evidence(
            root,
            "wrapper_rollback",
            {
                "schema_version": "top10.daily-v2.rollback-evidence.v1",
                "base_sha": base,
                "candidate_sha": candidate,
                "runner": runner,
                "status": "GO",
                "tested": True,
                "entrypoint_before_sha256": "a" * 64,
                "entrypoint_after_sha256": "a" * 64,
            },
        ),
    ]
    return {
        "schema_version": "top10.daily-v2.promotion-acceptance.v1",
        "base_sha": base,
        "candidate_sha": candidate,
        "runner": runner,
        "evidence": evidence,
        "failure_injection": {
            "status": "GO",
            "scenarios": ["timeout", "partial_output", "stale_input"],
        },
        "resume": {
            "status": "GO",
            "persistent_checkpointer": True,
            "idempotent_side_effects": True,
        },
        "wrapper_rollback": {"status": "GO", "tested": True},
    }


def review(root: Path) -> dict:
    candidate = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    base = subprocess.run(["git", "rev-parse", "HEAD~1"], capture_output=True, text=True, check=True).stdout.strip()
    reviewer = {"id": "independent-test-reviewer", "independent": True}
    evidence = _write_evidence(
        root,
        "review",
        {
            "schema_version": "top10.architecture-review-evidence.v1",
            "verdict": "GO",
            "base_sha": base,
            "candidate_sha": candidate,
            "reviewer": reviewer,
            "findings": [],
            "verification": [{"command": ["pytest"], "exit_code": 0}],
        },
    )
    return {
        "schema_version": "top10.architecture-independent-review.v1",
        "verdict": "GO",
        "base_sha": base,
        "candidate_sha": candidate,
        "reviewer": reviewer,
        "evidence": [evidence],
    }


class DailyV2PromotionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidate_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        self.base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD~1"], capture_output=True, text=True, check=True
        ).stdout.strip()

    def _sha_args(self) -> dict[str, str]:
        return {
            "expected_base_sha": self.base_sha,
            "expected_candidate_sha": self.candidate_sha,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_in_memory_payload_can_never_authorize_switch(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16"), parity("2026-07-17")],
            script_governance=governance(),
            acceptance=acceptance(self.root),
            independent_review=review(self.root),
            **self._sha_args(),
        )
        self.assertEqual(decision["status"], "NO-GO")
        self.assertFalse(decision["production_switch"]["authorized"])
        self.assertFalse(decision["production_switch"]["executed"])
        self.assertIn("unverified_evidence_sources", {item["code"] for item in decision["blockers"]})

    def test_fixture_and_missing_evidence_retain_current_production(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16", profile="fixture")],
            script_governance=governance(unknown=True),
            acceptance=None,
            independent_review=None,
            **self._sha_args(),
        )
        codes = {item["code"] for item in decision["blockers"]}
        self.assertEqual(decision["status"], "NO-GO")
        self.assertEqual(decision["decision"], "retain_current_production")
        self.assertIn("production_equivalent_parity_dates", codes)
        self.assertIn("unresolved_dynamic_imports", codes)
        self.assertIn("promotion_acceptance_missing", codes)
        self.assertIn("independent_review_missing", codes)

    def test_one_equivalent_date_is_not_enough(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16")],
            script_governance=governance(),
            acceptance=acceptance(self.root),
            independent_review=review(self.root),
            **self._sha_args(),
        )
        self.assertEqual(decision["status"], "NO-GO")
        self.assertEqual(decision["production_equivalent_dates"], ["2026-07-16"])

    def test_any_representative_date_no_go_blocks(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16"), parity("2026-07-17", status="NO-GO")],
            script_governance=governance(),
            acceptance=acceptance(self.root),
            independent_review=review(self.root),
            **self._sha_args(),
        )
        self.assertIn("parity_no_go", {item["code"] for item in decision["blockers"]})

    def test_unbound_boolean_acceptance_and_review_are_rejected(self) -> None:
        unbound_acceptance = acceptance(self.root)
        unbound_acceptance.pop("evidence")
        unbound_review = review(self.root)
        unbound_review["candidate_sha"] = "wrong"
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16"), parity("2026-07-17")],
            script_governance=governance(),
            acceptance=unbound_acceptance,
            independent_review=unbound_review,
            **self._sha_args(),
        )
        codes = {item["code"] for item in decision["blockers"]}
        self.assertIn("promotion_acceptance_unbound", codes)
        self.assertIn("independent_review_unbound", codes)

    def test_arbitrary_text_digest_cannot_satisfy_semantic_evidence(self) -> None:
        text_path = self.root / "claim.txt"
        text_path.write_text("everything passed", encoding="utf-8")
        record = {"kind": "failure_injection", "path": str(text_path), "sha256": hashlib.sha256(text_path.read_bytes()).hexdigest()}
        forged_acceptance = acceptance(self.root)
        forged_acceptance["evidence"] = [record, record, record]
        forged_review = review(self.root)
        forged_review["evidence"] = [{**record, "kind": "review"}]
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16"), parity("2026-07-17")],
            script_governance=governance(),
            acceptance=forged_acceptance,
            independent_review=forged_review,
            **self._sha_args(),
        )
        codes = {item["code"] for item in decision["blockers"]}
        self.assertIn("promotion_acceptance_unbound", codes)
        self.assertIn("independent_review_unbound", codes)

    def test_stale_but_valid_sha_pair_is_rejected(self) -> None:
        stale_acceptance = acceptance(self.root)
        stale_review = review(self.root)
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16"), parity("2026-07-17")],
            script_governance=governance(),
            acceptance=stale_acceptance,
            independent_review=stale_review,
            expected_base_sha=subprocess.run(
                ["git", "rev-parse", "HEAD~2"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            expected_candidate_sha=self.candidate_sha,
        )
        codes = {item["code"] for item in decision["blockers"]}
        self.assertIn("promotion_acceptance_unbound", codes)
        self.assertIn("independent_review_unbound", codes)

    def test_daily_entrypoint_change_is_derived_from_fixed_git_diff(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16")],
            script_governance=governance(),
            acceptance=None,
            independent_review=None,
            expected_base_sha="2ca23b2d6157e3336ae69babe81cb0cefb6800bd",
            expected_candidate_sha="b325c7f60ac0728a92fc3523e10f727bfa52bb88",
        )
        self.assertTrue(decision["production_switch"]["daily_entrypoint_modified"])

    def test_file_backed_decision_is_portable_and_recomputed(self) -> None:
        core = ("etl", "validate", "rank", "report", "publish-ready")
        production_names = {
            "etl": "etl",
            "validate": "data.validate",
            "rank": "ranking",
            "report": "daily.report",
            "publish-ready": "clawd.payload",
        }
        payloads = {
            "production": {
                "schema_version": "daily-run-status.v1",
                "mode": "daily",
                "status": "OK",
                "run_date": "2026-07-17",
                "dry_run": False,
                "steps": [{"name": production_names[name], "status": "OK"} for name in core],
            },
            "workflow": {
                "schema_version": "top10.daily-workflow-v2.run-manifest.v1",
                "run_date": "2026-07-17",
                "run_dir": str(self.root),
                "status": "finished",
                "steps": [
                    {"name": name, "status": "finished", "outputs": [{"exists": True}]}
                    for name in core
                ],
            },
            "real_shadow": {
                "schema_version": "top10.daily-v2.real-shadow-manifest.v1",
                "run_date": "2026-07-17",
                "run_dir": str(self.root),
                "shadow_only": True,
                "live_send_enabled": False,
                "inputs_unchanged": True,
                "comparison_status": "GO",
                "production_switch": {"status": "GO", "executed": False},
            },
            "comparison": {
                "schema_version": "top10.daily-v2.ranking-comparison.v1",
                "status": "GO",
                "production_switch": {"status": "GO", "executed": False},
            },
        }
        source_paths = {}
        for label, payload in payloads.items():
            path = self.root / f"{label}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            source_paths[label] = path
        parity_report = build_daily_v2_parity_report_from_files(
            production_status_path=source_paths["production"],
            workflow_manifest_path=source_paths["workflow"],
            real_shadow_manifest_path=source_paths["real_shadow"],
            ranking_comparison_path=source_paths["comparison"],
            shadow_root=self.root,
            workflow_profile="fixture",
        )
        parity_path = self.root / "parity.json"
        parity_path.write_text(json.dumps(parity_report), encoding="utf-8")
        governance_path = self.root / "governance.json"
        governance_path.write_text(json.dumps(governance()), encoding="utf-8")
        acceptance_path = self.root / "acceptance.json"
        acceptance_path.write_text(json.dumps(acceptance(self.root)), encoding="utf-8")
        review_path = self.root / "independent_review.json"
        review_path.write_text(json.dumps(review(self.root)), encoding="utf-8")

        decision = build_daily_v2_promotion_decision_from_files(
            parity_paths=[parity_path],
            script_governance_path=governance_path,
            acceptance_path=acceptance_path,
            independent_review_path=review_path,
            **self._sha_args(),
        )
        self.assertNotIn("unverified_evidence_sources", {item["code"] for item in decision["blockers"]})
        original_cwd = Path.cwd()
        try:
            os.chdir(tempfile.gettempdir())
            verify_daily_v2_promotion_decision_from_files(decision, **self._sha_args())
        finally:
            os.chdir(original_cwd)

        with self.assertRaisesRegex(DailyV2PromotionError, "verifier 指定"):
            verify_daily_v2_promotion_decision_from_files(
                decision,
                expected_base_sha=subprocess.run(
                    ["git", "rev-parse", "HEAD~2"], capture_output=True, text=True, check=True
                ).stdout.strip(),
                expected_candidate_sha=self.candidate_sha,
            )


if __name__ == "__main__":
    unittest.main()
