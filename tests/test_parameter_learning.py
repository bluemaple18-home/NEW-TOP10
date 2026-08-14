from __future__ import annotations

from pathlib import Path

from app.research.observation_ingest import ingest_corpus
from app.research.parameter_learning import (
    analyze_interaction,
    analyze_numeric_landscape,
    build_projection,
    classify_matched_contrasts,
    load_policy,
)


def points(values, scores, *, returns=None, drawdowns=None):
    returns = returns or [0.05] * len(values)
    drawdowns = drawdowns or [-0.1] * len(values)
    return [
        {"value": value, "score": score, "total_return": ret, "max_drawdown": dd}
        for value, score, ret, dd in zip(values, scores, returns, drawdowns)
    ]


def test_higher_lower_and_boundary_direction() -> None:
    higher = analyze_numeric_landscape(
        points([0.05, 0.08, 0.12], [-0.10, 0.0, 0.08]), parameter="stop_loss_pct"
    )
    assert higher["direction"] == "HIGHER_LOOKS_BETTER"
    assert higher["edge_behavior"] == "BEST_AT_UPPER_BOUNDARY"
    assert higher["next_direction"] == "EXPAND_UPWARD"
    lower = analyze_numeric_landscape(
        points([0.10, 0.15, 0.25], [0.08, 0.04, -0.05]), parameter="take_profit_pct"
    )
    assert lower["direction"] == "LOWER_LOOKS_BETTER"


def test_interior_peak_flat_and_sharp_peak() -> None:
    peak = analyze_numeric_landscape(
        points([0.10, 0.15, 0.20, 0.25], [0.01, 0.05, 0.04, 0.0]),
        parameter="take_profit_pct",
    )
    assert peak["direction"] == "INTERIOR_PEAK"
    sharp = analyze_numeric_landscape(
        points([0.10, 0.15, 0.20], [0.0, 0.10, 0.0]), parameter="take_profit_pct"
    )
    assert {"SHARP_PEAK", "OVERFIT_RISK"}.issubset(sharp["flags"])
    assert sharp["robust_basins"] == []
    flat = analyze_numeric_landscape(
        points([0.25, 0.35, 0.45, 0.55], [0.101, 0.102, 0.100, 0.101]),
        parameter="max_group_exposure",
    )
    assert flat["direction"] == "FLAT"
    assert "LOW_SENSITIVITY" in flat["flags"]


def test_robust_basin_requires_catalog_adjacency() -> None:
    basin = analyze_numeric_landscape(
        points([0.08, 0.10, 0.12], [0.081, 0.083, 0.080]), parameter="stop_loss_pct"
    )
    assert basin["robust_basins"] == [[0.08, 0.12]]
    non_adjacent = analyze_numeric_landscape(
        points([0.05, 0.08, 0.12], [0.081, 0.083, 0.080]), parameter="stop_loss_pct"
    )
    assert non_adjacent["robust_basins"] == []


def test_interaction_requires_complete_two_by_two() -> None:
    cells = [
        {"horizon": 3, "stop_loss_pct": 0.08, "score": 0.0},
        {"horizon": 5, "stop_loss_pct": 0.08, "score": 0.1},
        {"horizon": 3, "stop_loss_pct": 0.12, "score": 0.0},
        {"horizon": 5, "stop_loss_pct": 0.12, "score": 0.4},
    ]
    result = analyze_interaction(cells, "horizon", "stop_loss_pct")
    assert result["classification"] == "CONDITIONAL_EFFECT"
    assert analyze_interaction(cells[:-1], "horizon", "stop_loss_pct")["classification"] == "INSUFFICIENT_EVIDENCE"


def test_return_up_drawdown_worse_is_visible_in_contrast_direction() -> None:
    result = analyze_numeric_landscape(
        points([0.08, 0.12], [0.0, 0.05], returns=[0.01, 0.05], drawdowns=[-0.1, -0.3]),
        parameter="stop_loss_pct",
    )
    assert result["edges"][0]["delta_score"] > 0
    assert "RISK_RETURN_TRADEOFF" in result["flags"]


def test_zero_eligible_cold_start_is_formal_result(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    result = build_projection(
        ledger_path=ledger,
        eligibility_output_root=tmp_path / "eligibility",
        output_root=tmp_path / "learning",
    )
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["counts"]["eligible_observations"] == 0
    assert result["matched_contrasts"] == []
    assert result["interaction_findings"] == []


def test_matched_direction_ignores_cross_stratum_level_confounding() -> None:
    policy = load_policy()
    contrasts = [
        {"delta_score": 0.0},
        {"delta_score": 0.0},
        {"delta_score": 0.0},
    ]
    # Raw levels可呈0→100→200；exact within-stratum deltas仍全flat。
    assert classify_matched_contrasts(contrasts, policy)["direction"] == "FLAT"


def test_boundary_requires_highest_catalog_edge_support() -> None:
    policy = load_policy()
    low_only = [
        {"delta_score": 0.1, "lower": 0.05, "upper": 0.08},
        {"delta_score": 0.1, "lower": 0.05, "upper": 0.08},
        {"delta_score": 0.1, "lower": 0.05, "upper": 0.08},
    ]
    result = classify_matched_contrasts(low_only, policy, parameter="stop_loss_pct")
    assert result["direction"] == "HIGHER_LOOKS_BETTER"
    assert result["edge_behavior"] is None
    assert result["next_direction"] is None
