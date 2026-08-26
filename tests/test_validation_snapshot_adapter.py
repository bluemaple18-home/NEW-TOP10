from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.pipeline.validation import PipelineDataValidator


def _representative_quotes() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-02", periods=80)
    rows: list[dict[str, object]] = []
    for index, stock_id in enumerate(("1101", "1216", "1301", "2330", "3008", "6488")):
        market = "TWSE" if index < 3 else "TPEX"
        for offset, date in enumerate(dates):
            close = 50 + index * 10 + offset * 0.2
            rows.append(
                {
                    "date": date,
                    "stock_id": stock_id,
                    "stock_name": f"真實行情樣本{stock_id}",
                    "market": market,
                    "open": close - 0.5,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1_000_000 + offset,
                    "value": close * (1_000_000 + offset),
                }
            )
    return pd.DataFrame(rows)


def test_validation_snapshot_replaces_provider_only_and_runs_canonical_downstream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.pipeline import ETLPipeline, EventStage, FetchStage, FilterStage, FundamentalStage, IndicatorStage
    from app.pipeline import fetch_stage

    snapshot = tmp_path / "real_quotes.csv"
    _representative_quotes().to_csv(snapshot, index=False)
    output_data = tmp_path / "output" / "data"
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SNAPSHOT_INPUT", str(snapshot))

    class ProviderMustNotRun:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("validation snapshot path must not construct network provider")

    monkeypatch.setattr(fetch_stage, "DataFetcherOrchestrator", ProviderMustNotRun)
    pipeline = (
        ETLPipeline(data_dir=str(output_data), artifacts_dir=str(tmp_path / "output" / "artifacts"))
        .add_stage(FetchStage())
        .add_stage(IndicatorStage())
        .add_stage(FundamentalStage())
        .add_stage(EventStage())
        .add_stage(FilterStage())
    )

    pipeline.run(start_date="2026-01-02", end_date="2026-04-23")

    metadata = pipeline.context["stats"]["validation_snapshot"]
    assert metadata["provider_acquisition"] == "snapshot"
    assert metadata["coverage"]["stock_count"] == 6
    assert metadata["coverage"]["markets"] == ["TPEX", "TWSE"]
    assert (output_data / "clean" / "features.parquet").is_file()
    assert PipelineDataValidator(data_dir=output_data).validate_outputs().ok


def test_validation_snapshot_rejects_empty_input_before_provider_can_run(tmp_path: Path) -> None:
    from app.pipeline.validation_snapshot import ValidationSnapshotError, load_validation_snapshot

    snapshot = tmp_path / "empty.csv"
    pd.DataFrame(columns=["date", "stock_id", "stock_name", "market", "open", "high", "low", "close", "volume", "value"]).to_csv(snapshot, index=False)

    with pytest.raises(ValidationSnapshotError, match="不可為空"):
        load_validation_snapshot(snapshot)


def test_validation_snapshot_rejects_partial_canonical_window(tmp_path: Path) -> None:
    from app.pipeline.validation_snapshot import (
        ValidationSnapshotError,
        load_validation_snapshot,
        require_snapshot_window,
    )

    snapshot = tmp_path / "partial.csv"
    _representative_quotes().to_csv(snapshot, index=False)

    with pytest.raises(ValidationSnapshotError, match="未完整覆蓋 canonical ETL window"):
        require_snapshot_window(
            load_validation_snapshot(snapshot),
            start_date="2025-01-02",
            end_date="2026-04-23",
        )


def test_validation_seatbelt_profile_keeps_network_denied() -> None:
    from app.storage_safety import _sandbox_profile

    profile = _sandbox_profile(Path("/private/tmp/top10-validation-sandbox"))
    assert "(deny default)" in profile
    assert "(allow network" not in profile
