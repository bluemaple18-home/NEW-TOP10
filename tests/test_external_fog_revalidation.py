from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_external_fog_revalidation as revalidation


class ExternalFogRevalidationTest(unittest.TestCase):
    def test_contract_pins_entrypoint_and_runner_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-external-fog-contract-") as tmp:
            sandbox = Path(tmp)
            entrypoint = sandbox / "scripts" / "storage_validation" / "fog_research_worker.py"
            runner = sandbox / "scripts" / "run_fog_research_worker.sh"
            entrypoint.parent.mkdir(parents=True)
            entrypoint.write_text("print('entrypoint')\n", encoding="utf-8")
            runner.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

            marker_path, contract_path = revalidation.build_validation_contract(sandbox)
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            contract = json.loads(contract_path.read_text(encoding="utf-8"))

            self.assertEqual(contract["job"], revalidation.JOB)
            self.assertEqual(contract["entrypoint_sha256"], revalidation.sha256_file(entrypoint))
            self.assertEqual(contract["argv"], ["--runner-sha256", revalidation.sha256_file(runner)])
            registration = marker["trusted_entrypoints"][revalidation.JOB]
            self.assertEqual(registration["contract_sha256"], revalidation.sha256_file(contract_path))
            self.assertEqual(marker["sandbox_root"], str(sandbox))

    def test_main_requires_lifecycle_owned_root(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "tmp_artifact_lifecycle"):
                revalidation.main()

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
