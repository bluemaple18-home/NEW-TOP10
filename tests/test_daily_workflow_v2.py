from __future__ import annotations

import json
import pickle
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.contracts.daily_v2 import DailyStep, StepSpec
from app.workflows.daily_v2 import DailyWorkflowV2, WorkflowExecutionError


RUN_DATE = "2026-07-13"
RUN_ID = "shadow-20260713-test"


def write_text_command(path: str, content: str) -> tuple[str, ...]:
    code = (
        "from pathlib import Path; import sys; "
        "path = Path(sys.argv[1]); path.parent.mkdir(parents=True, exist_ok=True); "
        "path.write_text(sys.argv[2], encoding='utf-8')"
    )
    return (sys.executable, "-c", code, path, content)


def ranking_csv(run_date: str, count: int = 10) -> str:
    lines = ["rank,stock_id,score,run_date"]
    lines.extend(
        f"{rank},{1000 + rank},{1 - rank / 100:.2f},{run_date}"
        for rank in range(1, count + 1)
    )
    return "\n".join(lines) + "\n"


class DailyWorkflowV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="top10-daily-v2-")
        self.root = Path(self.tempdir.name)
        self.model_path = self.root / "fixture_model.pkl"
        with self.model_path.open("wb") as handle:
            pickle.dump({"model": "fixture", "feature_names": ["score"]}, handle)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def specs(
        self,
        *,
        ranking_date: str = RUN_DATE,
        ranking_count: int = 10,
        etl_command: tuple[str, ...] | None = None,
        report_command: tuple[str, ...] | None = None,
    ) -> tuple[StepSpec, ...]:
        etl = etl_command or write_text_command(
            "{run_dir}/features.json",
            json.dumps({"run_date": RUN_DATE, "rows": 20}),
        )
        report = report_command or write_text_command(
            "{run_dir}/report.json",
            json.dumps({"run_date": RUN_DATE, "shadow_only": True}),
        )
        return (
            StepSpec(
                name=DailyStep.ETL,
                command=etl,
                inputs=(),
                outputs=("features.json",),
                timeout_seconds=2,
            ),
            StepSpec(
                name=DailyStep.VALIDATE,
                command=write_text_command(
                    "{run_dir}/validation.json",
                    json.dumps({"run_date": RUN_DATE, "valid": True}),
                ),
                inputs=("features.json", str(self.model_path)),
                outputs=("validation.json",),
                timeout_seconds=2,
            ),
            StepSpec(
                name=DailyStep.RANK,
                command=write_text_command(
                    f"{{run_dir}}/ranking_{RUN_DATE}.csv",
                    ranking_csv(ranking_date, ranking_count),
                ),
                inputs=("validation.json", str(self.model_path)),
                outputs=(f"ranking_{RUN_DATE}.csv",),
                timeout_seconds=2,
            ),
            StepSpec(
                name=DailyStep.REPORT,
                command=report,
                inputs=(f"ranking_{RUN_DATE}.csv",),
                outputs=("report.json",),
                timeout_seconds=2,
            ),
            StepSpec(
                name=DailyStep.PUBLISH_READY,
                command=write_text_command(
                    "{run_dir}/publish_ready.json",
                    json.dumps(
                        {
                            "run_date": RUN_DATE,
                            "shadow_only": True,
                            "send_enabled": False,
                            "publish_ready": True,
                        }
                    ),
                ),
                inputs=(f"ranking_{RUN_DATE}.csv", "report.json"),
                outputs=("publish_ready.json",),
                timeout_seconds=2,
            ),
        )

    def workflow(self, specs: tuple[StepSpec, ...] | None = None) -> DailyWorkflowV2:
        return DailyWorkflowV2(
            run_id=RUN_ID,
            run_date=RUN_DATE,
            run_root=self.root / "runs",
            model_path=self.model_path,
            steps=specs or self.specs(),
        )

    def manifest(self) -> dict[str, object]:
        path = self.root / "runs" / RUN_ID / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_unloadable_model_fails_loud(self) -> None:
        self.model_path.write_bytes(b"not-a-pickle")

        with self.assertRaisesRegex(WorkflowExecutionError, "model.*load"):
            self.workflow().run()

        manifest = self.manifest()
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["steps"][0]["status"], "finished")
        failed = manifest["steps"][1]
        self.assertEqual(failed["status"], "failed")
        self.assertIn("model", failed["failure"]["reason"])

    def test_stale_ranking_fails_loud(self) -> None:
        with self.assertRaisesRegex(WorkflowExecutionError, "ranking date mismatch"):
            self.workflow(self.specs(ranking_date="2026-07-12")).run()

        failed = self.manifest()["steps"][2]
        self.assertEqual(failed["status"], "failed")
        self.assertIn("2026-07-12", failed["failure"]["reason"])

    def test_incomplete_top10_fails_loud(self) -> None:
        with self.assertRaisesRegex(WorkflowExecutionError, "exactly 10"):
            self.workflow(self.specs(ranking_count=9)).run()

        failed = self.manifest()["steps"][2]
        self.assertEqual(failed["status"], "failed")
        self.assertIn("got 9", failed["failure"]["reason"])

    def test_step_timeout_records_command_exit_code_and_stderr(self) -> None:
        timeout_command = (
            sys.executable,
            "-c",
            "import time; time.sleep(1)",
        )
        specs = list(self.specs(etl_command=timeout_command))
        specs[0] = StepSpec(
            name=DailyStep.ETL,
            command=timeout_command,
            inputs=(),
            outputs=("features.json",),
            timeout_seconds=0.05,
        )

        with self.assertRaisesRegex(WorkflowExecutionError, "timed out"):
            self.workflow(tuple(specs)).run()

        failed = self.manifest()["steps"][0]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["failure"]["exit_code"], 124)
        self.assertIn("time.sleep", " ".join(failed["command"]))
        self.assertIn("timed out", failed["failure"]["stderr_summary"])

    def test_resume_skips_finished_steps_and_keeps_prior_artifacts(self) -> None:
        marker = "{run_dir}/report-ready"
        report_command = (
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import json, sys; "
                "marker = Path(sys.argv[1]); output = Path(sys.argv[2]); "
                "sys.exit(7) if not marker.exists() else "
                "output.write_text(json.dumps({'run_date': sys.argv[3], "
                "'shadow_only': True}), encoding='utf-8')"
            ),
            marker,
            "{run_dir}/report.json",
            RUN_DATE,
        )
        workflow = self.workflow(self.specs(report_command=report_command))

        with self.assertRaisesRegex(WorkflowExecutionError, "exit_code=7"):
            workflow.run()

        run_dir = self.root / "runs" / RUN_ID
        protected = [
            run_dir / "features.json",
            run_dir / "validation.json",
            run_dir / f"ranking_{RUN_DATE}.csv",
        ]
        snapshots = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in protected}
        (run_dir / "report-ready").touch()

        resumed = workflow.run()

        self.assertEqual(resumed["status"], "finished")
        for path, snapshot in snapshots.items():
            self.assertEqual((path.stat().st_mtime_ns, path.read_bytes()), snapshot)
        manifest = self.manifest()
        self.assertEqual([step["status"] for step in manifest["steps"]], ["finished"] * 5)
        self.assertEqual([len(step["attempts"]) for step in manifest["steps"]], [1, 1, 1, 2, 1])
        self.assertFalse(any(run_dir.glob("*.tmp")))

    def test_cli_dry_run_completes_entire_shadow_workflow(self) -> None:
        workspace = self.root / "cli-runs"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_daily_v2.py",
                "--dry-run",
                "--run-date",
                RUN_DATE,
                "--run-id",
                "cli-shadow-test",
                "--workspace",
                str(workspace),
            ],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest_path = workspace / "cli-shadow-test" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "finished")
        self.assertTrue(manifest["shadow_only"])
        self.assertFalse(manifest["live_send_enabled"])


if __name__ == "__main__":
    unittest.main()
