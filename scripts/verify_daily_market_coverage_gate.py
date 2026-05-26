#!/usr/bin/env python3
"""驗證 daily freshness 會擋住最新日只覆蓋單一市場的資料。"""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scripts.run_automation as automation
from app.pipeline.validation import PipelineDataValidator


def main() -> int:
    original_root = automation.PROJECT_ROOT
    original_status = automation.STATUS_PATH
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_project(root)
            automation.PROJECT_ROOT = root
            automation.STATUS_PATH = root / "artifacts" / "automation_status.json"

            runner = automation.AutomationRunner(mode="daily", dry_run=True)
            try:
                runner._record_data_freshness("data.freshness.test")
            except RuntimeError as exc:
                assert "TWSE actual=0" in str(exc)
            else:
                raise AssertionError("missing TWSE latest market coverage should fail")
            validator = PipelineDataValidator(data_dir=root / "data")
            summary = validator.validate_contract(validator.features_contract())
            assert any(
                issue.severity == "ERROR" and "TWSE actual=0" in issue.message
                for issue in summary.issues
            ), "pipeline contract should reject missing TWSE latest market coverage"

            write_clean_data(root, twse_count=60, tpex_count=60)
            runner = automation.AutomationRunner(mode="daily", dry_run=True)
            runner._record_data_freshness("data.freshness.test")
            step = runner.status.steps[-1]
            assert step.status == "OK"
            coverage = runner.status.metadata["data_freshness"]["datasets"]["features.parquet"]["latest_market_coverage"]
            assert {item["status"] for item in coverage["markets"]} == {"OK"}
            validator = PipelineDataValidator(data_dir=root / "data")
            summary = validator.validate_contract(validator.features_contract())
            coverage_errors = [issue for issue in summary.issues if "最新日期市場覆蓋不足" in issue.message]
            assert not coverage_errors, f"pipeline contract should pass balanced latest market coverage: {coverage_errors}"
    finally:
        automation.PROJECT_ROOT = original_root
        automation.STATUS_PATH = original_status
    print("DAILY_MARKET_COVERAGE_GATE_OK")
    return 0


def prepare_project(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "artifacts").mkdir(parents=True)
    (root / "data" / "clean").mkdir(parents=True)
    (root / "data" / "reference").mkdir(parents=True)
    (root / "config" / "automation.yaml").write_text(
        "\n".join(
            [
                'timezone: "Asia/Taipei"',
                "daily:",
                "  max_data_lag_days: 9999",
                "  market_coverage_enabled: true",
                '  required_market_types: ["twse", "tpex"]',
                "  min_latest_market_coverage_ratio: 0.5",
            ]
        ),
        encoding="utf-8",
    )
    universe_rows = []
    for market in ("twse", "tpex"):
        for index in range(100):
            prefix = "1" if market == "twse" else "6"
            universe_rows.append(
                {
                    "stock_id": f"{prefix}{index:03d}",
                    "market_type": market,
                    "is_active": True,
                    "is_etf": False,
                }
            )
    pd.DataFrame(universe_rows).to_csv(root / "data" / "reference" / "tradable_universe.csv", index=False)
    write_clean_data(root, twse_count=0, tpex_count=100)


def write_clean_data(root: Path, twse_count: int, tpex_count: int) -> None:
    latest = pd.Timestamp("2026-05-25")
    rows = []
    for market, count in (("TWSE", twse_count), ("TPEX", tpex_count)):
        for index in range(count):
            prefix = "1" if market == "TWSE" else "6"
            rows.append(
                {
                    "date": latest,
                    "stock_id": f"{prefix}{index:03d}",
                    "market": market,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.5,
                    "volume": 1000,
                    "ma5": 10.3,
                    "ma20": 10.0,
                    "rsi": 55.0,
                    "macd": 0.1,
                    "macd_signal": 0.05,
                    "bb_middle": 10.0,
                    "avg_value_20d": 30_000_000,
                }
            )
    clean = root / "data" / "clean"
    frame = pd.DataFrame(rows)
    frame.to_parquet(clean / "features.parquet", index=False)
    frame[["date", "stock_id"]].assign(event_flag=0).to_parquet(clean / "events.parquet", index=False)
    frame[["date", "stock_id", "close", "avg_value_20d"]].to_parquet(clean / "universe.parquet", index=False)


if __name__ == "__main__":
    raise SystemExit(main())
