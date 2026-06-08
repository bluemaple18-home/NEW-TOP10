#!/usr/bin/env python3
"""驗證 daily pipeline window override 不會被舊資料 preflight 擋住。"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from datetime import timedelta

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_automation as automation


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        build_fixture(root)

        original_root = automation.PROJECT_ROOT
        original_status_path = automation.STATUS_PATH
        original_start_date = os.environ.get("TOP10_PIPELINE_START_DATE")
        original_end_date = os.environ.get("TOP10_PIPELINE_END_DATE")
        try:
            automation.PROJECT_ROOT = root
            automation.STATUS_PATH = root / "artifacts" / "automation_status.json"
            os.environ.pop("TOP10_PIPELINE_START_DATE", None)
            os.environ.pop("TOP10_PIPELINE_END_DATE", None)

            blocked = automation.AutomationRunner("daily", dry_run=True)
            try:
                blocked._daily_preflight()
            except RuntimeError as exc:
                assert "市場覆蓋檢查失敗" in str(exc)
            else:
                raise AssertionError("preflight without pipeline window should fail on incomplete latest market coverage")

            write_config(root, pipeline_lookback_days=420)
            default_runner = automation.AutomationRunner("daily", dry_run=True)
            default_command = default_runner._pipeline_run_command()
            default_end = default_runner._today_local().date()
            default_start = default_end - timedelta(days=420)
            assert default_command == [
                "python",
                "-m",
                "app.pipeline_cli",
                "run",
                "--start-date",
                default_start.isoformat(),
                "--end-date",
                default_end.isoformat(),
            ]
            assert default_runner.status.metadata["pipeline_window"] == {
                "end_date": default_end.isoformat(),
                "start_date": default_start.isoformat(),
            }
            assert default_runner.status.metadata["pipeline_window_policy"]["lookback_days"] == 420

            os.environ["TOP10_PIPELINE_END_DATE"] = "2026-05-26"
            runner = automation.AutomationRunner("daily", dry_run=True)
            runner._daily_preflight()
            command = runner._pipeline_run_command()
            steps = {step.name: step for step in runner.status.steps}

            assert command == [
                "python",
                "-m",
                "app.pipeline_cli",
                "run",
                "--start-date",
                "2025-04-01",
                "--end-date",
                "2026-05-26",
            ]
            assert runner.status.metadata["pipeline_window"] == {"end_date": "2026-05-26", "start_date": "2025-04-01"}
            assert steps["data.freshness.preflight"].status == "WARN"
            assert "deferred until ETL" in (steps["data.freshness.preflight"].message or "")
        finally:
            automation.PROJECT_ROOT = original_root
            automation.STATUS_PATH = original_status_path
            if original_start_date is None:
                os.environ.pop("TOP10_PIPELINE_START_DATE", None)
            else:
                os.environ["TOP10_PIPELINE_START_DATE"] = original_start_date
            if original_end_date is None:
                os.environ.pop("TOP10_PIPELINE_END_DATE", None)
            else:
                os.environ["TOP10_PIPELINE_END_DATE"] = original_end_date

    print("DAILY_PIPELINE_WINDOW_OVERRIDE_OK")
    return 0


def build_fixture(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "requirements.txt").write_text("", encoding="utf-8")
    (root / "artifacts").mkdir()
    (root / "models").mkdir()
    (root / "models" / "latest_lgbm.pkl").write_bytes(b"placeholder")
    (root / "data" / "clean").mkdir(parents=True)
    (root / "data" / "reference").mkdir(parents=True)

    write_config(root, pipeline_lookback_days=0)
    pd.DataFrame(
        [
            {"stock_id": "1001", "market_type": "twse", "is_active": True, "is_etf": False},
            {"stock_id": "1002", "market_type": "twse", "is_active": True, "is_etf": False},
            {"stock_id": "2001", "market_type": "tpex", "is_active": True, "is_etf": False},
            {"stock_id": "2002", "market_type": "tpex", "is_active": True, "is_etf": False},
        ]
    ).to_csv(root / "data" / "reference" / "tradable_universe.csv", index=False)

    latest = pd.Timestamp("2026-05-27")
    features = pd.DataFrame(
        [
            {"date": latest, "stock_id": "1001", "market": "TWSE", "close": 10.0},
            {"date": latest, "stock_id": "1002", "market": "TWSE", "close": 11.0},
        ]
    )
    features.to_parquet(root / "data" / "clean" / "features.parquet", index=False)
    pd.DataFrame([{"date": latest, "stock_id": "1001"}]).to_parquet(root / "data" / "clean" / "events.parquet", index=False)
    pd.DataFrame([{"date": latest, "stock_id": "1001"}]).to_parquet(root / "data" / "clean" / "universe.parquet", index=False)


def write_config(root: Path, pipeline_lookback_days: int) -> None:
    (root / "config" / "automation.yaml").write_text(
        "\n".join(
            [
                'timezone: "Asia/Taipei"',
                "daily:",
                "  market_coverage_enabled: true",
                f"  pipeline_lookback_days: {pipeline_lookback_days}",
                '  required_market_types: ["twse", "tpex"]',
                "  min_latest_market_coverage_ratio: 0.5",
                "  max_data_lag_days: 7",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
