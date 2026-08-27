from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.automation.status_contract import AutomationStatus
from scripts import run_isolated_daily_backfill as backfill
from scripts.run_automation import AutomationRunner


class IsolatedDailyBackfillTest(unittest.TestCase):
    def test_entrypoint_help_runs_when_called_as_script(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "run_isolated_daily_backfill.py"), "--help"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Run isolated NEW-TOP10 daily backfill", completed.stdout)

    def test_output_root_must_stay_under_isolated_backfill_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-isolated-root-") as tmp:
            source = Path(tmp).resolve()
            with self.assertRaisesRegex(backfill.BackfillNoGo, "output_root must stay under"):
                backfill.resolve_output_root(source, source / "artifacts" / "ranking_2026-08-03.csv")

    def test_strict_run_date_guard_stops_before_ranking_on_date_mismatch(self) -> None:
        runner = AutomationRunner.__new__(AutomationRunner)
        runner.strict_run_date = True
        runner.run_date = "2026-08-04"
        runner.status = AutomationStatus(
            schema_version="daily-run-status.v1",
            mode="daily",
            status="RUNNING",
            dry_run=False,
            started_at="2026-08-27T00:00:00+00:00",
            run_date="2026-08-04",
            metadata={"data_freshness": {"datasets": {"features.parquet": {"latest_date": "2026-08-03"}}}},
        )
        runner._now = lambda: "2026-08-27T00:00:00+00:00"

        with self.assertRaisesRegex(RuntimeError, "strict run_date mismatch"):
            runner._guard_strict_run_date()

        self.assertEqual(runner.status.steps[-1].name, "data.freshness.strict_run_date")
        self.assertEqual(runner.status.steps[-1].status, "FAILED")

    def test_run_backfill_records_representative_capacity_manifest_and_formal_baseline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-isolated-backfill-") as tmp:
            source = Path(tmp).resolve()
            (source / "artifacts" / "isolated_daily_backfill").mkdir(parents=True)
            (source / "artifacts" / "ranking_2026-08-01.csv").write_text("stock_id,rank\n2330,1\n", encoding="utf-8")
            evidence = source / "docs" / "evidence" / backfill.CARD_ID
            output = source / backfill.DEFAULT_OUTPUT_RELATIVE
            raw_evidence = output / "evidence"
            calls: list[str] = []

            def fake_run_cycle(source_root, output_root, run_day, lookback_days):
                del source_root, lookback_days
                calls.append(run_day.isoformat())
                marker = output_root / "artifacts" / f"ranking_{run_day.isoformat()}.csv"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("stock_id,rank,final_score\n2330,1,0.9\n", encoding="utf-8")
                return {
                    "schema_version": "top10-isolated-daily-cycle.v1",
                    "status": "OK",
                    "run_date": run_day.isoformat(),
                    "validation": {
                        "ranking_rows": 1,
                        "feature_latest_date": run_day.isoformat(),
                        "artifacts": {"ranking": {"path": str(marker.relative_to(output_root)), "sha256": "fixture"}},
                    },
                    "external_write_contract": {
                        "run_daily_publish": False,
                        "clawd_live_send": False,
                        "ops_live_send": False,
                        "external_review": False,
                        "scheduler_change": False,
                    },
                }

            args = SimpleNamespace(
                source_root=source,
                output_root=output,
                evidence_dir=None,
                sanitized_receipt_path=evidence / "sanitized_receipt.md",
                start_date=backfill.parse_date("2026-08-03"),
                end_date=backfill.parse_date("2026-08-05"),
                representative_date=backfill.parse_date("2026-08-04"),
                lookback_days=420,
            )
            with mock.patch.object(
                backfill,
                "run_shared_etl",
                return_value={"schema_version": "top10-isolated-backfill-shared-etl.v1", "status": "OK"},
            ), mock.patch.object(
                backfill,
                "available_feature_dates",
                return_value={"2026-08-03", "2026-08-04", "2026-08-05"},
            ), mock.patch.object(backfill, "run_cycle", side_effect=fake_run_cycle), mock.patch.object(
                backfill,
                "launchd_status",
                return_value={"command": ["launchctl", "list", "com.new-top10.daily"], "exit_code": 0, "loaded": True},
            ):
                manifest = backfill.run_backfill(args)

            self.assertEqual(manifest["status"], "DELIVERED_CANDIDATE")
            self.assertEqual(calls, ["2026-08-04", "2026-08-03", "2026-08-05"])
            self.assertEqual(manifest["capacity"]["status"], "PASS")
            self.assertEqual(manifest["formal_baseline_comparison"]["status"], "PASS")
            self.assertTrue((raw_evidence / "capacity-receipt.json").exists())
            self.assertTrue((raw_evidence / "launchd-before.json").exists())
            self.assertTrue((evidence / "sanitized_receipt.md").exists())
            receipt_text = (evidence / "sanitized_receipt.md").read_text(encoding="utf-8")
            self.assertNotIn("rm -rf", receipt_text)
            self.assertNotIn(str(source), receipt_text)
            self.assertNotIn(str(output), receipt_text)
            self.assertNotIn("rollback_command", json.dumps(manifest))
            self.assertNotIn("rm -rf", json.dumps(manifest))
            self.assertFalse(manifest["completed"][0]["external_write_contract"]["run_daily_publish"])

    def test_default_evidence_dir_does_not_write_repo_docs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-isolated-backfill-default-evidence-") as tmp:
            source = Path(tmp).resolve()
            (source / "artifacts" / "isolated_daily_backfill").mkdir(parents=True)
            output = source / backfill.DEFAULT_OUTPUT_RELATIVE

            args = SimpleNamespace(
                source_root=source,
                output_root=output,
                evidence_dir=None,
                sanitized_receipt_path=None,
                start_date=backfill.parse_date("2026-08-03"),
                end_date=backfill.parse_date("2026-08-03"),
                representative_date=backfill.parse_date("2026-08-03"),
                lookback_days=420,
            )

            with mock.patch.object(
                backfill,
                "run_shared_etl",
                return_value={"schema_version": "top10-isolated-backfill-shared-etl.v1", "status": "OK"},
            ), mock.patch.object(
                backfill,
                "available_feature_dates",
                return_value={"2026-08-03"},
            ), mock.patch.object(
                backfill,
                "run_cycle",
                return_value={
                    "schema_version": "top10-isolated-daily-cycle.v1",
                    "status": "OK",
                    "run_date": "2026-08-03",
                    "external_write_contract": {"run_daily_publish": False},
                },
            ), mock.patch.object(
                backfill,
                "launchd_status",
                return_value={"command": ["launchctl", "list", "com.new-top10.daily"], "exit_code": 0, "loaded": True},
            ):
                manifest = backfill.run_backfill(args)

            self.assertTrue((output / "evidence" / "capacity-receipt.json").exists())
            self.assertFalse((source / "docs" / "evidence" / backfill.CARD_ID).exists())
            self.assertEqual(str(output / "evidence"), manifest["roots"]["evidence_dir"])

    def test_validate_daily_outputs_requires_same_day_non_empty_ranking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-isolated-validate-") as tmp:
            root = Path(tmp).resolve()
            artifacts = root / "artifacts"
            artifacts.mkdir()
            run_date = "2026-08-03"
            (artifacts / f"ranking_{run_date}.csv").write_text("stock_id,rank,final_score\n2330,1,0.9\n", encoding="utf-8")
            (artifacts / f"daily_run_summary_{run_date}.json").write_text(json.dumps({"status": "OK"}), encoding="utf-8")
            (artifacts / f"automation_status_{run_date}.json").write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "run_date": run_date,
                        "metadata": {
                            "data_freshness": {
                                "datasets": {"features.parquet": {"latest_date": "2026-08-02"}}
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            for name in ["daily_report", "clawd_publish_payload"]:
                (artifacts / f"{name}_{run_date}.json").write_text("{}", encoding="utf-8")
            (artifacts / f"clawd_publish_message_{run_date}.md").write_text("fixture\n", encoding="utf-8")

            with self.assertRaisesRegex(backfill.BackfillNoGo, "feature latest_date mismatch"):
                backfill.validate_daily_outputs(root, backfill.parse_date(run_date))


if __name__ == "__main__":
    unittest.main()
