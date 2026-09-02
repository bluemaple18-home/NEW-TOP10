from __future__ import annotations

import json
import sys

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

    assert research.is_baseline_like(fixture.CANDIDATE_DIR) is False
    assert eligibility["eligible"] is True
    assert allowed_dates == {"2025-08-07"}


def test_pinned_fixture_fresh_manager_selects_representative_topic(
    tmp_path, monkeypatch
) -> None:
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
    fixture_history = tmp_path / "market_regime_history.json"
    fixture_history.write_text(json.dumps(merged), encoding="utf-8")
    manager_root = tmp_path / "manager"
    monkeypatch.setattr(research, "OUTPUT_DIR", manager_root)
    monkeypatch.setattr(research, "RESEARCH_LEDGER_PATH", tmp_path / "ledger.duckdb")
    monkeypatch.setattr(research, "RESEARCH_SPINE_ROOT", tmp_path / "research_spine")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_autonomous_research.py",
            "--date",
            fixture.FIXTURE_DATE,
            "--execute",
            "--closed-regime-research",
            "--market-regime-history",
            str(fixture_history),
            "--research-contract",
            "config/regime_research_contract.json",
            "--candidate-dir",
            fixture.CANDIDATE_DIR,
            "--baseline-dir",
            fixture.BASELINE_DIR,
            "--development-screen-on-sealed-exhaustion",
            "--development-screen-topic-count",
            "1",
        ],
    )
    args = research.parse_args()
    generated = research.generate_all_topics(args)
    all_topics = research.apply_closed_experiment_capacity(generated, args)
    selected = research.select_topics_for_run(
        all_topics,
        args,
        fallback_topics=[topic for topic in all_topics if topic.eligible],
    )
    supply = None
    if not selected:
        supplied, supply = research.replenish_development_topics(
            generated,
            args,
            same_round_ids=set(),
        )
        selected = research.select_topics_for_run(
            [*supplied, *all_topics],
            args,
            fallback_topics=[*supplied, *[topic for topic in all_topics if topic.eligible]],
        )

    diagnostics = {
        "generated": [
            {
                "topic_id": topic.topic_id,
                "eligible": topic.eligible,
                "reason_code": topic.reason_code,
                "horizons": topic.horizons,
                "regime_identity": topic.regime_identity,
            }
            for topic in generated
        ],
        "supply": supply,
    }
    assert selected, json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
    assert selected[0].eligible is True
