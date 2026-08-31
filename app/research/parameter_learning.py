"""Matched parameter learning；只產deterministic evidence，不改queue。"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import duckdb

from app.research.contracts import content_hash
from app.research.eligibility import DEFAULT_POLICY as DEFAULT_ELIGIBILITY_POLICY, build_projection as build_eligibility
from app.research.observation_ingest import DEFAULT_LEDGER_PATH
from app.research.parameter_catalog import load_parameter_catalog, parameter_catalog_hash
from app.research.receipt_store import write_immutable_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = PROJECT_ROOT / "config/research_learning_policy_v1.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts/autonomous_research/projections/learning"
# v1含wall-clock generated_at；v2以新identity/path並存，舊v1 immutable bytes不改寫。
PROJECTION_SCHEMA_VERSION = "research-parameter-learning.v2"


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("schema_version") != "research-learning-policy.v1":
        raise ValueError("INVALID_LEARNING_POLICY")
    if set(policy.get("numeric_parameters") or []) != {
        "horizon", "stop_loss_pct", "take_profit_pct", "max_group_exposure"
    }:
        raise ValueError("INVALID_LEARNING_PARAMETERS")
    for key in ("min_independent_matched_contrasts", "min_distinct_lineages", "min_interaction_contrasts", "min_robust_region_points", "min_global_regimes"):
        if not isinstance(policy.get(key), int) or policy[key] < 1:
            raise ValueError(f"INVALID_{key.upper()}")
    for key in ("direction_consistency_threshold", "flat_consistency_threshold"):
        if not isinstance(policy.get(key), (int, float)) or not 0.5 <= policy[key] <= 1:
            raise ValueError(f"INVALID_{key.upper()}")
    return policy


def numeric_catalog_values(parameter: str) -> list[float]:
    dimension = next(row for row in load_parameter_catalog()["dimensions"] if row["id"] == parameter)
    return sorted(float(value) for value in dimension["executable_values"] if value is not None)


def analyze_numeric_landscape(
    points: list[dict[str, Any]], *, parameter: str, policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    deadband = float(policy["effect_deadbands"]["score"])
    values = sorted({float(point["value"]) for point in points if point.get("value") is not None})
    by_value = {
        value: [point for point in points if point.get("value") is not None and float(point["value"]) == value]
        for value in values
    }
    summaries = {
        value: {
            "score": statistics.median(float(row["score"]) for row in rows),
            "total_return": statistics.median(float(row.get("total_return", 0)) for row in rows),
            "max_drawdown": statistics.median(float(row.get("max_drawdown", 0)) for row in rows),
        }
        for value, rows in by_value.items()
    }
    edges = []
    for lower, upper in zip(values, values[1:]):
        delta = summaries[upper]["score"] - summaries[lower]["score"]
        edges.append((lower, upper, delta))
    material = [delta for _, _, delta in edges if abs(delta) > deadband]
    higher = sum(delta > deadband for _, _, delta in edges)
    lower = sum(delta < -deadband for _, _, delta in edges)
    flat = sum(abs(delta) <= deadband for _, _, delta in edges)
    direction = "INSUFFICIENT_EVIDENCE"
    flags: list[str] = []
    if any(
        summaries[upper]["total_return"] - summaries[lower]["total_return"]
        > policy["effect_deadbands"]["total_return"]
        and summaries[upper]["max_drawdown"] - summaries[lower]["max_drawdown"]
        < -policy["effect_deadbands"]["max_drawdown"]
        for lower, upper, _ in edges
    ):
        flags.append("RISK_RETURN_TRADEOFF")
    if edges:
        ratio = max(higher, lower, flat) / len(edges)
        if flat / len(edges) >= policy["flat_consistency_threshold"]:
            direction, flags = "FLAT", ["LOW_SENSITIVITY"]
        elif higher / len(edges) >= policy["direction_consistency_threshold"]:
            direction = "HIGHER_LOOKS_BETTER"
        elif lower / len(edges) >= policy["direction_consistency_threshold"]:
            direction = "LOWER_LOOKS_BETTER"
        elif higher and lower:
            direction = "NON_MONOTONIC"
        else:
            direction = "UNSTABLE"
    peaks = []
    for index in range(1, len(values) - 1):
        left, center, right = values[index - 1:index + 2]
        if (
            summaries[center]["score"] - summaries[left]["score"] > deadband
            and summaries[center]["score"] - summaries[right]["score"] > deadband
        ):
            peaks.append(center)
    if peaks:
        direction = "INTERIOR_PEAK"
        center = peaks[0]
        index = values.index(center)
        drops = (
            summaries[center]["score"] - summaries[values[index - 1]]["score"],
            summaries[center]["score"] - summaries[values[index + 1]]["score"],
        )
        if min(drops) >= policy["sharp_peak"]["minimum_score_drop_each_side"]:
            flags.extend(["SHARP_PEAK", "OVERFIT_RISK"])
    basins = []
    needed = policy["min_robust_region_points"]
    for start in range(0, len(values) - needed + 1):
        region = values[start:start + needed]
        rows = [summaries[value] for value in region]
        catalog_values = numeric_catalog_values(parameter)
        catalog_indexes = [catalog_values.index(value) if value in catalog_values else -1 for value in region]
        catalog_adjacent = (
            all(index >= 0 for index in catalog_indexes)
            and all(right == left + 1 for left, right in zip(catalog_indexes, catalog_indexes[1:]))
        )
        if (
            catalog_adjacent
            and
            max(row["score"] for row in rows) - min(row["score"] for row in rows)
            <= policy["robust_basin"]["score_range_tolerance"]
            and all(row["total_return"] > policy["robust_basin"]["minimum_total_return"] for row in rows)
            and all(row["max_drawdown"] >= policy["robust_basin"]["max_drawdown_limit"] for row in rows)
        ):
            basins.append([region[0], region[-1]])
    if "SHARP_PEAK" in flags:
        basins = []
    best = max(values, key=lambda value: summaries[value]["score"]) if values else None
    edge_behavior = None
    next_direction = None
    if best == (values[-1] if values else None):
        edge_behavior, next_direction = "BEST_AT_UPPER_BOUNDARY", "EXPAND_UPWARD"
    elif best == (values[0] if values else None):
        edge_behavior, next_direction = "BEST_AT_LOWER_BOUNDARY", "EXPAND_LOWER"
    return {
        "parameter": parameter, "direction": direction, "flags": sorted(set(flags)),
        "edge_behavior": edge_behavior, "next_direction": next_direction,
        "tested_min": values[0] if values else None, "tested_max": values[-1] if values else None,
        "edges": [{"lower": a, "upper": b, "delta_score": delta} for a, b, delta in edges],
        "interior_peaks": peaks,
        "robust_basins": basins,
    }


def analyze_interaction(cells: list[dict[str, Any]], parameter_a: str, parameter_b: str, deadband: float = 0.01) -> dict[str, Any]:
    values_a = sorted({float(row[parameter_a]) for row in cells})
    values_b = sorted({float(row[parameter_b]) for row in cells})
    if len(values_a) != 2 or len(values_b) != 2:
        return {"classification": "INSUFFICIENT_EVIDENCE"}
    lookup = {(float(row[parameter_a]), float(row[parameter_b])): float(row["score"]) for row in cells}
    if len(lookup) != 4:
        return {"classification": "INSUFFICIENT_EVIDENCE"}
    low_a, high_a = values_a
    low_b, high_b = values_b
    did = (lookup[(high_a, high_b)] - lookup[(low_a, high_b)]) - (lookup[(high_a, low_b)] - lookup[(low_a, low_b)])
    return {
        "classification": "CONDITIONAL_EFFECT" if abs(did) > deadband else "NO_INTERACTION_SIGNAL",
        "parameter_a": parameter_a, "parameter_b": parameter_b,
        "dependent_on": parameter_b, "did": did,
    }


def classify_matched_contrasts(
    contrasts: list[dict[str, Any]], policy: dict[str, Any] | None = None,
    *, parameter: str | None = None,
) -> dict[str, Any]:
    """只用matched deltas分類方向，避免raw level confounding。"""
    policy = policy or load_policy()
    deadband = policy["effect_deadbands"]["score"]
    # 缺失或空白 lineage 不能視作獨立證據；先拒絕，避免 unit fixture
    # 意外把沒有 provenance 的 contrast 升格成方向訊號。
    if any(not isinstance(item.get("lineage_id"), str) or not item["lineage_id"].strip() for item in contrasts):
        return {"direction": "INSUFFICIENT_EVIDENCE", "edge_behavior": None, "next_direction": None}
    count = len(contrasts)
    higher = sum(item["delta_score"] > deadband for item in contrasts)
    lower = sum(item["delta_score"] < -deadband for item in contrasts)
    flat = sum(abs(item["delta_score"]) <= deadband for item in contrasts)
    result = {"direction": "INSUFFICIENT_EVIDENCE", "edge_behavior": None, "next_direction": None}
    if count < policy["min_independent_matched_contrasts"]:
        return result
    lineage_ids = {
        str(item["lineage_id"])
        for item in contrasts
        if item.get("lineage_id") is not None
    }
    if len(lineage_ids) < policy["min_distinct_lineages"]:
        return result
    if flat / count >= policy["flat_consistency_threshold"]:
        return {**result, "direction": "FLAT"}
    if higher / count >= policy["direction_consistency_threshold"]:
        boundary_supported = bool(parameter) and any(
            item.get("upper") == max(numeric_catalog_values(parameter))
            and item["delta_score"] > deadband for item in contrasts
        )
        return {
            "direction": "HIGHER_LOOKS_BETTER",
            "edge_behavior": "BEST_AT_UPPER_BOUNDARY" if boundary_supported else None,
            "next_direction": "EXPAND_UPWARD" if boundary_supported else None,
        }
    if lower / count >= policy["direction_consistency_threshold"]:
        boundary_supported = bool(parameter) and any(
            item.get("lower") == min(numeric_catalog_values(parameter))
            and item["delta_score"] < -deadband for item in contrasts
        )
        return {
            "direction": "LOWER_LOOKS_BETTER",
            "edge_behavior": "BEST_AT_LOWER_BOUNDARY" if boundary_supported else None,
            "next_direction": "EXPAND_LOWER" if boundary_supported else None,
        }
    return {**result, "direction": "UNSTABLE" if higher and lower else "NON_MONOTONIC"}


def canonical_execution_profile_identity(profile: Any) -> str:
    """所有 A5 consumer 共用完整 execution-profile identity。"""
    if not isinstance(profile, dict):
        raise ValueError("INVALID_EXECUTION_PROFILE")
    return content_hash(profile)


def _validator(payload: dict[str, Any]) -> list[str]:
    required = {
        "schema_version", "projection_id", "projection_schema_version",
        "eligibility_projection_id", "failure_projection_id", "input_corpus_hash",
        "ledger_snapshot_hash", "learning_policy_version", "learning_policy_hash",
        "parameter_catalog_hash", "status", "counts", "matched_contrasts",
        "parameter_findings", "interaction_findings", "robust_regions",
    }
    if set(payload) != required or payload.get("schema_version") != PROJECTION_SCHEMA_VERSION:
        return ["INVALID_LEARNING_PROJECTION_SHAPE"]
    identity = {key: payload.get(key) for key in (
        "projection_schema_version", "eligibility_projection_id", "failure_projection_id",
        "input_corpus_hash", "ledger_snapshot_hash", "learning_policy_version",
        "learning_policy_hash", "parameter_catalog_hash",
    )}
    errors = []
    if payload.get("projection_id") != content_hash(identity):
        errors.append("LEARNING_PROJECTION_ID_MISMATCH")
    contrasts = payload.get("matched_contrasts")
    if not isinstance(contrasts, list) or len({row.get("contrast_id") for row in contrasts if isinstance(row, dict)}) != len(contrasts):
        errors.append("INVALID_CONTRAST_LIST")
    else:
        for row in contrasts:
            expected_id = content_hash({"policy": payload["learning_policy_version"], "parameter": row.get("parameter"), "low": row.get("low_evidence_unit_id"), "high": row.get("high_evidence_unit_id")})
            if (not isinstance(row.get("lineage_id"), str) or not row["lineage_id"].strip()
                    or row.get("contrast_id") != expected_id
                    or not all(isinstance(row.get(key), str) and row[key] for key in ("low_observation_id", "high_observation_id", "low_evidence_unit_id", "high_evidence_unit_id"))):
                errors.append("INVALID_CONTRAST_PROVENANCE")
                break
    counts = payload.get("counts")
    if not isinstance(counts, dict) or counts != {
        "eligible_observations": counts.get("eligible_observations") if isinstance(counts, dict) else None,
        "matched_contrasts": len(contrasts) if isinstance(contrasts, list) else None,
        "parameter_findings": len(payload.get("parameter_findings") or []),
    }:
        errors.append("LEARNING_COUNT_MISMATCH")
    return errors


def _cohort_profile_hash(raw_profile: str) -> str:
    return canonical_execution_profile_identity(json.loads(raw_profile))


def build_projection(
    *, ledger_path: Path = DEFAULT_LEDGER_PATH, policy_path: Path = DEFAULT_POLICY,
    eligibility_output_root: Path | None = None, output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    eligibility = build_eligibility(
        ledger_path=ledger_path,
        output_root=eligibility_output_root or output_root.parent / "eligibility",
    )
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT o.observation_id,o.evidence_unit_id,o.lineage_id,o.score,o.total_return,
                   o.max_drawdown,o.win_rate,o.avg_trade_return,o.trade_count,o.p_value,
                   t.topic_family_id,t.research_stage,t.regime_scope_json,t.dataset_hash,
                   t.ranking_source_hash,t.parameters_json,t.execution_profile_json
            FROM observations o JOIN trial_specs t ON t.trial_spec_id=o.executed_trial_spec_id
            JOIN eligibility_decisions e ON e.subject_id=o.observation_id
             AND e.subject_type='OBSERVATION' AND e.projection_id=?
            WHERE e.eligibility_status='ADAPTIVE_ELIGIBLE' AND e.evidence_weight=1
            ORDER BY o.observation_id
            """, [eligibility["projection_id"]]
        ).fetchall()
    finally:
        connection.close()
    names = ("observation_id","evidence_unit_id","lineage_id","score","total_return","max_drawdown","win_rate","avg_trade_return","trade_count","p_value","topic_family_id","research_stage","regime_scope_json","dataset_hash","ranking_source_hash","parameters_json","execution_profile_json")
    observations = [dict(zip(names, row)) for row in rows]
    findings = []
    contrasts = []
    for parameter in policy["numeric_parameters"]:
        catalog_values = numeric_catalog_values(parameter)
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in observations:
            parameters = json.loads(row["parameters_json"])
            value = parameters.get(parameter)
            if value is None:
                continue
            regime = json.loads(row["regime_scope_json"]).get("regime_id")
            others = tuple((key, parameters.get(key)) for key in policy["numeric_parameters"] if key != parameter)
            key = (
                row["topic_family_id"], regime, row["dataset_hash"],
                row["ranking_source_hash"], row["research_stage"], row["lineage_id"],
                _cohort_profile_hash(row["execution_profile_json"]), others,
            )
            groups[key].append({**row, "value": float(value)})
        scoped_points: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        scoped_shapes: dict[tuple[str, str], list[tuple[str, Any, str]]] = defaultdict(list)
        for key, group in groups.items():
            by_value = {item["value"]: item for item in group}
            for lower, upper in zip(catalog_values, catalog_values[1:]):
                if lower not in by_value or upper not in by_value:
                    continue
                low, high = by_value[lower], by_value[upper]
                contrast = {
                    "contrast_id": content_hash({"policy": policy["policy_version"], "parameter": parameter, "low": low["evidence_unit_id"], "high": high["evidence_unit_id"]}),
                    "parameter": parameter, "topic_family_id": key[0], "regime_id": key[1],
                    "lineage_id": low["lineage_id"], "lower": lower, "upper": upper,
                    "low_observation_id": low["observation_id"], "high_observation_id": high["observation_id"],
                    "low_evidence_unit_id": low["evidence_unit_id"], "high_evidence_unit_id": high["evidence_unit_id"],
                    "delta_score": high["score"] - low["score"],
                    "delta_total_return": high["total_return"] - low["total_return"],
                    "delta_max_drawdown": high["max_drawdown"] - low["max_drawdown"],
                    "risk_return_tradeoff": (
                        high["total_return"] - low["total_return"] > policy["effect_deadbands"]["total_return"]
                        and high["max_drawdown"] - low["max_drawdown"] < -policy["effect_deadbands"]["max_drawdown"]
                    ),
                }
                contrasts.append(contrast)
            for item in group:
                scoped_points[(str(key[0]), str(key[1]))].append(item)
            stratum_shape = analyze_numeric_landscape(group, parameter=parameter, policy=policy)
            if stratum_shape["direction"] == "INTERIOR_PEAK":
                for center in stratum_shape["interior_peaks"]:
                    scoped_shapes[(str(key[0]), str(key[1]))].append(
                        ("INTERIOR_PEAK", center, str(key[5]))
                    )
                    if "SHARP_PEAK" in stratum_shape["flags"]:
                        scoped_shapes[(str(key[0]), str(key[1]))].append(
                            ("SHARP_PEAK", center, str(key[5]))
                        )
            for region in stratum_shape["robust_basins"]:
                scoped_shapes[(str(key[0]), str(key[1]))].append(
                    ("ROBUST_BASIN", tuple(region), str(key[5]))
                )
        for (topic, regime), points in scoped_points.items():
            finding = analyze_numeric_landscape(points, parameter=parameter, policy=policy)
            # pooled raw levels只作描述；正式flags/shape由matched strata重建。
            finding["flags"] = []
            finding["robust_basins"] = []
            finding["interior_peaks"] = []
            scope_contrasts = [
                item for item in contrasts
                if item["parameter"] == parameter and item["topic_family_id"] == topic and item["regime_id"] == regime
            ]
            lineages = {item["lineage_id"] for item in scope_contrasts}
            matched_direction = classify_matched_contrasts(scope_contrasts, policy, parameter=parameter)
            finding.update(matched_direction)
            material_higher = sum(item["delta_score"] > policy["effect_deadbands"]["score"] for item in scope_contrasts)
            material_lower = sum(item["delta_score"] < -policy["effect_deadbands"]["score"] for item in scope_contrasts)
            if finding["direction"] == "FLAT":
                finding["flags"] = sorted(set([*finding.get("flags", []), "LOW_SENSITIVITY"]))
            confidence = min(1.0, len(scope_contrasts) / max(1, policy["min_independent_matched_contrasts"])) * min(1.0, len(lineages) / policy["min_distinct_lineages"])
            finding.update({
                "scope": "TOPIC_X_REGIME", "topic_family_id": topic, "regime_id": regime,
                "raw_observation_count": len(points),
                "deduplicated_observation_count": len({item["evidence_unit_id"] for item in points}),
                "distinct_lineage_count": len(lineages),
                "independent_matched_contrast_count": len(scope_contrasts),
                "evidence_confidence_score": round(confidence, 6),
                "evidence_confidence_label": "HIGH" if confidence >= 0.75 and len(lineages) >= 2 else "MEDIUM" if confidence >= 0.5 else "LOW",
            })
            if any(item["risk_return_tradeoff"] for item in scope_contrasts):
                finding["flags"] = sorted(set([*finding.get("flags", []), "RISK_RETURN_TRADEOFF"]))
            if len(lineages) < policy["min_distinct_lineages"]:
                finding["robust_basins"] = []
            # Shape不得由跨stratum pooled medians拼成；只接受多lineage同shape支持。
            shapes = scoped_shapes[(topic, regime)]
            basin_support: dict[Any, set[str]] = defaultdict(set)
            peak_support: dict[Any, set[str]] = defaultdict(set)
            sharp_support: dict[Any, set[str]] = defaultdict(set)
            for kind, value, lineage in shapes:
                if kind == "ROBUST_BASIN":
                    basin_support[value].add(lineage)
                elif kind == "INTERIOR_PEAK":
                    peak_support[value].add(lineage)
                elif kind == "SHARP_PEAK":
                    sharp_support[value].add(lineage)
            finding["robust_basins"] = [
                list(region) for region, support in basin_support.items()
                if len(support) >= policy["min_distinct_lineages"]
            ]
            supported_peaks = [center for center, support in peak_support.items() if len(support) >= policy["min_distinct_lineages"]]
            if supported_peaks:
                finding["direction"] = "INTERIOR_PEAK"
                finding["interior_peaks"] = sorted(supported_peaks)
                finding["edge_behavior"] = None
                finding["next_direction"] = None
                finding["flags"] = [flag for flag in finding["flags"] if flag != "LOW_SENSITIVITY"]
            if any(len(support) >= policy["min_distinct_lineages"] for support in sharp_support.values()):
                finding["flags"] = sorted(set([*finding["flags"], "SHARP_PEAK", "OVERFIT_RISK"]))
                finding["robust_basins"] = []
            findings.append(finding)
        regimes = {str(json.loads(row["regime_scope_json"]).get("regime_id")) for row in observations}
        if len(regimes) < policy["min_global_regimes"]:
            findings.append({"scope": "GLOBAL", "parameter": parameter, "direction": "GLOBAL_NOT_ESTIMABLE", "flags": ["INSUFFICIENT_REGIME_COVERAGE"]})
    interaction_pairs = (
        ("horizon", "stop_loss_pct"), ("horizon", "take_profit_pct"),
        ("stop_loss_pct", "take_profit_pct"),
        ("stop_loss_pct", "max_group_exposure"),
        ("take_profit_pct", "max_group_exposure"),
        ("horizon", "max_group_exposure"),
    )
    interaction_findings = []
    for parameter_a, parameter_b in interaction_pairs:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in observations:
            parameters = json.loads(row["parameters_json"])
            if parameters.get(parameter_a) is None or parameters.get(parameter_b) is None:
                continue
            regime = json.loads(row["regime_scope_json"]).get("regime_id")
            others = tuple((key, parameters.get(key)) for key in policy["numeric_parameters"] if key not in {parameter_a, parameter_b})
            key = (
                row["topic_family_id"], regime, row["dataset_hash"],
                row["ranking_source_hash"], row["research_stage"], row["lineage_id"],
                _cohort_profile_hash(row["execution_profile_json"]), others,
            )
            groups[key].append({**row, parameter_a: parameters[parameter_a], parameter_b: parameters[parameter_b]})
        scoped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for key, cells in groups.items():
            values_a = numeric_catalog_values(parameter_a)
            values_b = numeric_catalog_values(parameter_b)
            for low_a, high_a in zip(values_a, values_a[1:]):
                for low_b, high_b in zip(values_b, values_b[1:]):
                    subset = [
                        cell for cell in cells
                        if float(cell[parameter_a]) in {low_a, high_a}
                        and float(cell[parameter_b]) in {low_b, high_b}
                    ]
                    result = analyze_interaction(subset, parameter_a, parameter_b, policy["effect_deadbands"]["score"])
                    if result["classification"] == "CONDITIONAL_EFFECT":
                        scoped[(str(key[0]), str(key[1]))].append({**result, "lineage_id": key[5]})
        for (topic, regime), results in scoped.items():
            lineages = {item["lineage_id"] for item in results}
            if len(results) >= policy["min_interaction_contrasts"] and len(lineages) >= policy["min_distinct_lineages"]:
                interaction_findings.append({
                    "scope": "TOPIC_X_REGIME", "topic_family_id": topic, "regime_id": regime,
                    "parameter_a": parameter_a, "parameter_b": parameter_b,
                    "dependent_on": parameter_b, "classification": "CONDITIONAL_EFFECT",
                    "did_median": statistics.median(item["did"] for item in results),
                    "independent_interaction_count": len(results), "distinct_lineage_count": len(lineages),
                })
    identity = {
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "eligibility_projection_id": eligibility["projection_id"],
        "failure_projection_id": eligibility["projection_id"],
        "input_corpus_hash": eligibility["input_corpus_hash"],
        "ledger_snapshot_hash": eligibility["ledger_snapshot_hash"],
        "learning_policy_version": policy["policy_version"], "learning_policy_hash": content_hash(policy),
        "parameter_catalog_hash": parameter_catalog_hash(),
    }
    projection_id = content_hash(identity)
    payload = {
        "schema_version": PROJECTION_SCHEMA_VERSION, "projection_id": projection_id,
        **identity,
        "status": "OK" if contrasts else "INSUFFICIENT_EVIDENCE",
        "counts": {"eligible_observations": len(observations), "matched_contrasts": len(contrasts), "parameter_findings": len(findings)},
        "matched_contrasts": contrasts, "parameter_findings": findings,
        "interaction_findings": interaction_findings, "robust_regions": [
            {"parameter": finding["parameter"], "scope": finding.get("scope"), "range": region, "classification": "ROBUST_BASIN"}
            for finding in findings for region in finding.get("robust_basins", [])
        ],
    }
    target = output_root / f"{projection_id[7:]}.json"
    write_immutable_json(target, payload, validator=_validator, identity_field="projection_id")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    result = build_projection(ledger_path=args.ledger, policy_path=args.policy, output_root=args.output_root)
    print(json.dumps({key: result[key] for key in ("projection_id", "status", "counts")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
