"""TSKG evidence-backed graph diffusion 的 research-only 合約。

本模組只處理離線 snapshot，輸出不含分數、排名或 prediction，亦不被
production ranking path import。所有 edge 都必須在 ``as_of_date`` 有效，
並可回溯到 source observation 與 evidence。
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import date
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "tskg-graph-diffusion-shadow-v1"
ALGORITHM_VERSION = "bounded-mass-conserving-v1"
_TOP_LEVEL = {
    "fixture_version", "schema_version", "algorithm_version", "as_of_date",
    "source", "version", "evidence_locator", "nodes", "edges",
}
_NODE_FIELDS = {
    "node_id", "node_type", "source_observation_id", "evidence_id",
    "observed_at", "coverage",
}
_EDGE_FIELDS = {
    "edge_id", "source_id", "target_id", "weight", "weight_version",
    "valid_from", "valid_to", "source_observation_id", "evidence_id",
    "coverage",
}
_COVERAGE_FIELDS = {"venue", "status"}
_PROHIBITED = {
    "rank", "score", "prediction", "recommendation", "risk_adjusted_score",
    "buy_signal", "sell_signal", "target_price", "expected_return", "weighting",
}

# 這些是 research-only shadow contract 的固定 deterministic work budgets。
MAX_NODES = 256
MAX_EDGES = 2048
MAX_OUT_DEGREE = 32
MAX_PATH_STATES = 1024
MAX_EDGE_WEIGHT = 1e300


class GraphDiffusionContractError(ValueError):
    """Graph snapshot 或 diffusion 參數違反 shadow contract。"""


def _as_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise GraphDiffusionContractError(f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise GraphDiffusionContractError(f"{field} must be YYYY-MM-DD") from error


def _coverage(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _COVERAGE_FIELDS:
        raise GraphDiffusionContractError(f"{field} must contain venue/status")
    if value["status"] != "AVAILABLE" or not all(
        isinstance(value[key], str) and value[key] for key in _COVERAGE_FIELDS
    ):
        raise GraphDiffusionContractError(f"{field} is not available evidence")
    return {key: str(value[key]) for key in sorted(_COVERAGE_FIELDS)}


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _finite_float(value: Any, field: str, *, maximum: float | None = None) -> float:
    """將數值轉成 finite float，避免 NaN、Infinity 與轉換溢位穿過契約。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GraphDiffusionContractError(f"{field} must be numeric and finite")
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise GraphDiffusionContractError(f"{field} must be numeric and finite") from error
    if not math.isfinite(converted) or (maximum is not None and converted > maximum):
        raise GraphDiffusionContractError(f"{field} must be finite and within contract bounds")
    return converted


def _assert_finite(value: Any, field: str = "artifact") -> None:
    """遞迴確認 hash 前的 artifact 不含任何非 finite 浮點數。"""
    if isinstance(value, float) and not math.isfinite(value):
        raise GraphDiffusionContractError(f"{field} contains a non-finite value")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_finite(child, f"{field}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite(child, f"{field}[{index}]")


def _contains_prohibited(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(key in _PROHIBITED or _contains_prohibited(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_prohibited(child) for child in value)
    return False


class GraphDiffusionSnapshot:
    """驗證並 canonicalize 一份 as-of graph snapshot。"""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        if not isinstance(payload, Mapping) or set(payload) != _TOP_LEVEL:
            raise GraphDiffusionContractError("snapshot has an unexpected or missing field")
        data = deepcopy(dict(payload))
        if _contains_prohibited(data):
            raise GraphDiffusionContractError("strategy fields are prohibited")
        if data["fixture_version"] != "graph-diffusion-v1" or data["schema_version"] != SCHEMA_VERSION:
            raise GraphDiffusionContractError("snapshot version mismatch")
        if data["algorithm_version"] != ALGORITHM_VERSION:
            raise GraphDiffusionContractError("algorithm_version mismatch")
        as_of = _as_date(data["as_of_date"], "as_of_date")
        for field in ("source", "version", "evidence_locator"):
            if not isinstance(data[field], str) or not data[field].strip():
                raise GraphDiffusionContractError(f"{field} must be non-empty")
        if not isinstance(data["nodes"], list) or not isinstance(data["edges"], list):
            raise GraphDiffusionContractError("nodes and edges must be lists")
        if len(data["nodes"]) > MAX_NODES:
            raise GraphDiffusionContractError(f"node budget exceeded: maximum is {MAX_NODES}")
        if len(data["edges"]) > MAX_EDGES:
            raise GraphDiffusionContractError(f"edge budget exceeded: maximum is {MAX_EDGES}")
        nodes: dict[str, dict[str, Any]] = {}
        for node in data["nodes"]:
            if not isinstance(node, Mapping) or set(node) != _NODE_FIELDS:
                raise GraphDiffusionContractError("invalid node shape")
            node_id = node["node_id"]
            if not isinstance(node_id, str) or not node_id or node_id in nodes:
                raise GraphDiffusionContractError("node_id must be unique and non-empty")
            if not isinstance(node["node_type"], str) or not node["node_type"]:
                raise GraphDiffusionContractError("node_type must be non-empty")
            if not isinstance(node["source_observation_id"], str) or not node["source_observation_id"]:
                raise GraphDiffusionContractError("node source observation is required")
            if not isinstance(node["evidence_id"], str) or not node["evidence_id"]:
                raise GraphDiffusionContractError("node evidence is required")
            if _as_date(node["observed_at"], "node.observed_at") > as_of:
                raise GraphDiffusionContractError("future node observation is rejected")
            _coverage(node["coverage"], "node.coverage")
            nodes[node_id] = dict(node)

        edges: list[dict[str, Any]] = []
        edge_ids: set[str] = set()
        for edge in data["edges"]:
            if not isinstance(edge, Mapping) or set(edge) != _EDGE_FIELDS:
                raise GraphDiffusionContractError("invalid edge shape")
            edge_id = edge["edge_id"]
            if not isinstance(edge_id, str) or not edge_id or edge_id in edge_ids:
                raise GraphDiffusionContractError("edge_id must be unique and non-empty")
            edge_ids.add(edge_id)
            if edge["source_id"] not in nodes or edge["target_id"] not in nodes:
                raise GraphDiffusionContractError("missing edge endpoint is rejected")
            weight = _finite_float(edge["weight"], "edge weight", maximum=MAX_EDGE_WEIGHT)
            if weight <= 0:
                raise GraphDiffusionContractError("edge weight must be positive")
            if not isinstance(edge["weight_version"], str) or not edge["weight_version"]:
                raise GraphDiffusionContractError("edge weight version is required")
            start, end = _as_date(edge["valid_from"], "edge.valid_from"), _as_date(edge["valid_to"], "edge.valid_to")
            if start > end:
                raise GraphDiffusionContractError("edge validity interval is inverted")
            if start > as_of or end < as_of:
                raise GraphDiffusionContractError("future/stale edge is rejected")
            for field in ("source_observation_id", "evidence_id"):
                if not isinstance(edge[field], str) or not edge[field]:
                    raise GraphDiffusionContractError(f"edge {field} is required")
            _coverage(edge["coverage"], "edge.coverage")
            edges.append(dict(edge))
        data["nodes"] = sorted(nodes.values(), key=lambda row: row["node_id"])
        data["edges"] = sorted(edges, key=lambda row: (row["source_id"], row["target_id"], row["edge_id"]))
        out_degree: dict[str, int] = {}
        for edge in data["edges"]:
            source_id = edge["source_id"]
            out_degree[source_id] = out_degree.get(source_id, 0) + 1
            if out_degree[source_id] > MAX_OUT_DEGREE:
                raise GraphDiffusionContractError(
                    f"out-degree budget exceeded for {source_id}: maximum is {MAX_OUT_DEGREE}"
                )
        self._payload = data

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._payload)

    @property
    def as_of_date(self) -> str:
        return self._payload["as_of_date"]


def build_graph_diffusion_shadow(
    snapshot: GraphDiffusionSnapshot,
    seeds: Iterable[str],
    *,
    max_hops: int = 2,
    decay: float = 0.75,
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    """以固定 seed/order 做 bounded diffusion，並保留每條 provenance path。"""
    if not isinstance(snapshot, GraphDiffusionSnapshot):
        raise TypeError("snapshot must be a GraphDiffusionSnapshot")
    if isinstance(max_hops, bool) or not isinstance(max_hops, int) or not 0 <= max_hops <= 8:
        raise GraphDiffusionContractError("max_hops must be an integer in [0, 8]")
    decay = _finite_float(decay, "decay")
    if not 0 < decay <= 1:
        raise GraphDiffusionContractError("decay must be in (0, 1]")
    tolerance = _finite_float(tolerance, "tolerance")
    if tolerance <= 0:
        raise GraphDiffusionContractError("tolerance must be positive")
    data = snapshot.as_dict()
    nodes = {row["node_id"]: row for row in data["nodes"]}
    seed_ids = sorted(set(seeds))
    if not seed_ids or any(seed not in nodes for seed in seed_ids):
        raise GraphDiffusionContractError("seeds must be known, non-empty node IDs")
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in data["edges"]:
        outgoing.setdefault(edge["source_id"], []).append(edge)
    for values in outgoing.values():
        values.sort(key=lambda row: (row["target_id"], row["edge_id"]))

    baseline = {node_id: (1.0 if node_id in seed_ids else 0.0) for node_id in sorted(nodes)}
    values: list[dict[str, Any]] = []
    conservation: list[dict[str, Any]] = []
    for seed in seed_ids:
        # state: node, mass, path, visited；visited 使 cycle 不會無限增長。
        states: list[tuple[str, float, tuple[dict[str, Any], ...], frozenset[str]]] = [
            (seed, 1.0, tuple(), frozenset({seed}))
        ]
        for hop in range(1, max_hops + 1):
            next_states: list[tuple[str, float, tuple[dict[str, Any], ...], frozenset[str]]] = []
            for node_id, mass, path, visited in states:
                if not math.isfinite(mass):
                    raise GraphDiffusionContractError("diffused mass must be finite")
                edges = [edge for edge in outgoing.get(node_id, []) if edge["target_id"] not in visited]
                if not edges or mass <= tolerance:
                    next_states.append((node_id, mass, path, visited))
                    if len(next_states) > MAX_PATH_STATES:
                        raise GraphDiffusionContractError(
                            f"path-state budget exceeded: maximum is {MAX_PATH_STATES}"
                        )
                    continue
                try:
                    total_weight = math.fsum(float(edge["weight"]) for edge in edges)
                except (OverflowError, ValueError) as error:
                    raise GraphDiffusionContractError("edge weight total must be finite") from error
                if not math.isfinite(total_weight) or total_weight <= 0:
                    raise GraphDiffusionContractError("edge weight total must be finite and positive")
                propagated = mass * float(decay)
                retained = mass - propagated
                if not math.isfinite(propagated) or not math.isfinite(retained):
                    raise GraphDiffusionContractError("diffused mass must be finite")
                if retained > tolerance:
                    next_states.append((node_id, retained, path, visited))
                    if len(next_states) > MAX_PATH_STATES:
                        raise GraphDiffusionContractError(
                            f"path-state budget exceeded: maximum is {MAX_PATH_STATES}"
                        )
                for edge in edges:
                    share = propagated * float(edge["weight"]) / total_weight
                    if not math.isfinite(share):
                        raise GraphDiffusionContractError("diffused share must be finite")
                    edge_trace = {
                        "edge_id": edge["edge_id"], "weight": edge["weight"],
                        "weight_version": edge["weight_version"], "hop": hop,
                        "decay": decay, "source_observation_id": edge["source_observation_id"],
                        "evidence_id": edge["evidence_id"], "coverage": deepcopy(edge["coverage"]),
                    }
                    next_states.append((edge["target_id"], share, path + (edge_trace,), visited | {edge["target_id"]}))
                    if len(next_states) > MAX_PATH_STATES:
                        raise GraphDiffusionContractError(
                            f"path-state budget exceeded: maximum is {MAX_PATH_STATES}"
                        )
            states = next_states
        total = math.fsum(mass for _, mass, _, _ in states)
        if not math.isfinite(total):
            raise GraphDiffusionContractError("mass total must be finite")
        if abs(total - 1.0) > tolerance:
            raise GraphDiffusionContractError(f"mass conservation failed for seed {seed}")
        conservation.append({"seed_id": seed, "input_mass": 1.0, "output_mass": total, "within_tolerance": True})
        for node_id, mass, path, _ in states:
            values.append({
                "seed_id": seed, "node_id": node_id, "value": mass,
                "source_observation_id": nodes[seed]["source_observation_id"],
                "evidence_id": nodes[seed]["evidence_id"], "hop": len(path),
                "decay": decay, "edge_path": list(path),
            })
    values.sort(key=lambda row: (row["seed_id"], row["node_id"], row["hop"], tuple(edge["edge_id"] for edge in row["edge_path"])))
    shadow_values = {node_id: 0.0 for node_id in sorted(nodes)}
    for row in values:
        shadow_values[row["node_id"]] += row["value"]
    core = {
        "schema_version": SCHEMA_VERSION, "algorithm_version": ALGORITHM_VERSION,
        "as_of_date": data["as_of_date"], "snapshot_version": data["version"],
        "snapshot_evidence_locator": data["evidence_locator"], "seed_ids": seed_ids,
        "max_hops": max_hops, "decay": decay, "tolerance": tolerance,
        "baseline_no_diffusion": baseline, "shadow_values": shadow_values,
        "values": values, "mass_conservation": conservation,
        "production_impact": "NONE_SHADOW_ONLY",
    }
    _assert_finite(core)
    return {**core, "canonical_hash": _canonical_hash(core)}
