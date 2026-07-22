"""TSKG-MFO-GRAPH-01 shadow graph diffusion contract tests。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.tskg.graph_diffusion import (
    GraphDiffusionContractError,
    GraphDiffusionSnapshot,
    MAX_PATH_STATES,
    build_graph_diffusion_shadow,
)


ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict:
    return json.loads((ROOT / "data/fixtures/tskg/graph_diffusion_v1.json").read_text())


def _snapshot() -> GraphDiffusionSnapshot:
    return GraphDiffusionSnapshot(_payload())


def test_determinism_order_independence_and_baseline_comparison() -> None:
    payload = _payload()
    first = build_graph_diffusion_shadow(_snapshot(), ["security-a"], max_hops=2)
    payload["nodes"].reverse()
    payload["edges"].reverse()
    reordered = build_graph_diffusion_shadow(GraphDiffusionSnapshot(payload), ["security-a"], max_hops=2)
    assert first == reordered
    assert first["baseline_no_diffusion"]["security-a"] == 1.0
    assert first["baseline_no_diffusion"]["security-b"] == 0.0
    assert first["shadow_values"]["security-b"] > 0


def test_cycle_is_bounded_and_mass_is_conserved() -> None:
    result = build_graph_diffusion_shadow(_snapshot(), ["security-a"], max_hops=8)
    assert all(row["hop"] <= 8 for row in result["values"])
    assert all(row["output_mass"] == pytest.approx(1.0) for row in result["mass_conservation"])
    assert all(row["within_tolerance"] for row in result["mass_conservation"])
    assert result["production_impact"] == "NONE_SHADOW_ONLY"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("target_id", "security-missing", "missing edge endpoint"),
        ("valid_to", "2026-07-16", "stale edge"),
        ("valid_from", "2026-07-18", "future"),
    ],
)
def test_missing_stale_and_future_edges_are_rejected(field: str, value: str, message: str) -> None:
    payload = _payload()
    payload["edges"][0][field] = value
    with pytest.raises(GraphDiffusionContractError, match=message):
        GraphDiffusionSnapshot(payload)


def test_provenance_trace_contains_observation_path_weight_version_hop_decay_and_coverage() -> None:
    result = build_graph_diffusion_shadow(_snapshot(), ["security-a"], max_hops=2)
    propagated = next(row for row in result["values"] if row["node_id"] == "security-b")
    assert propagated["source_observation_id"] == "obs-a"
    assert propagated["evidence_id"] == "evidence-a"
    assert propagated["hop"] == 1
    assert propagated["decay"] == 0.75
    trace = propagated["edge_path"][0]
    assert trace["weight_version"] == "fixture-weight-v1"
    assert trace["source_observation_id"] == "edge-obs-a-b"
    assert trace["evidence_id"] == "edge-evidence-a-b"
    assert trace["coverage"] == {"status": "AVAILABLE", "venue": "TWSE"}


def test_invalid_parameters_fail_closed() -> None:
    for kwargs in ({"max_hops": -1}, {"max_hops": 9}, {"decay": 0}, {"decay": 1.1}):
        with pytest.raises(GraphDiffusionContractError):
            build_graph_diffusion_shadow(_snapshot(), ["security-a"], **kwargs)
    with pytest.raises(GraphDiffusionContractError, match="known"):
        build_graph_diffusion_shadow(_snapshot(), ["security-missing"])


def test_future_node_and_missing_edge_provenance_are_rejected() -> None:
    future = _payload()
    future["nodes"][0]["observed_at"] = "2026-07-18"
    with pytest.raises(GraphDiffusionContractError, match="future node"):
        GraphDiffusionSnapshot(future)
    missing = deepcopy(_payload())
    missing["edges"][0]["evidence_id"] = ""
    with pytest.raises(GraphDiffusionContractError, match="evidence"):
        GraphDiffusionSnapshot(missing)


@pytest.mark.parametrize("weight", [float("nan"), float("inf"), float("-inf"), 1e308])
def test_non_finite_and_overflow_prone_weights_fail_closed(weight: float) -> None:
    payload = _payload()
    payload["edges"][0]["weight"] = weight
    with pytest.raises(GraphDiffusionContractError):
        GraphDiffusionSnapshot(payload)


def test_diffusion_artifact_values_are_finite_and_mass_is_conserved() -> None:
    result = build_graph_diffusion_shadow(_snapshot(), ["security-a"], max_hops=8)
    serialized = json.dumps(result, allow_nan=False)
    assert serialized
    assert all(row["output_mass"] == pytest.approx(1.0) for row in result["mass_conservation"])
    assert sum(result["shadow_values"].values()) == pytest.approx(1.0)
    assert all(row["value"] >= 0 and row["value"] == pytest.approx(row["value"]) for row in result["values"])


def _layered_payload(branching: int, depth: int) -> dict:
    """建立可精確控制最終 path-state 數量的分層 DAG。"""
    layers = [["root"]]
    for layer in range(1, depth + 1):
        layers.append([f"n{layer}-{index}" for index in range(branching)])
    nodes = []
    for layer in layers:
        for node_id in layer:
            nodes.append({
                "node_id": node_id,
                "node_type": "SECURITY",
                "source_observation_id": f"obs-{node_id}",
                "evidence_id": f"evidence-{node_id}",
                "observed_at": "2026-07-17",
                "coverage": {"venue": "TWSE", "status": "AVAILABLE"},
            })
    edges = []
    edge_number = 0
    for source_layer, target_layer in zip(layers, layers[1:]):
        for source_id in source_layer:
            for target_id in target_layer:
                edges.append({
                    "edge_id": f"edge-{edge_number}",
                    "source_id": source_id,
                    "target_id": target_id,
                    "weight": 1.0,
                    "weight_version": "v1",
                    "valid_from": "2026-07-17",
                    "valid_to": "2026-07-17",
                    "source_observation_id": f"edge-obs-{edge_number}",
                    "evidence_id": f"edge-evidence-{edge_number}",
                    "coverage": {"venue": "TWSE", "status": "AVAILABLE"},
                })
                edge_number += 1
    return {
        "fixture_version": "graph-diffusion-v1",
        "schema_version": "tskg-graph-diffusion-shadow-v1",
        "algorithm_version": "bounded-mass-conserving-v1",
        "as_of_date": "2026-07-17",
        "source": "synthetic",
        "version": "v1",
        "evidence_locator": "fixture",
        "nodes": nodes,
        "edges": edges,
    }


def test_path_state_budget_succeeds_at_limit() -> None:
    snapshot = GraphDiffusionSnapshot(_layered_payload(branching=4, depth=5))
    result = build_graph_diffusion_shadow(snapshot, ["root"], max_hops=5, decay=1.0)
    assert len(result["values"]) == MAX_PATH_STATES


def test_path_state_budget_rejects_over_limit_deterministically() -> None:
    snapshot = GraphDiffusionSnapshot(_layered_payload(branching=4, depth=6))
    messages = []
    for _ in range(2):
        with pytest.raises(GraphDiffusionContractError, match="path-state budget exceeded") as raised:
            build_graph_diffusion_shadow(snapshot, ["root"], max_hops=6, decay=1.0)
        messages.append(str(raised.value))
    assert messages[0] == messages[1]
