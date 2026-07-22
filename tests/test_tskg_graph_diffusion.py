"""TSKG-MFO-GRAPH-01 shadow graph diffusion contract tests。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.tskg.graph_diffusion import (
    GraphDiffusionContractError,
    GraphDiffusionSnapshot,
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
