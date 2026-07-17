from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
import json
from pathlib import Path

from app.workflows.daily_v2_parity import (
    DailyV2ParityError,
    build_daily_v2_parity_report,
    build_daily_v2_parity_report_from_files,
    verify_daily_v2_parity_report,
    verify_daily_v2_parity_report_from_files,
)


RUN_DATE = "2026-07-09"
CORE_STEPS = ("etl", "validate", "rank", "report", "publish-ready")


def production_status(*, status: str = "OK", failed_step: str | None = None) -> dict:
    name_map = {
        "etl": "etl",
        "validate": "data.validate",
        "rank": "ranking",
        "report": "daily.report",
        "publish-ready": "clawd.payload",
    }
    steps = []
    for name in CORE_STEPS:
        if failed_step and CORE_STEPS.index(name) > CORE_STEPS.index(failed_step):
            break
        step_status = "FAILED" if name == failed_step else "OK"
        steps.append({"name": name_map[name], "status": step_status, "exit_code": 1 if step_status == "FAILED" else 0})
    return {
        "schema_version": "daily-run-status.v1",
        "mode": "daily",
        "status": status,
        "run_date": RUN_DATE,
        "dry_run": False,
        "steps": steps,
    }


def workflow_manifest(
    root: Path,
    *,
    status: str = "finished",
    failed_step: str | None = None,
    resume_count: int = 0,
) -> dict:
    steps = []
    for name in CORE_STEPS:
        if failed_step == name:
            step_status = "failed"
        elif failed_step and CORE_STEPS.index(name) > CORE_STEPS.index(failed_step):
            step_status = "pending"
        else:
            step_status = "finished"
        steps.append(
            {
                "name": name,
                "status": step_status,
                "outputs": [{"path": str(root / name), "exists": step_status == "finished", "sha256": "a" * 64}],
                "failure": (
                    {"reason": "step timed out", "error_type": "timeout", "exit_code": None}
                    if step_status == "failed"
                    else None
                ),
                "attempts": [{"attempt": 1, "status": "failed" if step_status == "failed" else "finished"}],
            }
        )
    return {
        "schema_version": "top10.daily-workflow-v2.run-manifest.v1",
        "run_id": "daily-v2-parity-fixture",
        "run_date": RUN_DATE,
        "run_dir": str(root),
        "status": status,
        "resume_count": resume_count,
        "steps": steps,
    }


def real_shadow_manifest(root: Path) -> dict:
    return {
        "schema_version": "top10.daily-v2.real-shadow-manifest.v1",
        "run_id": "daily-v2-real-shadow",
        "run_date": RUN_DATE,
        "run_dir": str(root),
        "status": "finished",
        "shadow_only": True,
        "live_send_enabled": False,
        "inputs_unchanged": True,
        "comparison_status": "GO",
        "production_switch": {"status": "GO", "executed": False, "reasons": []},
        "outputs": {
            "ranking": {"exists": True, "sha256": "b" * 64},
            "comparison": {"exists": True, "sha256": "c" * 64},
        },
    }


def ranking_comparison() -> dict:
    return {
        "schema_version": "top10.daily-v2.ranking-comparison.v1",
        "status": "GO",
        "production_switch": {"status": "GO", "executed": False, "reasons": []},
        "top10": {"overlap_count": 10, "same_order": True},
        "numeric_differences": {"core_within_tolerance": True},
    }


class DailyV2ParityTest(unittest.TestCase):
    def test_success_fixture_is_parity_go_but_not_production_switch_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_daily_v2_parity_report(
                production_status=production_status(),
                workflow_manifest=workflow_manifest(root),
                real_shadow_manifest=real_shadow_manifest(root),
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="fixture",
            )

        self.assertEqual(report["status"], "GO")
        self.assertEqual(report["production_switch"]["status"], "NO-GO")
        self.assertIn("production_equivalent_workflow", report["production_switch"]["blockers"])
        self.assertTrue(all(item["type"] == "expected_difference" for item in report["mismatches"]))

    def test_fixture_cannot_be_relabelled_production_equivalent_by_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_daily_v2_parity_report(
                production_status=production_status(),
                workflow_manifest=workflow_manifest(root),
                real_shadow_manifest=real_shadow_manifest(root),
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="production-equivalent",
            )

        self.assertEqual(report["status"], "NO-GO")
        self.assertIn(
            "production_equivalence_attestation_missing",
            {item["code"] for item in report["mismatches"] if item["blocking"]},
        )
        self.assertEqual(report["production_switch"]["status"], "NO-GO")

    def test_stale_ranking_date_is_data_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shadow = real_shadow_manifest(root)
            shadow["run_date"] = "2026-07-08"
            report = build_daily_v2_parity_report(
                production_status=production_status(),
                workflow_manifest=workflow_manifest(root),
                real_shadow_manifest=shadow,
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="fixture",
            )

        self.assertEqual(report["status"], "NO-GO")
        self.assertIn("data_mismatch", {item["type"] for item in report["mismatches"] if item["blocking"]})

    def test_matching_timeout_failure_semantics_are_reported_without_false_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_daily_v2_parity_report(
                production_status=production_status(status="FAILED", failed_step="rank"),
                workflow_manifest=workflow_manifest(root, status="failed", failed_step="rank"),
                real_shadow_manifest=real_shadow_manifest(root),
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="fixture",
            )

        self.assertEqual(report["execution_outcome"], "failed")
        self.assertEqual(report["status"], "GO")
        self.assertEqual(report["production_switch"]["status"], "NO-GO")

    def test_resume_manifest_is_accepted_when_completed_outputs_remain_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_daily_v2_parity_report(
                production_status=production_status(),
                workflow_manifest=workflow_manifest(root, resume_count=1),
                real_shadow_manifest=real_shadow_manifest(root),
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="fixture",
            )

        self.assertEqual(report["resume"]["resume_count"], 1)
        self.assertTrue(report["resume"]["completed_outputs_preserved"])

    def test_partial_output_is_contract_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = workflow_manifest(root)
            workflow["steps"][2]["outputs"][0]["exists"] = False
            report = build_daily_v2_parity_report(
                production_status=production_status(),
                workflow_manifest=workflow,
                real_shadow_manifest=real_shadow_manifest(root),
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="fixture",
            )

        self.assertIn("contract_gap", {item["type"] for item in report["mismatches"] if item["blocking"]})

    def test_publish_ready_status_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = workflow_manifest(root, status="failed", failed_step="publish-ready")
            report = build_daily_v2_parity_report(
                production_status=production_status(),
                workflow_manifest=workflow,
                real_shadow_manifest=real_shadow_manifest(root),
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="fixture",
            )

        self.assertIn("status_mismatch", {item["type"] for item in report["mismatches"] if item["blocking"]})

    def test_live_send_or_source_mutation_is_unsafe_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shadow = real_shadow_manifest(root)
            shadow["live_send_enabled"] = True
            shadow["inputs_unchanged"] = False
            report = build_daily_v2_parity_report(
                production_status=production_status(),
                workflow_manifest=workflow_manifest(root),
                real_shadow_manifest=shadow,
                ranking_comparison=ranking_comparison(),
                shadow_root=root,
                workflow_profile="fixture",
            )

        unsafe = [item for item in report["mismatches"] if item["type"] == "unsafe_side_effect"]
        self.assertGreaterEqual(len(unsafe), 2)
        self.assertEqual(report["status"], "NO-GO")

    def test_tampered_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = {
                "production_status": production_status(),
                "workflow_manifest": workflow_manifest(root),
                "real_shadow_manifest": real_shadow_manifest(root),
                "ranking_comparison": ranking_comparison(),
            }
            report = build_daily_v2_parity_report(
                **sources,
                shadow_root=root,
                workflow_profile="fixture",
            )
            tampered = deepcopy(report)
            tampered["status"] = "GO" if report["status"] != "GO" else "NO-GO"

            with self.assertRaisesRegex(DailyV2ParityError, "重算結果不一致"):
                verify_daily_v2_parity_report(
                    tampered,
                    **sources,
                    shadow_root=root,
                    workflow_profile="fixture",
                )

    def test_file_backed_report_binds_source_digests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payloads = {
                "production_status": production_status(),
                "workflow_manifest": workflow_manifest(root),
                "real_shadow_manifest": real_shadow_manifest(root),
                "ranking_comparison": ranking_comparison(),
            }
            paths = {}
            for label, payload in payloads.items():
                path = root / f"{label}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[label] = path
            report = build_daily_v2_parity_report_from_files(
                production_status_path=paths["production_status"],
                workflow_manifest_path=paths["workflow_manifest"],
                real_shadow_manifest_path=paths["real_shadow_manifest"],
                ranking_comparison_path=paths["ranking_comparison"],
                shadow_root=root,
                workflow_profile="fixture",
            )
            verify_daily_v2_parity_report_from_files(report)

            paths["production_status"].write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(DailyV2ParityError, "digest 不一致"):
                verify_daily_v2_parity_report_from_files(report)


if __name__ == "__main__":
    unittest.main()
