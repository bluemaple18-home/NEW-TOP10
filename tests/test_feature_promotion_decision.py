import subprocess
import sys
import unittest
from pathlib import Path

from scripts.build_feature_promotion_decision import build_payload
from scripts.verify_feature_promotion_decision import verify


class FeaturePromotionDecisionTests(unittest.TestCase):
    def test_missing_required_evidence_is_no_go_and_reproducible(self) -> None:
        base = "b5a5e6394fa1bdb4f82124ffa5e1694844605f28"
        first = build_payload(base, base)
        second = build_payload(base, base)
        self.assertEqual(first, second)
        self.assertEqual(first["decision"], "NO_GO")
        self.assertTrue(first["missing_required_evidence"])
        self.assertEqual(verify(first), [])
        self.assertEqual(first["attribution_and_risk"]["graph_residual_tolerance_gt_1"]["status"], "RISK")
        self.assertEqual(first["attribution_and_risk"]["tpex"]["status"], "KEEP_BLOCKED")

    def test_source_mutation_fails_verification(self) -> None:
        payload = build_payload("b5a5e6394fa1bdb4f82124ffa5e1694844605f28", "b5a5e6394fa1bdb4f82124ffa5e1694844605f28")
        payload["missing_required_evidence"] = []
        self.assertIn("missing_evidence_recomputed", verify(payload))

    def test_cli_help(self) -> None:
        for script in ("scripts/build_feature_promotion_decision.py", "scripts/verify_feature_promotion_decision.py"):
            result = subprocess.run([sys.executable, script, "--help"], cwd=Path(__file__).parents[1], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
