from __future__ import annotations

from unittest import mock

import pandas as pd

from app.agent_b_ranking import StockRanker
from app.modeling import feature_contract
from app.modeling.feature_contract import FeatureFrameMetadata


def _metadata() -> FeatureFrameMetadata:
    return FeatureFrameMetadata(
        feature_groups={},
        rows=1,
        stocks=1,
        start_date="2026-08-31",
        end_date="2026-08-31",
        fundamental_cache_coverage=0.0,
        notes=[],
    )


def test_ranking_reads_only_universe_keys(tmp_path) -> None:
    data_dir = tmp_path / "clean"
    data_dir.mkdir()
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-31"]),
            "stock_id": ["2330"],
            "unused_wide_column": ["x" * 1024],
        }
    ).to_parquet(data_dir / "universe.parquet", index=False)
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-31"]),
            "trade_date": pd.to_datetime(["2026-08-31"]),
            "stock_id": ["2330"],
            "high": [10.0],
            "low": [9.0],
            "close": [10.0],
        }
    )
    features.to_parquet(data_dir / "features.parquet", index=False)
    ranker = StockRanker(
        data_dir=str(data_dir),
        artifact_dir=str(tmp_path / "artifacts"),
        config_path=str(tmp_path / "missing.yaml"),
        generate_report=False,
    )

    original_read_parquet = pd.read_parquet
    requested_columns: list[list[str] | None] = []

    def read_parquet(path, *args, **kwargs):
        requested_columns.append(kwargs.get("columns"))
        return original_read_parquet(path, *args, **kwargs)

    with (
        mock.patch(
            "app.agent_b_ranking.load_m4_feature_frame",
            return_value=(features, _metadata()),
        ) as load_feature_frame,
        mock.patch("pandas.read_parquet", side_effect=read_parquet),
    ):
        daily, history = ranker.load_daily_data("2026-08-31")

    assert requested_columns == [["date"], ["date", "stock_id"]]
    assert load_feature_frame.call_args.kwargs["start_date"] == pd.Timestamp("2026-06-02")
    assert daily["stock_id"].tolist() == ["2330"]
    assert history["stock_id"].tolist() == ["2330"]


def test_feature_contract_pushes_ranking_window_into_parquet_reads(tmp_path) -> None:
    data_dir = tmp_path / "clean"
    data_dir.mkdir()
    (data_dir / "features.parquet").touch()
    (data_dir / "events.parquet").touch()
    source = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-31"]),
            "stock_id": ["2330"],
        }
    )
    expected = (source, _metadata())

    with (
        mock.patch("app.modeling.feature_contract.pd.read_parquet", side_effect=[source, source]) as read_parquet,
        mock.patch("app.modeling.feature_contract.build_m4_feature_frame", return_value=expected),
    ):
        actual = feature_contract.load_m4_feature_frame(
            data_dir=data_dir,
            project_root=tmp_path,
            start_date="2026-06-02",
        )

    expected_filter = [("date", ">=", pd.Timestamp("2026-06-02"))]
    assert actual is expected
    assert read_parquet.call_args_list == [
        mock.call(data_dir / "features.parquet", filters=expected_filter),
        mock.call(data_dir / "events.parquet", filters=expected_filter),
    ]
