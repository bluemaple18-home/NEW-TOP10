"""FinMind 統計跨 ETL 子程序與 Daily status 的離線契約。"""

import json
import sys
from types import SimpleNamespace

from app.automation.status_contract import AutomationStatus
from app import pipeline_cli
from scripts.run_automation import AutomationRunner, RuntimePaths, _DailyActions


def _runner(tmp_path):
    runner = object.__new__(AutomationRunner)
    runner.runtime_paths = RuntimePaths(tmp_path, tmp_path, tmp_path)
    runner.status = AutomationStatus("daily-run-status.v1", "daily", "RUNNING", False,
                                     "2026-10-22T00:00:00Z", "2026-10-22")
    runner.mode = "daily"
    runner.run_date = "2026-10-22"
    runner.dry_run = False
    runner.backfill = False
    runner.validation_mode = False
    runner._now = lambda: "2026-10-22T00:01:00Z"
    return runner


def _coverage(failed=0):
    return {
        "status": "partial" if failed else "ok", "limit": 600, "used": 0,
        "remaining": 600, "required_fetch_count": 401, "next_available_time": None,
        "expected_fetch_count": 400, "received_fetch_count": 400 - failed,
        "failed_fetch_count": failed, "failed_stock_count": failed,
        "by_dataset": {
            "institutional": {"expected_stock_count": 200, "received_stock_count": 200,
                              "failed_stock_count": 0},
            "margin": {"expected_stock_count": 200, "received_stock_count": 200 - failed,
                       "failed_stock_count": failed},
        },
    }


def test_pipeline_cli_exports_context_stats_offline(tmp_path, monkeypatch):
    stats = _coverage()
    pipeline = SimpleNamespace(context={"stats": {"finmind": stats}}, run=lambda **_: None)
    monkeypatch.setattr(pipeline_cli, "build_pipeline", lambda **_: pipeline)
    output = tmp_path / "stats.json"
    monkeypatch.setattr(sys, "argv", ["pipeline_cli", "run", "--finmind-stats-output", str(output)])
    assert pipeline_cli.main() == 0
    assert json.loads(output.read_text()) == stats


def test_daily_status_persists_coverage_and_quota(tmp_path):
    runner = _runner(tmp_path)
    runner._pipeline_run_command = lambda: ["python", "-m", "app.pipeline_cli", "run"]

    def execute(name, command):
        assert name == "etl" and command[-2] == "--finmind-stats-output"
        from pathlib import Path
        Path(command[-1]).write_text(json.dumps(_coverage()))

    runner._run_command = execute
    _DailyActions(runner).run_etl()
    runner.status.status = "OK"
    runner._write_status()
    saved = json.loads((tmp_path / "artifacts/automation_status_2026-10-22.json").read_text())
    assert saved["metadata"]["finmind"] == _coverage()


def test_missing_coverage_marks_daily_incomplete(tmp_path):
    runner = _runner(tmp_path)
    runner._pipeline_run_command = lambda: ["python", "-m", "app.pipeline_cli", "run"]
    runner._run_command = lambda name, command: None
    _DailyActions(runner).run_etl()
    runner._write_status()
    saved = json.loads((tmp_path / "artifacts/automation_status_2026-10-22.json").read_text())
    assert saved["status"] == "INCOMPLETE"
    assert saved["metadata"]["finmind"]["reason_code"] == "FINMIND_COVERAGE_MISSING"


def test_margin_100_failures_remain_visible_by_dataset(tmp_path):
    runner = _runner(tmp_path)
    path = tmp_path / "finmind.json"
    path.write_text(json.dumps(_coverage(100)))
    runner._record_finmind_stats(path)
    runner.status.status = "OK"
    runner._write_status()
    saved = json.loads((tmp_path / "artifacts/automation_status_2026-10-22.json").read_text())
    stats = saved["metadata"]["finmind"]
    assert stats["failed_fetch_count"] == stats["failed_stock_count"] == 100
    assert stats["by_dataset"]["margin"]["failed_stock_count"] == 100
    assert stats["by_dataset"]["institutional"]["failed_stock_count"] == 0
