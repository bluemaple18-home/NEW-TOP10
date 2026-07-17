from __future__ import annotations

import unittest

from app.workflows.daily_v2_promotion import build_daily_v2_promotion_decision


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


def acceptance() -> dict:
    return {
        "schema_version": "top10.daily-v2.promotion-acceptance.v1",
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


def review() -> dict:
    return {"schema_version": "top10.architecture-independent-review.v1", "verdict": "GO"}


class DailyV2PromotionTest(unittest.TestCase):
    def test_all_strict_requirements_can_authorize_but_never_execute_switch(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16"), parity("2026-07-17")],
            script_governance=governance(),
            acceptance=acceptance(),
            independent_review=review(),
        )
        self.assertEqual(decision["status"], "GO")
        self.assertTrue(decision["production_switch"]["authorized"])
        self.assertFalse(decision["production_switch"]["executed"])

    def test_fixture_and_missing_evidence_retain_current_production(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16", profile="fixture")],
            script_governance=governance(unknown=True),
            acceptance=None,
            independent_review=None,
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
            acceptance=acceptance(),
            independent_review=review(),
        )
        self.assertEqual(decision["status"], "NO-GO")
        self.assertEqual(decision["production_equivalent_dates"], ["2026-07-16"])

    def test_any_representative_date_no_go_blocks(self) -> None:
        decision = build_daily_v2_promotion_decision(
            parity_reports=[parity("2026-07-16"), parity("2026-07-17", status="NO-GO")],
            script_governance=governance(),
            acceptance=acceptance(),
            independent_review=review(),
        )
        self.assertIn("parity_no_go", {item["code"] for item in decision["blockers"]})


if __name__ == "__main__":
    unittest.main()
