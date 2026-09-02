from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_external_fog_revalidation as revalidation


class ExternalFogRevalidationTest(unittest.TestCase):
    def test_run_cycle_rejects_guard_ok_when_topic_runs_are_empty(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-external-fog-empty-") as tmp:
            sandbox = Path(tmp)
            receipt_path = (
                sandbox
                / "logs"
                / "storage_safety"
                / f"{revalidation.JOB}_latest.json"
            )
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps({"status": "OK", "child_exit_code": 0, "reasons": []}),
                encoding="utf-8",
            )
            (sandbox / revalidation.EVIDENCE_DIR).mkdir(parents=True)

            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            with mock.patch.object(revalidation.subprocess, "run", return_value=completed):
                code, receipt = revalidation.run_cycle(
                    sandbox,
                    sandbox / "marker.json",
                    sandbox / "contract.json",
                    1,
                )

            self.assertEqual(code, 70)
            self.assertEqual(receipt["status"], "STOPPED")
            self.assertIn("REPRESENTATIVE_WORKLOAD_EMPTY", receipt["reasons"])
            published = json.loads(
                (sandbox / revalidation.EVIDENCE_DIR / "cycle-1.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(published["status"], "STOPPED")
            self.assertEqual(
                published["representative_workload"]["topic_run_count"],
                0,
            )

    def test_run_cycle_rejects_unchanged_topic_runs_copied_from_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-external-fog-stale-") as tmp:
            sandbox = Path(tmp)
            receipt_path = (
                sandbox
                / "logs"
                / "storage_safety"
                / f"{revalidation.JOB}_latest.json"
            )
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps({"status": "OK", "child_exit_code": 0, "reasons": []}),
                encoding="utf-8",
            )
            run_artifact = (
                sandbox
                / "artifacts"
                / "autonomous_research"
                / "autonomous_research_daily_quota_2026-09-02.json"
            )
            run_artifact.parent.mkdir(parents=True)
            run_artifact.write_text(
                json.dumps({"topic_runs": [{"topic": {"topic_id": "stale"}}]}),
                encoding="utf-8",
            )
            (sandbox / revalidation.EVIDENCE_DIR).mkdir(parents=True)

            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            with mock.patch.object(revalidation.subprocess, "run", return_value=completed):
                code, receipt = revalidation.run_cycle(
                    sandbox,
                    sandbox / "marker.json",
                    sandbox / "contract.json",
                    1,
                )

            self.assertEqual(code, 70)
            self.assertIn("REPRESENTATIVE_WORKLOAD_STALE", receipt["reasons"])

    def test_contract_pins_entrypoint_and_runner_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-external-fog-contract-") as tmp:
            sandbox = Path(tmp)
            entrypoint = sandbox / "scripts" / "storage_validation" / "fog_research_worker.py"
            runner = sandbox / "scripts" / "run_fog_research_worker.sh"
            entrypoint.parent.mkdir(parents=True)
            entrypoint.write_text("print('entrypoint')\n", encoding="utf-8")
            runner.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

            source_commit = "a" * 40
            marker_path, contract_path = revalidation.build_validation_contract(
                sandbox, source_commit
            )
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            contract = json.loads(contract_path.read_text(encoding="utf-8"))

            self.assertEqual(contract["job"], revalidation.JOB)
            self.assertEqual(contract["entrypoint_sha256"], revalidation.sha256_file(entrypoint))
            self.assertEqual(
                contract["argv"],
                ["--runner-sha256", revalidation.sha256_file(runner), "--source-commit", source_commit],
            )
            registration = marker["trusted_entrypoints"][revalidation.JOB]
            self.assertEqual(registration["contract_sha256"], revalidation.sha256_file(contract_path))
            self.assertEqual(marker["sandbox_root"], str(sandbox))

    def test_main_requires_lifecycle_owned_root(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "tmp_artifact_lifecycle"):
                revalidation.main()

    def test_publish_evidence_uses_fresh_destination(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-external-fog-evidence-") as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "published"
            source.mkdir()
            (source / "summary.json").write_text("{}\n", encoding="utf-8")

            revalidation.publish_evidence(source, destination)

            self.assertEqual((destination / "summary.json").read_text(encoding="utf-8"), "{}\n")
            with self.assertRaises(FileExistsError):
                revalidation.publish_evidence(source, destination)

    def test_project_policy_fits_measured_full_sandbox(self) -> None:
        policy = json.loads(
            (revalidation.PROJECT_ROOT / "config" / "project_sandbox_policy.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(policy["defaults"], policy["hard_limits"])
        self.assertEqual(policy["defaults"]["max_bytes"], 5 * 1024**3)
        self.assertEqual(policy["defaults"]["max_file_count"], 50_000)


if __name__ == "__main__":
    unittest.main()
