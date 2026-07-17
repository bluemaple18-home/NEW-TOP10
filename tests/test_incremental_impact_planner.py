from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from app.architecture.impact import (
    ImpactPlanError,
    build_incremental_verification_plan,
    changed_files_from_git,
    verify_incremental_verification_plan,
    _is_generated_evidence,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class IncrementalImpactPlannerTest(unittest.TestCase):
    def test_shared_automation_contract_reaches_production_workflows_and_tests(self) -> None:
        plan = build_incremental_verification_plan(
            PROJECT_ROOT,
            changed_files=["app/automation/status_contract.py"],
        )

        self.assertEqual(plan["risk"]["level"], "critical")
        self.assertIn("scripts/run_automation.py", plan["impact"]["files"])
        self.assertIn("daily", plan["impact"]["workflows"])
        self.assertIn("monitor", plan["impact"]["workflows"])
        self.assertIn("retrain", plan["impact"]["workflows"])
        self.assertIn("daily_contract", plan["required_verification"])
        self.assertIn("retrain_contract", plan["required_verification"])

    def test_production_entrypoint_change_is_critical_and_fail_closed(self) -> None:
        plan = build_incremental_verification_plan(
            PROJECT_ROOT,
            changed_files=["scripts/run_daily.sh"],
        )

        self.assertEqual(plan["risk"]["level"], "critical")
        self.assertIn("daily", plan["impact"]["workflows"])
        self.assertIn("daily_contract", plan["required_verification"])
        self.assertFalse(plan["risk"]["missing_production_verification"])

    def test_docs_only_change_stays_low_risk(self) -> None:
        plan = build_incremental_verification_plan(
            PROJECT_ROOT,
            changed_files=["docs/architecture/ARCHITECTURE_CONTROL_PLANE.md"],
        )

        self.assertEqual(plan["risk"]["level"], "low")
        self.assertEqual(plan["impact"]["workflows"], [])
        self.assertEqual(plan["required_verification"], ["architecture_contract"])

    def test_tampered_plan_is_rejected(self) -> None:
        plan = build_incremental_verification_plan(
            PROJECT_ROOT,
            changed_files=["scripts/run_daily.sh"],
        )
        tampered = deepcopy(plan)
        tampered["required_verification"] = []

        with self.assertRaisesRegex(ImpactPlanError, "repo source 不一致"):
            verify_incremental_verification_plan(tampered, PROJECT_ROOT)

    def test_path_escape_is_rejected(self) -> None:
        with self.assertRaisesRegex(ImpactPlanError, "repo-relative"):
            build_incremental_verification_plan(PROJECT_ROOT, changed_files=["../outside.py"])

    def test_empty_git_diff_produces_noop_plan(self) -> None:
        changed = changed_files_from_git(PROJECT_ROOT, "HEAD", "HEAD")
        plan = build_incremental_verification_plan(PROJECT_ROOT, changed_files=changed)

        self.assertEqual(changed, [])
        self.assertEqual(plan["risk"]["level"], "none")
        self.assertEqual(plan["impact"]["files"], [])
        self.assertEqual(plan["required_verification"], [])

    def test_unknown_source_commit_is_rejected(self) -> None:
        plan = build_incremental_verification_plan(
            PROJECT_ROOT,
            changed_files=["docs/architecture/ARCHITECTURE_CONTROL_PLANE.md"],
        )
        plan["source"]["git_sha"] = "0" * 40

        with self.assertRaisesRegex(ImpactPlanError, "必須等於目前 HEAD"):
            verify_incremental_verification_plan(plan, PROJECT_ROOT)

    def test_tracked_working_tree_digest_tamper_is_rejected(self) -> None:
        plan = build_incremental_verification_plan(
            PROJECT_ROOT,
            changed_files=["docs/architecture/ARCHITECTURE_CONTROL_PLANE.md"],
        )
        plan["source"]["tracked_tree_digest"] = "0" * 64
        with self.assertRaisesRegex(ImpactPlanError, "repo source 不一致"):
            verify_incremental_verification_plan(plan, PROJECT_ROOT)

    def test_unknown_dynamic_edges_force_full_production_verification(self) -> None:
        unknown = [{"source": "scripts/run_daily.sh", "kind": "python_dynamic_import", "line": 1}]
        with mock.patch("app.architecture.impact._dependency_graph", return_value=([], unknown)):
            plan = build_incremental_verification_plan(
                PROJECT_ROOT,
                changed_files=["config/automation.yaml"],
            )
        self.assertTrue(plan["risk"]["unknown_edges_fail_closed"])
        self.assertEqual(plan["risk"]["level"], "critical")
        self.assertIn("daily_contract", plan["required_verification"])
        self.assertIn("publish_guard", plan["required_verification"])
        self.assertIn("scheduler_ownership", plan["required_verification"])

    def test_generated_evidence_is_not_a_dependency_source(self) -> None:
        payload = '{"schema_version":"top10.incremental-verification-plan.v1","changed_files":["scripts/run_daily.sh"]}'

        self.assertTrue(_is_generated_evidence(".work/task/evidence/plan.json", payload))
        self.assertFalse(_is_generated_evidence("config/manual-contract.json", '{"schema_version":"manual.v1"}'))


if __name__ == "__main__":
    unittest.main()
