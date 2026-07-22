import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import scripts.build_feature_promotion_decision as builder
import scripts.verify_feature_promotion_decision as verifier
from scripts.build_feature_promotion_decision import (
    FRESHNESS_CONTRACT,
    REVIEW_BASE_SHA,
    REVIEW_CANDIDATE_SHA,
    build_payload,
    freshness_error,
    is_versioned_evidence,
)
from scripts.verify_feature_promotion_decision import verify


class FeaturePromotionDecisionTests(unittest.TestCase):
    def test_missing_required_evidence_is_no_go_and_reproducible(self) -> None:
        first = build_payload(REVIEW_BASE_SHA, REVIEW_CANDIDATE_SHA)
        second = build_payload(REVIEW_BASE_SHA, REVIEW_CANDIDATE_SHA)
        self.assertEqual(first, second)
        self.assertEqual(first["decision"], "NO_GO")
        self.assertTrue(first["missing_required_evidence"])
        self.assertEqual(verify(first), [])
        self.assertEqual(first["attribution_and_risk"]["graph_residual_tolerance_gt_1"]["status"], "RISK")
        self.assertEqual(first["attribution_and_risk"]["tpex"]["status"], "KEEP_BLOCKED")

    def test_source_mutation_fails_verification(self) -> None:
        payload = build_payload(REVIEW_BASE_SHA, REVIEW_CANDIDATE_SHA)
        payload["missing_required_evidence"] = []
        self.assertIn("missing_evidence_recomputed", verify(payload))

    def test_complete_versioned_evidence_is_a_synthetic_go_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-promotion-tests-") as temp:
            root = Path(temp)
            today = dt.date.today().isoformat()
            evidence = {
                "schema_version": builder.EVIDENCE_SCHEMA_VERSION,
                "evidence_kind": "placeholder",
                "decision": "GO",
                "verdict": "PASS",
                "base_sha": REVIEW_BASE_SHA,
                "candidate_sha": REVIEW_CANDIDATE_SHA,
                "data_sha256": "a" * 64,
                "universe_id": "synthetic-universe",
                "date_start": "2026-01-01",
                "date_end": "2026-07-22",
                "cost_model": "synthetic-cost-v1",
                "metrics": {"metric": 1.0},
                "thresholds": {"metric": 0.0},
                "freshness": {"as_of": today, "max_age_days": 1},
                "source_file_sha256": "b" * 64,
            }
            old_builder_root, old_verifier_root = builder.PROJECT_ROOT, verifier.PROJECT_ROOT
            try:
                builder.PROJECT_ROOT = root
                verifier.PROJECT_ROOT = root
                for key, _, pattern in builder.REQUIRED:
                    relative = pattern.replace("*", f"{key}.json")
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    document = dict(evidence, evidence_kind=key)
                    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
                payload = builder.build_payload(REVIEW_BASE_SHA, REVIEW_CANDIDATE_SHA)
                self.assertEqual(payload["decision"], "GO", payload["missing_required_evidence"])
                self.assertEqual(verifier.verify(payload), [])
            finally:
                builder.PROJECT_ROOT, verifier.PROJECT_ROOT = old_builder_root, old_verifier_root

    def test_cli_help(self) -> None:
        for script in ("scripts/build_feature_promotion_decision.py", "scripts/verify_feature_promotion_decision.py"):
            result = subprocess.run([sys.executable, script, "--help"], cwd=Path(__file__).parents[1], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_freshness_exact_boundary_and_fixed_contract(self) -> None:
        decision_as_of = dt.date(2026, 7, 22)
        base = {
            "date_start": "2026-01-01",
            "date_end": "2026-07-22",
            "freshness": {"as_of": "2026-07-21", "max_age_days": 1},
        }
        self.assertIsNone(freshness_error(base, "sealed_oos", decision_as_of))
        over_age = dict(base, freshness={"as_of": "2026-07-20", "max_age_days": 1})
        self.assertEqual(freshness_error(over_age, "sealed_oos", decision_as_of), "freshness_stale")
        self.assertEqual(FRESHNESS_CONTRACT["sealed_oos"]["max_age_days"], 1)

    def test_freshness_rejects_future_invalid_reversed_and_over_window(self) -> None:
        decision_as_of = dt.date(2026, 7, 22)
        base = {
            "date_start": "2026-01-01",
            "date_end": "2026-07-22",
            "freshness": {"as_of": "2026-07-22", "max_age_days": 1},
        }
        self.assertEqual(freshness_error(dict(base, freshness={"as_of": "2026-07-23", "max_age_days": 1}), "sealed_oos", decision_as_of), "freshness_future")
        self.assertEqual(freshness_error(dict(base, freshness={"as_of": "2026-02-30", "max_age_days": 1}), "sealed_oos", decision_as_of), "freshness_date")
        self.assertEqual(freshness_error(dict(base, date_start="2026-07-22", date_end="2026-07-21"), "sealed_oos", decision_as_of), "freshness_date")
        self.assertEqual(freshness_error(dict(base, date_start="2025-07-21"), "sealed_oos", decision_as_of), "freshness_window")
        self.assertEqual(freshness_error(dict(base, date_end="2026-07-23"), "sealed_oos", decision_as_of), "freshness_future")

    def test_decision_as_of_is_bound_and_future_input_fails_closed(self) -> None:
        payload = build_payload(REVIEW_BASE_SHA, REVIEW_CANDIDATE_SHA, "2026-07-22")
        self.assertEqual(verify(payload), [])
        payload["decision_as_of"] = "2026-07-21"
        self.assertIn("decision_as_of_hash", verify(payload))
        with self.assertRaises(ValueError):
            build_payload(REVIEW_BASE_SHA, REVIEW_CANDIDATE_SHA, "2999-01-01")

    def test_builder_evidence_uses_fixed_freshness_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feature-promotion-freshness-") as temp:
            path = Path(temp) / "evidence.json"
            document = {
                "schema_version": builder.EVIDENCE_SCHEMA_VERSION,
                "evidence_kind": "sealed_oos", "decision": "GO", "verdict": "PASS",
                "base_sha": REVIEW_BASE_SHA, "candidate_sha": REVIEW_CANDIDATE_SHA,
                "data_sha256": "a" * 64, "universe_id": "u",
                "date_start": "2026-01-01", "date_end": "2026-07-22", "cost_model": "c",
                "metrics": {"m": 1}, "thresholds": {},
                "freshness": {"as_of": "2026-07-21", "max_age_days": 1},
                "source_file_sha256": "b" * 64,
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertTrue(is_versioned_evidence(path, "sealed_oos", dt.date(2026, 7, 22)))
            document["freshness"]["as_of"] = "2026-07-20"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertFalse(is_versioned_evidence(path, "sealed_oos", dt.date(2026, 7, 22)))


if __name__ == "__main__":
    unittest.main()
