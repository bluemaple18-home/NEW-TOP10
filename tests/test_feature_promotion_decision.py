import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import scripts.build_feature_promotion_decision as builder
import scripts.verify_feature_promotion_decision as verifier
from scripts.build_feature_promotion_decision import REVIEW_BASE_SHA, REVIEW_CANDIDATE_SHA, build_payload
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


if __name__ == "__main__":
    unittest.main()
