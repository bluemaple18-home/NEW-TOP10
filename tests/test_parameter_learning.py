from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from app.research.contracts import canonical_json_bytes, content_hash
from app.research.observation_ingest import ingest_corpus
from app.research.parameter_learning import (
    analyze_interaction,
    analyze_numeric_landscape,
    build_projection,
    classify_matched_contrasts,
    load_policy,
)
from app.research.receipt_store import ImmutableCollisionError


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


def test_learning_projection_clean_rebuild_preserves_canonical_bytes(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    output_root = tmp_path / "learning"

    first = build_projection(
        ledger_path=ledger,
        eligibility_output_root=tmp_path / "eligibility",
        output_root=output_root,
    )
    target = output_root / f"{first['projection_id'][7:]}.json"
    first_bytes = target.read_bytes()
    target.unlink()

    second = build_projection(
        ledger_path=ledger,
        eligibility_output_root=tmp_path / "eligibility",
        output_root=output_root,
    )

    assert first == second
    assert target.read_bytes() == first_bytes


def test_existing_learning_artifact_cannot_replace_fresh_projection_truth(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    output_root = tmp_path / "learning"
    result = build_projection(
        ledger_path=ledger,
        eligibility_output_root=tmp_path / "eligibility",
        output_root=output_root,
    )
    target = output_root / f"{result['projection_id'][7:]}.json"
    tampered = {**result, "counts": {**result["counts"], "eligible_observations": 99}}
    target.write_bytes(canonical_json_bytes(tampered) + b"\n")

    with pytest.raises(ImmutableCollisionError, match="immutable target collision"):
        build_projection(
            ledger_path=ledger,
            eligibility_output_root=tmp_path / "eligibility",
            output_root=output_root,
        )


def test_matched_direction_ignores_cross_stratum_level_confounding() -> None:
    policy = load_policy()
    contrasts = [
        {"delta_score": 0.0, "lineage_id": "lineage-a"},
        {"delta_score": 0.0, "lineage_id": "lineage-b"},
        {"delta_score": 0.0, "lineage_id": "lineage-c"},
    ]
    # Raw levels可呈0→100→200；exact within-stratum deltas仍全flat。
    assert classify_matched_contrasts(contrasts, policy)["direction"] == "FLAT"


def test_single_lineage_contrasts_are_not_independent_direction_support() -> None:
    policy = load_policy()
    contrasts = [
        {"delta_score": 0.1, "lineage_id": "lineage-a"},
        {"delta_score": 0.1, "lineage_id": "lineage-a"},
        {"delta_score": 0.1, "lineage_id": "lineage-a"},
    ]

    assert classify_matched_contrasts(contrasts, policy)["direction"] == "INSUFFICIENT_EVIDENCE"


def test_boundary_requires_highest_catalog_edge_support() -> None:
    policy = load_policy()
    low_only = [
        {"delta_score": 0.1, "lower": 0.05, "upper": 0.08, "lineage_id": "lineage-a"},
        {"delta_score": 0.1, "lower": 0.05, "upper": 0.08, "lineage_id": "lineage-b"},
        {"delta_score": 0.1, "lower": 0.05, "upper": 0.08, "lineage_id": "lineage-c"},
    ]
    result = classify_matched_contrasts(low_only, policy, parameter="stop_loss_pct")
    assert result["direction"] == "HIGHER_LOOKS_BETTER"
    assert result["edge_behavior"] is None
    assert result["next_direction"] is None


@pytest.mark.parametrize("lineage", [None, "", "   "])
def test_missing_or_blank_lineage_is_insufficient_evidence(lineage: object) -> None:
    policy = load_policy()
    contrasts = [
        {"delta_score": 0.1, "lineage_id": lineage},
        {"delta_score": 0.1, "lineage_id": "lineage-b"},
        {"delta_score": 0.1, "lineage_id": "lineage-c"},
    ]
    assert classify_matched_contrasts(contrasts, policy)["direction"] == "INSUFFICIENT_EVIDENCE"


def _insert_learning_observation(
    connection: duckdb.DuckDBPyConnection,
    *,
    index: int,
    lineage_id: str,
    stop_loss_pct: float,
    score: float,
    execution_profile: dict[str, object],
) -> None:
    parameters = {
        "horizon": 5,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": 0.15,
        "max_group_exposure": 0.35,
    }
    trial_spec_id = content_hash({"trial": index, "parameters": parameters, "profile": execution_profile})
    receipt_id = content_hash({"receipt": index})
    execution_unit_id = content_hash({"unit": index})
    observation_id = content_hash({"observation": index})
    evidence_unit_id = content_hash({"evidence": index})
    connection.execute(
        "INSERT INTO trial_specs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            trial_spec_id,
            "topic-a",
            "family-a",
            "DEVELOPMENT_SCREEN",
            json.dumps({"regime_id": "RISK_OFF|"}),
            "sha256:" + "1" * 64,
            "sha256:" + "2" * 64,
            json.dumps(parameters),
            json.dumps(execution_profile),
            "sha256:" + "3" * 64,
            content_hash({"trial_spec": index}),
        ],
    )
    connection.execute(
        "INSERT INTO run_receipts VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            receipt_id,
            f"run-{index}",
            f"intent-{index}",
            "SUCCEEDED",
            "OBSERVED",
            "EXACT",
            "2026-08-31T00:00:00+00:00",
            "2026-08-31T00:01:00+00:00",
            content_hash({"receipt_payload": index}),
            f"receipts/run-{index}.json",
        ],
    )
    connection.execute(
        "INSERT INTO execution_units VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            execution_unit_id,
            receipt_id,
            trial_spec_id,
            trial_spec_id,
            lineage_id,
            "PROVEN_NON_SEALED",
            "VALID",
            json.dumps(["episode-dev"]),
            json.dumps([]),
            content_hash({"unit_payload": index}),
        ],
    )
    connection.execute(
        "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            observation_id,
            execution_unit_id,
            receipt_id,
            trial_spec_id,
            lineage_id,
            f"result-{index}",
            evidence_unit_id,
            f"scenario-{index}",
            0.05 + score,
            -0.1,
            0.55,
            0.01,
            12,
            score,
            0.04,
            2,
            content_hash({"result": index, "score": score}),
            "executed-trial-lineage-result-unit.v1",
            "strategy-matrix-metrics.v1",
            "terminal-receipts-all-statuses.v1",
        ],
    )


def test_execution_profile_mismatch_prevents_matched_contrast(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    connection = duckdb.connect(str(ledger))
    try:
        _insert_learning_observation(
            connection,
            index=1,
            lineage_id="lineage-a",
            stop_loss_pct=0.08,
            score=0.1,
            execution_profile={"variant_role": "candidate", "engine": "v1"},
        )
        _insert_learning_observation(
            connection,
            index=2,
            lineage_id="lineage-a",
            stop_loss_pct=0.10,
            score=0.2,
            execution_profile={"variant_role": "candidate", "engine": "v2"},
        )
    finally:
        connection.close()

    result = build_projection(
        ledger_path=ledger,
        eligibility_output_root=tmp_path / "eligibility",
        output_root=tmp_path / "learning",
    )

    assert result["counts"]["eligible_observations"] == 2
    assert result["counts"]["matched_contrasts"] == 0
