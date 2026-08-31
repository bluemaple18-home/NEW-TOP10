from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pandas as pd

from scripts.run_automation import AutomationRunner


def test_freshness_reads_only_the_columns_needed_for_dates(tmp_path) -> None:
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    for filename in ("features.parquet", "events.parquet", "universe.parquet"):
        pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-08-31"]),
                "stock_id": ["2330"],
                "market": ["twse"],
                "unused_wide_column": ["x" * 1024],
            }
        ).to_parquet(clean_dir / filename, index=False)

    runner = object.__new__(AutomationRunner)
    runner.runtime_paths = SimpleNamespace(clean_data_dir=clean_dir)
    runner.config = {"daily": {"market_coverage_enabled": False}}
    runner.status = SimpleNamespace(metadata={})
    runner._today_local = lambda: datetime(2026, 8, 31)
    runner._record_step = mock.Mock()

    original_read_parquet = pd.read_parquet
    requested_columns: list[list[str] | None] = []

    def read_parquet(path, *args, **kwargs):
        requested_columns.append(kwargs.get("columns"))
        return original_read_parquet(path, *args, **kwargs)

    with mock.patch("pandas.read_parquet", side_effect=read_parquet):
        runner._record_data_freshness("data.freshness.after_etl")

    assert requested_columns == [["date"], ["date"], ["date"]]
