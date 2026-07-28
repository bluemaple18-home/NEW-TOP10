from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts import run_autonomous_research as research
from scripts.fog_daily_source_lineage import (
    DailySourceLineageError,
    build_daily_source_lineage,
    verify_daily_source_lineage,
)


def write_features(path: Path, dates: list[str], column: str = "date") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({column: pd.to_datetime(dates), "stock_id": ["0001"] * len(dates)}).to_parquet(path)


def test_lineage_uses_latest_feature_date_not_after_market_run_date(tmp_path: Path) -> None:
    features = tmp_path / "data" / "features.parquet"
    write_features(features, ["2026-08-07", "2026-08-08", "2026-08-09"])

    lineage = build_daily_source_lineage(
        root=tmp_path,
        features_path="data/features.parquet",
        market_run_date="2026-08-08",
    )

    assert lineage == {
        "schema_version": "fog-daily-source-lineage.v1",
        "features_path": "data/features.parquet",
        "features_sha256": hashlib.sha256(features.read_bytes()).hexdigest(),
        "daily_source_date": "2026-08-08",
    }
    assert verify_daily_source_lineage(
        root=tmp_path,
        lineage=lineage,
        market_run_date="2026-08-08",
    ) == {"ok": True, "reason_codes": [], "daily_source_date": "2026-08-08"}


@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    [
        ({"features_path": "../escape.parquet"}, "DAILY_SOURCE_PATH_REJECT"),
        ({"features_sha256": "0" * 64}, "DAILY_SOURCE_HASH_MISMATCH"),
        ({"daily_source_date": "2026-08-07"}, "DAILY_SOURCE_DATE_MISMATCH"),
    ],
)
def test_verifier_rejects_lineage_drift(
    tmp_path: Path,
    mutation: dict[str, str],
    reason_code: str,
) -> None:
    features = tmp_path / "data" / "features.parquet"
    write_features(features, ["2026-08-07", "2026-08-08"])
    lineage = build_daily_source_lineage(
        root=tmp_path,
        features_path="data/features.parquet",
        market_run_date="2026-08-08",
    )

    result = verify_daily_source_lineage(
        root=tmp_path,
        lineage={**lineage, **mutation},
        market_run_date="2026-08-08",
    )

    assert result["ok"] is False
    assert reason_code in result["reason_codes"]


@pytest.mark.parametrize(
    ("dates", "column", "reason_code"),
    [
        (["2026-08-09"], "date", "DAILY_SOURCE_DATE_UNAVAILABLE"),
        (["2026-08-08"], "observed_at", "DAILY_SOURCE_DATE_COLUMN_REJECT"),
    ],
)
def test_builder_rejects_unusable_features(
    tmp_path: Path,
    dates: list[str],
    column: str,
    reason_code: str,
) -> None:
    features = tmp_path / "features.parquet"
    write_features(features, dates, column=column)

    with pytest.raises(DailySourceLineageError, match=reason_code):
        build_daily_source_lineage(
            root=tmp_path,
            features_path="features.parquet",
            market_run_date="2026-08-08",
        )


def test_no_executable_daily_payload_keeps_canonical_source_lineage() -> None:
    args = SimpleNamespace(
        execute=True,
        date="2026-08-08",
        features="data/features.parquet",
        baseline_dir="artifacts/backtest/baseline",
        candidate_dir=None,
        topic_index=0,
        execute_topic_count=1,
        from_queue=True,
        rerun=False,
        include_rejected=False,
        max_ranking_files=1,
        horizons="3",
        stop_loss_pcts="none",
        take_profit_pcts="none",
        max_group_exposures="none",
        no_manager_update=True,
        closed_regime_research=True,
        market_regime_history="artifacts/market_regime_history.json",
        research_contract="config/regime_research_contract.json",
        coverage_map=None,
    )
    lineage = {
        "schema_version": "fog-daily-source-lineage.v1",
        "features_path": "data/features.parquet",
        "features_sha256": "a" * 64,
        "daily_source_date": "2026-08-07",
    }

    payload = research.build_payload(
        args,
        topics=[],
        selected_topics_for_run=[],
        topic_runs=[],
        steps=[],
        outcome={"decision": "NO_EXECUTABLE_TOPIC", "promotion_allowed": False},
        outputs={},
        source_lineage=lineage,
    )

    assert payload["topic_runs"] == []
    assert payload["source_lineage"] == lineage
