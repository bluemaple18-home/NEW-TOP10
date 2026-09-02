from __future__ import annotations

import pandas as pd

from scripts import run_autonomous_research as research
from scripts import run_fog_representative_validation as fixture
from scripts.update_fog_regime_authority import merge_append_only, read_json


def test_pinned_historical_fixture_is_exact_regime_and_executable() -> None:
    root = fixture.PROJECT_ROOT
    expected_dates = sorted(
        pd.to_datetime(
            pd.read_parquet(root / "data/clean/features.parquet", columns=["date"])[
                "date"
            ]
        )
        .dt.strftime("%Y-%m-%d")
        .unique()
        .tolist()
    )
    merged, _receipt = merge_append_only(
        read_json(root / "artifacts/market_regime_history.json"),
        read_json(
            root
            / "artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json"
        ),
        expected_dates,
    )
    row = next(
        item for item in merged["rows"] if item["trade_date"] == fixture.FIXTURE_DATE
    )
    assert {
        "base_regime": row["base_regime"],
        "family_tags": sorted(row["family_tags"]),
    } == fixture.FIXTURE_IDENTITY
    allowed_dates = research.canonical_exact_regime_allowed_dates(
        rows=merged["rows"],
        contract=read_json(root / "config/regime_research_contract.json"),
        regime_identity=fixture.FIXTURE_IDENTITY,
        horizons="3",
        as_of_date=fixture.FIXTURE_DATE,
    )
    eligibility = research.exact_regime_topic_ranking_eligibility(
        candidate_dir=fixture.CANDIDATE_DIR,
        baseline_dir=fixture.BASELINE_DIR,
        allowed_dates=allowed_dates,
        as_of_date=fixture.FIXTURE_DATE,
    )

    assert eligibility["eligible"] is True
    assert allowed_dates == {"2025-08-07"}
