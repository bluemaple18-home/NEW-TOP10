from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_research_component_ledger import build_payload
from scripts.verify_research_component_ledger import build_payload as verify_payload


class ResearchComponentLedgerTest(unittest.TestCase):
    def test_builds_runtime_and_research_rows(self) -> None:
        payload = build_payload(argparse.Namespace(date="2026-07-13", output=None))

        self.assertEqual(payload["schema_version"], "research-component-ledger.v1")
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["summary"]["family_counts"]["research_registry"], 10)
        self.assertGreaterEqual(payload["summary"]["family_counts"]["runtime_contract"], 10)

        rows = {row["ledger_id"]: row for row in payload["components"]}
        self.assertEqual(rows["research:overlap_first"]["lifecycle_status"], "rejected")
        self.assertFalse(rows["research:overlap_first"]["changes_production_ranking"])
        self.assertEqual(
            rows["research:overlap_first"]["tskg_adoption"]["adoption_mode"],
            "GRANDFATHERED",
        )
        self.assertEqual(rows["runtime:vwap_regime_gated_entry"]["lifecycle_status"], "shadow")
        self.assertEqual(
            rows["runtime:vwap_regime_gated_entry"]["tskg_adoption"]["adoption_mode"],
            "REQUIRED_NOW",
        )
        self.assertEqual(
            rows["runtime:vwap_regime_gated_entry"]["tskg_adoption"]["decision"],
            "BLOCKED",
        )
        self.assertTrue(
            any(
                "verify_vwap_cost_basis_features.py" in command
                for command in rows["runtime:vwap_regime_gated_entry"]["verification_commands"]
            )
        )
        self.assertTrue(rows["runtime:base_regime_risk_multiplier"]["changes_production_ranking"])
        self.assertTrue(rows["runtime:base_regime_risk_multiplier"]["production_baseline"])
        self.assertEqual(
            rows["runtime:base_regime_risk_multiplier"]["tskg_adoption"]["adoption_mode"],
            "CHECK_ON_REUSE",
        )

    def test_verifier_accepts_generated_ledger(self) -> None:
        payload = build_payload(argparse.Namespace(date="2026-07-13", output=None))

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "research_component_ledger.json"
            artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            report = verify_payload(artifact)

        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["summary"]["failed_count"], 0)

    def test_verifier_blocks_shadow_component_that_changes_production_ranking(self) -> None:
        payload = build_payload(argparse.Namespace(date="2026-07-13", output=None))
        row = next(item for item in payload["components"] if item["ledger_id"] == "runtime:vwap_regime_gated_entry")
        row["changes_production_ranking"] = True

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "bad_research_component_ledger.json"
            artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            report = verify_payload(artifact)

        failed_checks = {check["name"] for check in report["checks"] if not check["ok"]}
        self.assertEqual(report["status"], "FAILED")
        self.assertIn("non_production_cannot_change_ranking", failed_checks)
        self.assertIn("production_mutators_guarded", failed_checks)


if __name__ == "__main__":
    unittest.main()
