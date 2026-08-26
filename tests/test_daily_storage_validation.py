from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = PROJECT_ROOT / "scripts" / "storage_validation" / "daily.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_runner_source_fixture(source: Path) -> None:
    (source / "config").mkdir(parents=True)
    (source / "data" / "reference").mkdir(parents=True)
    (source / "models").mkdir()
    (source / "scripts").mkdir()
    (source / "app" / "automation").mkdir(parents=True)
    (source / "app" / "__init__.py").write_text("", encoding="utf-8")
    (source / "app" / "automation" / "__init__.py").write_text("", encoding="utf-8")
    (source / "requirements.txt").write_text("fixture\n", encoding="utf-8")
    (source / "config" / "signals.yaml").write_text("scoring:\n  weights: {}\n", encoding="utf-8")
    (source / "config" / "automation.yaml").write_text(
        "daily:\n  enabled: true\nnotify:\n  llm_rewrite_enabled: true\n",
        encoding="utf-8",
    )
    (source / "models" / "latest_lgbm.pkl").write_bytes(b"fixture-model")
    (source / "app" / "automation" / "daily_orchestrator.py").write_text(
        textwrap.dedent(
            """
            def run_daily(actions, config):
                actions.guard_resource_profile()
                actions.preflight()
                actions.run_etl()
                actions.validate_data()
                actions.record_data_freshness()
                actions.run_ranking()
                actions.record_ranking()

            def run_daily_final_artifacts(actions, config):
                ranking_path = actions.expected_ranking_path()
                report_path = actions.run_daily_report(config, ranking_path)
                actions.run_clawd_payload(config, report_path)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (source / "scripts" / "run_automation.py").write_text(
        textwrap.dedent(
            """
            import json
            from dataclasses import dataclass, field
            from pathlib import Path

            @dataclass
            class Step:
                name: str
                status: str
                command: list[str] | None = None
                exit_code: int | None = None

            @dataclass
            class Status:
                status: str = "RUNNING"
                run_date: str = "2026-08-27"
                errors: list[str] = field(default_factory=list)
                steps: list[Step] = field(default_factory=list)
                metadata: dict = field(default_factory=dict)

            class Actions:
                def __init__(self, runner):
                    self.runner = runner
                def guard_resource_profile(self): self.runner.status.steps.append(Step("resource_guard.daily", "OK"))
                def preflight(self): self.runner.status.steps.append(Step("daily.schema", "OK"))
                def run_etl(self):
                    clean = self.runner.output_root / "data" / "clean"
                    clean.mkdir(parents=True, exist_ok=True)
                    for name in ["features.parquet", "events.parquet", "universe.parquet"]:
                        (clean / name).write_text("cycle=" + self.runner.cycle_id, encoding="utf-8")
                    self.runner.status.steps.append(Step("etl", "OK", ["python", "-m", "app.pipeline_cli", "run"], 0))
                def validate_data(self): self.runner.status.steps.append(Step("data.validate", "OK", ["python", "-m", "app.pipeline_cli", "validate"], 0))
                def record_data_freshness(self): self.runner.status.metadata["data_freshness"] = {"datasets": {"features.parquet": {"latest_date": self.runner.run_date}}}
                def run_ranking(self):
                    path = self.runner.output_root / "artifacts" / f"ranking_{self.runner.run_date}.csv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("stock_id,score,cycle_id\\n2330,1," + self.runner.cycle_id + "\\n", encoding="utf-8")
                    self.runner.status.steps.append(Step("ranking", "OK", ["python", "-m", "app.agent_b_ranking"], 0))
                def record_ranking(self): self.runner.status.steps.append(Step("ranking.artifact", "OK"))
                def expected_ranking_path(self): return self.runner.output_root / "artifacts" / f"ranking_{self.runner.run_date}.csv"
                def run_daily_report(self, config, ranking_path):
                    report = self.runner.output_root / "artifacts" / f"daily_report_{self.runner.run_date}.json"
                    report.write_text(json.dumps({"ranking_path": str(ranking_path), "cycle_id": self.runner.cycle_id}), encoding="utf-8")
                    self.runner.status.steps.append(Step("daily.report", "OK", ["python", "scripts/generate_daily_report.py"], 0))
                    return report
                def run_clawd_payload(self, config, report_path):
                    payload = self.runner.output_root / "artifacts" / f"clawd_publish_payload_{self.runner.run_date}.json"
                    message = self.runner.output_root / "artifacts" / f"clawd_publish_message_{self.runner.run_date}.md"
                    payload.write_text(json.dumps({"report_path": str(report_path), "cycle_id": self.runner.cycle_id}), encoding="utf-8")
                    message.write_text("cycle=" + self.runner.cycle_id, encoding="utf-8")
                    self.runner.status.steps.append(Step("clawd.payload", "OK", ["python", "scripts/build_clawd_publish_payload.py"], 0))

            class AutomationRunner:
                def __init__(self, mode, dry_run=False, trigger="manual", resource_profile=None, run_date=None, source_root=None, output_root=None, runtime_root=None, validation_mode=False):
                    self.mode = mode
                    self.run_date = run_date
                    self.output_root = Path(output_root)
                    self.cycle_id = Path(runtime_root).name
                    self.status = Status(run_date=run_date, metadata={"validation_mode": validation_mode})
                def run(self):
                    from app.automation.daily_orchestrator import run_daily, run_daily_final_artifacts
                    actions = Actions(self)
                    run_daily(actions, {})
                    run_daily_final_artifacts(actions, {})
                    self.status.status = "OK"
                    return 0
                def _latest_feature_date(self): return self.run_date
                def _status_output_path(self):
                    path = self.output_root / "artifacts" / "automation_status.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}", encoding="utf-8")
                    return path
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def write_real_runner_source_fixture(source: Path) -> None:
    (source / "config").mkdir(parents=True)
    (source / "data" / "reference").mkdir(parents=True)
    (source / "models").mkdir()
    (source / "requirements.txt").write_text("fixture\n", encoding="utf-8")
    (source / "config" / "signals.yaml").write_text("scoring:\n  weights: {}\n", encoding="utf-8")
    (source / "config" / "automation.yaml").write_text(
        "\n".join(
            [
                "timezone: Asia/Taipei",
                "execution:",
                "  resource_profile: standard",
                "daily:",
                "  enabled: true",
                "  weekend_enabled: true",
                "  market_coverage_enabled: false",
                "  max_data_lag_days: 9999",
                "notify:",
                "  clawd_channel: discord",
                "  clawd_to: channel:fixture",
                "  llm_rewrite_enabled: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (source / "models" / "latest_lgbm.pkl").write_bytes(b"fixture-model")


class DailyStorageValidationEntrypointTest(unittest.TestCase):
    def test_real_automation_runner_routes_daily_writes_to_sandbox_and_hard_disables_external_sends(
        self,
    ) -> None:
        from app.automation.execution import CommandOutcome
        from scripts import run_automation
        from scripts.storage_validation import daily as daily_validation

        with tempfile.TemporaryDirectory(prefix="top10-daily-validation-") as tmp:
            fixture_root = Path(tmp).resolve()
            source = fixture_root / "source"
            output = fixture_root / "sandbox"
            runtime = output / "logs" / "storage_safety" / "runtime" / "cycle-1"
            source.mkdir()
            output.mkdir()
            write_real_runner_source_fixture(source)
            source_hash_before = sha256(source / "config" / "automation.yaml")
            commands: list[list[str]] = []

            def fake_execute_command(command, *, python_executable, dry_run, cwd, env, now):
                self.assertEqual(Path(cwd), source)
                self.assertEqual(env["TOP10_SOURCE_ROOT"], str(source))
                self.assertEqual(env["TOP10_OUTPUT_ROOT"], str(output))
                self.assertEqual(env["TOP10_RUNTIME_ROOT"], str(runtime))
                self.assertEqual(env["TOP10_STORAGE_VALIDATION_MODE"], "1")
                commands.append(list(command))
                started = now()
                clean = output / "data" / "clean"
                artifacts = output / "artifacts"
                clean.mkdir(parents=True, exist_ok=True)
                artifacts.mkdir(parents=True, exist_ok=True)
                if command[:3] == ["python", "-m", "app.pipeline_cli"] and "run" in command:
                    frame = pd.DataFrame({"trade_date": ["2026-08-27"], "stock_id": ["2330"], "market": ["twse"]})
                    for filename in ["features.parquet", "events.parquet", "universe.parquet"]:
                        frame.to_parquet(clean / filename)
                elif command[:3] == ["python", "-m", "app.agent_b_ranking"]:
                    self.assertIn(str(clean), command)
                    self.assertIn(str(source / "models"), command)
                    self.assertIn(str(artifacts), command)
                    (artifacts / "ranking_2026-08-27.csv").write_text(
                        "stock_id,score,cycle_id\n2330,1,cycle-1\n",
                        encoding="utf-8",
                    )
                elif command[:2] == ["python", "scripts/generate_daily_report.py"]:
                    ranking = artifacts / "ranking_2026-08-27.csv"
                    (artifacts / "daily_report_2026-08-27.json").write_text(
                        json.dumps(
                            {
                                "ranking_sha256": sha256(ranking),
                                "cycle_id": "cycle-1",
                            },
                            sort_keys=True,
                        ),
                        encoding="utf-8",
                    )
                    (artifacts / "daily_report_2026-08-27.md").write_text("cycle-1\n", encoding="utf-8")
                elif command[:2] == ["python", "scripts/build_clawd_publish_payload.py"]:
                    report = artifacts / "daily_report_2026-08-27.json"
                    (artifacts / "clawd_publish_payload_2026-08-27.json").write_text(
                        json.dumps({"report_sha256": sha256(report), "cycle_id": "cycle-1"}, sort_keys=True),
                        encoding="utf-8",
                    )
                    (artifacts / "clawd_publish_message_2026-08-27.md").write_text("cycle-1\n", encoding="utf-8")
                return CommandOutcome(
                    run_automation.normalize_command(command, python_executable=python_executable),
                    "OK",
                    started,
                    now(),
                    0,
                )

            with mock.patch.object(daily_validation, "_load_source_runner", return_value=run_automation), mock.patch.object(
                run_automation,
                "execute_command",
                side_effect=fake_execute_command,
            ):
                receipt_path = daily_validation.run_validation_cycle(
                    source_root=source,
                    output_root=output,
                    runtime_root=runtime,
                    run_date="2026-08-27",
                    cycle_id="cycle-1",
                )

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "OK")
            self.assertTrue(receipt["source_identity_unchanged"])
            self.assertEqual(sha256(source / "config" / "automation.yaml"), source_hash_before)
            self.assertEqual(receipt["external_send_contract"]["clawd_send_enabled"], False)
            self.assertEqual(receipt["external_send_contract"]["llm_rewrite_enabled"], False)
            command_names = [item["name"] for item in receipt["commands"]]
            self.assertEqual(command_names, ["etl", "data.validate", "ranking", "daily.report", "clawd.payload"])
            flattened_commands = " ".join(" ".join(command) for command in commands)
            self.assertNotIn("run_daily_publish.sh", flattened_commands)
            self.assertNotIn("send_daily_ops_report.py", flattened_commands)
            self.assertIn("clawd.payload.llm_rewrite", receipt["orchestrator_call_sequence"])
            self.assertIn("cycle-1", (output / "artifacts" / "ranking_2026-08-27.csv").read_text(encoding="utf-8"))
            payload = json.loads((output / "artifacts" / "clawd_publish_payload_2026-08-27.json").read_text(encoding="utf-8"))
            report = output / "artifacts" / "daily_report_2026-08-27.json"
            self.assertEqual(payload["report_sha256"], sha256(report))

    def test_entrypoint_cli_imports_source_runner_inside_sandbox_with_no_git_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-daily-validation-cli-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            runtime = sandbox / "logs" / "storage_safety" / "runtime" / "cycle-1"
            sandbox.mkdir()
            source.mkdir()
            write_runner_source_fixture(source)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(ENTRYPOINT),
                    "--source-root",
                    str(source),
                    "--output-root",
                    str(sandbox),
                    "--runtime-root",
                    str(runtime),
                    "--run-date",
                    "2026-08-27",
                    "--cycle-id",
                    "cycle-1",
                ],
                cwd=sandbox,
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            receipt = json.loads(Path(payload["receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(receipt["canonical_orchestrator"], "app.automation.daily_orchestrator")
            self.assertTrue(receipt["source_identity_unchanged"])
            self.assertEqual(receipt["artifacts"]["ranking"]["sha256"], sha256(sandbox / "artifacts" / "ranking_2026-08-27.csv"))
            self.assertFalse((source / "__pycache__").exists())

            (sandbox / ".git").mkdir()
            blocked = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(ENTRYPOINT),
                    "--source-root",
                    str(source),
                    "--output-root",
                    str(sandbox),
                    "--run-date",
                    "2026-08-27",
                    "--cycle-id",
                    "cycle-2",
                ],
                cwd=sandbox,
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )

            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("git checkout", blocked.stderr)


if __name__ == "__main__":
    unittest.main()
