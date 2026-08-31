"""Native evidence replay bundle 的匯出與獨立驗證。"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import duckdb

from app.research.contracts import content_hash
from app.research.parameter_catalog import load_parameter_catalog
from app.research.parameter_learning import canonical_execution_profile_identity


BUNDLE_SCHEMA = "native-evidence-replay-bundle.v1"
VERIFICATION_SCHEMA = "native-evidence-replay-verification.v1"
REQUIRED_PARAMETERS = {
    "horizon",
    "stop_loss_pct",
    "take_profit_pct",
    "max_group_exposure",
    "regime_gate",
    "risk_guard",
    "entry_filter",
}
METRIC_FIELDS = (
    "total_return",
    "max_drawdown",
    "win_rate",
    "avg_trade_return",
    "trade_count",
    "score",
    "p_value",
    "robust_neighbor_pass_count",
)
EXPECTED_BOUNDARY = {
    "development_only": True,
    "manual_only": True,
    "production_promotion_allowed": False,
    "canonical_queue_write_allowed": False,
    "scheduler_write_allowed": False,
    "isolated_root_retained": False,
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def semantic_hash(payload: Mapping[str, Any]) -> str:
    return content_hash(payload, omit={"generated_at"})


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _relative_path_errors(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or not value:
        return [f"{field}:INVALID_REPO_RELATIVE_PATH"]
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        return [f"{field}:INVALID_REPO_RELATIVE_PATH"]
    return []


def _eligibility_for(row: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    checks = {
        "TERMINAL_EXECUTION_NOT_SUCCESSFUL": row.get("terminal_status") != "SUCCEEDED",
        "EXECUTION_FACTS_NOT_OBSERVED": row.get("observation_status") != "OBSERVED",
        "REQUESTED_EXECUTED_IDENTITY_NOT_EXACT": row.get("identity_match_status") != "EXACT",
        "INVALID_LINEAGE": row.get("lineage_resolution_status") != "VALID",
        "NON_SEALED_STATUS_NOT_PROVEN": row.get("sealed_usage_status") != "PROVEN_NON_SEALED",
        "REPLAY_RESEARCH_STAGE_NOT_DEVELOPMENT": row.get("research_stage")
        != "DEVELOPMENT_SCREEN",
        "REGIME_IDENTITY_INVALID": row.get("regime_id") in {None, "", "UNKNOWN", "UNSCOPED"},
    }
    parameters = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
    checks["PARAMETER_IDENTITY_INCOMPLETE"] = (
        set(parameters) != REQUIRED_PARAMETERS or parameters.get("horizon") is None
    )
    checks["COVERAGE_ONLY_DIMENSION_EXECUTED"] = any(
        parameters.get(key) is not None for key in ("regime_gate", "risk_guard", "entry_filter")
    )
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    checks["RESULT_METRICS_INCOMPLETE"] = any(result.get(key) is None for key in METRIC_FIELDS)
    reasons.extend(reason for reason, failed in checks.items() if failed)
    if row.get("sealed_usage_status") == "SEALED":
        return "SEALED_VALIDATION_ONLY", ["SEALED_EVIDENCE_EXCLUDED"]
    return (
        ("INVALID_LINEAGE", reasons)
        if reasons
        else ("ADAPTIVE_ELIGIBLE", ["ALL_ELIGIBILITY_GATES_PASSED"])
    )


def _catalog_values(catalog: Mapping[str, Any], parameter: str) -> list[float]:
    dimension = next(
        row for row in catalog.get("dimensions", []) if isinstance(row, dict) and row.get("id") == parameter
    )
    return sorted(float(value) for value in dimension["executable_values"] if value is not None)


def recompute_contrasts(
    observations: list[dict[str, Any]], catalog: Mapping[str, Any], policy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    contrasts: list[dict[str, Any]] = []
    parameters = list(policy.get("numeric_parameters") or [])
    for parameter in parameters:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in observations:
            values = row["parameters"]
            value = values.get(parameter)
            if value is None:
                continue
            others = tuple((key, values.get(key)) for key in parameters if key != parameter)
            key = (
                row["topic_family_id"],
                row["regime_id"],
                row["dataset_hash"],
                row["ranking_source_hash"],
                row["research_stage"],
                row["lineage_id"],
                canonical_execution_profile_identity(row.get("execution_profile")),
                others,
            )
            groups[key].append({**row, "parameter_value": float(value)})
        for key, rows in groups.items():
            by_value = {row["parameter_value"]: row for row in rows}
            for lower, upper in zip(
                _catalog_values(catalog, parameter), _catalog_values(catalog, parameter)[1:]
            ):
                if lower not in by_value or upper not in by_value:
                    continue
                low, high = by_value[lower], by_value[upper]
                contrasts.append(
                    {
                        "contrast_id": content_hash(
                            {
                                "policy": policy["policy_version"],
                                "parameter": parameter,
                                "low": low["evidence_unit_id"],
                                "high": high["evidence_unit_id"],
                            }
                        ),
                        "parameter": parameter,
                        "topic_family_id": key[0],
                        "regime_id": key[1],
                        "lineage_id": key[5],
                        "lower": lower,
                        "upper": upper,
                        "delta_score": high["result"]["score"] - low["result"]["score"],
                        "delta_total_return": high["result"]["total_return"]
                        - low["result"]["total_return"],
                        "delta_max_drawdown": high["result"]["max_drawdown"]
                        - low["result"]["max_drawdown"],
                        "risk_return_tradeoff": (
                            high["result"]["total_return"] - low["result"]["total_return"]
                            > policy["effect_deadbands"]["total_return"]
                            and high["result"]["max_drawdown"]
                            - low["result"]["max_drawdown"]
                            < -policy["effect_deadbands"]["max_drawdown"]
                        ),
                    }
                )
    return sorted(contrasts, key=lambda row: row["contrast_id"])


def _bundle_observations(
    connection: duckdb.DuckDBPyConnection,
    eligibility: Mapping[str, Any],
) -> list[dict[str, Any]]:
    decision_by_id = {
        row["subject_id"]: row
        for row in eligibility.get("decisions", [])
        if row.get("subject_type") == "OBSERVATION"
    }
    rows = connection.execute(
        """
        SELECT o.observation_id,o.execution_unit_id,o.receipt_id,o.executed_trial_spec_id,
               o.lineage_id,o.result_unit_id,o.evidence_unit_id,o.scenario_id,
               o.total_return,o.max_drawdown,o.win_rate,o.avg_trade_return,o.trade_count,
               o.score,o.p_value,o.robust_neighbor_pass_count,o.result_payload_hash,
               o.identity_policy_version,o.metric_policy_version,o.attempt_inclusion_policy_version,
               r.run_id,r.intent_id,r.terminal_status,r.observation_status,r.identity_match_status,
               u.requested_trial_spec_id,u.sealed_usage_status,u.lineage_resolution_status,
               u.episode_ids_json,u.artifact_refs_json,
               t.topic_id,t.topic_family_id,t.research_stage,t.regime_scope_json,t.dataset_hash,
               t.ranking_source_hash,t.parameters_json,t.execution_profile_json,
               p.source_corpus_path
        FROM observations o
        JOIN run_receipts r ON r.receipt_id=o.receipt_id
        JOIN execution_units u ON u.execution_unit_id=o.execution_unit_id
        JOIN trial_specs t ON t.trial_spec_id=o.executed_trial_spec_id
        JOIN observation_provenance p ON p.observation_id=o.observation_id
        ORDER BY o.observation_id,p.source_corpus_path
        """
    ).fetchall()
    names = [item[0] for item in connection.description]
    observations: dict[str, dict[str, Any]] = {}
    for values in rows:
        row = dict(zip(names, values))
        observation_id = row["observation_id"]
        if observation_id in observations:
            observations[observation_id]["provenance_paths"].append(row["source_corpus_path"])
            continue
        regime = json.loads(row["regime_scope_json"])
        result = {field: row[field] for field in METRIC_FIELDS}
        result["scenario_id"] = row["scenario_id"]
        decision = decision_by_id.get(observation_id, {})
        observations[observation_id] = {
            "observation_id": observation_id,
            "execution_unit_id": row["execution_unit_id"],
            "receipt_id": row["receipt_id"],
            "run_id": row["run_id"],
            "intent_id": row["intent_id"],
            "requested_trial_spec_id": row["requested_trial_spec_id"],
            "executed_trial_spec_id": row["executed_trial_spec_id"],
            "result_unit_id": row["result_unit_id"],
            "evidence_unit_id": row["evidence_unit_id"],
            "lineage_id": row["lineage_id"],
            "terminal_status": row["terminal_status"],
            "observation_status": row["observation_status"],
            "identity_match_status": row["identity_match_status"],
            "sealed_usage_status": row["sealed_usage_status"],
            "lineage_resolution_status": row["lineage_resolution_status"],
            "episode_ids": json.loads(row["episode_ids_json"]),
            "artifact_refs": json.loads(row["artifact_refs_json"]),
            "topic_id": row["topic_id"],
            "topic_family_id": row["topic_family_id"],
            "research_stage": row["research_stage"],
            "regime_scope": regime,
            "regime_id": regime.get("regime_id"),
            "dataset_hash": row["dataset_hash"],
            "ranking_source_hash": row["ranking_source_hash"],
            "parameters": json.loads(row["parameters_json"]),
            "execution_profile": json.loads(row["execution_profile_json"]),
            "result": result,
            "source_result_payload_hash": row["result_payload_hash"],
            "result_semantic_hash": content_hash(result),
            "identity_policy_version": row["identity_policy_version"],
            "metric_policy_version": row["metric_policy_version"],
            "attempt_inclusion_policy_version": row["attempt_inclusion_policy_version"],
            "eligibility": {
                "status": decision.get("eligibility_status"),
                "evidence_weight": decision.get("evidence_weight"),
                "reason_codes": sorted(decision.get("reason_codes") or []),
            },
            "provenance_paths": [row["source_corpus_path"]],
        }
    return [observations[key] for key in sorted(observations)]


def build_bundle(
    *,
    ledger_path: Path,
    cycle_receipts: list[dict[str, Any]],
    eligibility: Mapping[str, Any],
    learning: Mapping[str, Any],
    project_root: Path,
    source_commit: str,
    generated_at: str,
) -> dict[str, Any]:
    catalog = load_parameter_catalog()
    learning_policy = _load_json(project_root / "config/research_learning_policy_v1.json")
    eligibility_policy = _load_json(project_root / "config/research_eligibility_policy_v1.json")
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        observations = _bundle_observations(connection, eligibility)
    finally:
        connection.close()
    contrasts = recompute_contrasts(observations, catalog, learning_policy)
    source_contrasts = sorted(
        deepcopy(learning.get("matched_contrasts") or []), key=lambda row: row["contrast_id"]
    )
    if contrasts != source_contrasts:
        raise ValueError("SOURCE_LEARNING_PROJECTION_PARITY_MISMATCH")
    scope_counts: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in contrasts:
        key = (row["parameter"], row["topic_family_id"], row["regime_id"])
        target = scope_counts.setdefault(key, {"contrasts": 0, "lineages": set()})
        target["contrasts"] += 1
        target["lineages"].add(row["lineage_id"])
    scopes = [
        {
            "parameter": key[0],
            "topic_family_id": key[1],
            "regime_id": key[2],
            "matched_contrast_count": value["contrasts"],
            "distinct_lineage_count": len(value["lineages"]),
        }
        for key, value in sorted(scope_counts.items())
    ]
    admission = any(
        row["matched_contrast_count"] >= learning_policy["min_independent_matched_contrasts"]
        and row["distinct_lineage_count"] >= learning_policy["min_distinct_lineages"]
        for row in scopes
    )
    compact_eligibility = {
        "policy_hash": content_hash(eligibility_policy),
        "decisions": [
            {
                "observation_id": row["observation_id"],
                "status": row["eligibility"]["status"],
                "evidence_weight": row["eligibility"]["evidence_weight"],
                "reason_codes": row["eligibility"]["reason_codes"],
            }
            for row in observations
        ],
    }
    compact_learning = {
        "policy_hash": content_hash(learning_policy),
        "catalog_hash": content_hash(catalog),
        "eligible_evidence_unit_ids": sorted(
            row["evidence_unit_id"]
            for row in observations
            if row["eligibility"]["status"] == "ADAPTIVE_ELIGIBLE"
        ),
        "matched_contrasts": contrasts,
        "scope_evidence": scopes,
    }
    payload: dict[str, Any] = {
        "schema_version": BUNDLE_SCHEMA,
        "bundle_id": "",
        "generated_at": generated_at,
        "source_commit": source_commit,
        "boundary": {
            "development_only": True,
            "manual_only": True,
            "production_promotion_allowed": False,
            "canonical_queue_write_allowed": False,
            "scheduler_write_allowed": False,
            "isolated_root_retained": False,
        },
        "policies": {
            "parameter_catalog_hash": content_hash(catalog),
            "eligibility_policy_hash": content_hash(eligibility_policy),
            "learning_policy_hash": content_hash(learning_policy),
            "learning_policy": learning_policy,
        },
        "cycles": sorted(deepcopy(cycle_receipts), key=lambda row: row["cycle_identity"]),
        "observations": observations,
        "eligibility_projection": {
            "projection_id": eligibility["projection_id"],
            "source_semantic_hash": semantic_hash(eligibility),
            "replay_semantic_hash": content_hash(compact_eligibility),
            "counts": eligibility["counts"],
        },
        "learning_projection": {
            "projection_id": learning["projection_id"],
            "source_semantic_hash": semantic_hash(learning),
            "replay_semantic_hash": content_hash(compact_learning),
            "counts": learning["counts"],
            "matched_contrasts": contrasts,
            "scope_evidence": scopes,
            "source_projection_parity": True,
        },
        "admission": {
            "status": "PASS" if admission else "NO-GO_INSUFFICIENT_EVIDENCE",
            "required_matched_contrasts": learning_policy["min_independent_matched_contrasts"],
            "required_distinct_lineages": learning_policy["min_distinct_lineages"],
        },
        "counts": {
            "cycles": len(cycle_receipts),
            "execution_units": len(observations),
            "observations": len(observations),
            "adaptive_eligible": sum(
                row["eligibility"]["status"] == "ADAPTIVE_ELIGIBLE" for row in observations
            ),
            "distinct_lineages": len({row["lineage_id"] for row in observations}),
            "matched_contrasts": len(contrasts),
        },
    }
    payload["bundle_id"] = content_hash(payload, omit={"bundle_id", "generated_at"})
    return payload


def verify_bundle(
    payload: Mapping[str, Any], *, project_root: Path | None = None
) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != BUNDLE_SCHEMA:
        errors.append("INVALID_SCHEMA")
    if payload.get("bundle_id") != content_hash(payload, omit={"bundle_id", "generated_at"}):
        errors.append("BUNDLE_HASH_MISMATCH")
    if payload.get("boundary") != EXPECTED_BOUNDARY:
        errors.append("BOUNDARY_MISMATCH")
    observations = payload.get("observations")
    cycles = payload.get("cycles")
    if not isinstance(observations, list) or not isinstance(cycles, list):
        errors.append("MISSING_ROWS")
        observations = []
        cycles = []
    identities = {
        field: [row.get(field) for row in observations if isinstance(row, dict)]
        for field in ("observation_id", "execution_unit_id", "evidence_unit_id")
    }
    for field, values in identities.items():
        if any(not isinstance(value, str) or not value for value in values):
            errors.append(f"MISSING_{field.upper()}")
        if len(values) != len(set(values)):
            errors.append(f"DUPLICATE_{field.upper()}")
    cycle_by_run = {
        row.get("run_id"): row for row in cycles if isinstance(row, dict) and row.get("run_id")
    }
    if len(cycle_by_run) != len(cycles):
        errors.append("DUPLICATE_CYCLE_IDENTITY")
    recomputed_eligibility: Counter[str] = Counter()
    eligible_rows: list[dict[str, Any]] = []
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            errors.append(f"OBSERVATION_{index}:INVALID_ROW")
            continue
        cycle = cycle_by_run.get(row.get("run_id"))
        if cycle is None or row.get("receipt_id") != cycle.get("receipt_id"):
            errors.append(f"OBSERVATION_{index}:CYCLE_RECEIPT_MISMATCH")
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if row.get("result_semantic_hash") != content_hash(result):
            errors.append(f"OBSERVATION_{index}:RESULT_HASH_MISMATCH")
        evidence_id = content_hash(
            {
                "executed_trial_spec_id": row.get("executed_trial_spec_id"),
                "lineage_id": row.get("lineage_id"),
                "result_unit_id": row.get("result_unit_id"),
                "metric_policy_version": row.get("metric_policy_version"),
            }
        )
        if row.get("evidence_unit_id") != evidence_id:
            errors.append(f"OBSERVATION_{index}:EVIDENCE_ID_MISMATCH")
        observation_identity = {
            "schema_version": "research-observation-identity.v1",
            "identity_policy_version": row.get("identity_policy_version"),
            "origin_execution_id": row.get("execution_unit_id"),
            "executed_trial_identity": row.get("executed_trial_spec_id"),
            "executed_lineage_id": row.get("lineage_id"),
            "evidence_unit_id": evidence_id,
            "result_unit_id": row.get("result_unit_id"),
            "metric_policy_version": row.get("metric_policy_version"),
            "attempt_inclusion_policy_version": row.get("attempt_inclusion_policy_version"),
        }
        if row.get("observation_id") != content_hash(observation_identity):
            errors.append(f"OBSERVATION_{index}:OBSERVATION_ID_MISMATCH")
        status, reasons = _eligibility_for(row)
        recomputed_eligibility[status] += 1
        supplied = row.get("eligibility") if isinstance(row.get("eligibility"), dict) else {}
        if supplied.get("status") != status or sorted(supplied.get("reason_codes") or []) != reasons:
            errors.append(f"OBSERVATION_{index}:ELIGIBILITY_MISMATCH")
        if supplied.get("evidence_weight") != int(status == "ADAPTIVE_ELIGIBLE"):
            errors.append(f"OBSERVATION_{index}:EVIDENCE_WEIGHT_MISMATCH")
        if status == "ADAPTIVE_ELIGIBLE":
            eligible_rows.append(row)
        for path_index, path in enumerate(row.get("provenance_paths") or []):
            errors.extend(_relative_path_errors(path, f"observations[{index}].provenance_paths[{path_index}]"))
    for index, cycle in enumerate(cycles):
        if not isinstance(cycle, dict):
            continue
        if cycle.get("terminal_status") != "SUCCEEDED":
            errors.append(f"CYCLE_{index}:TERMINAL_STATUS")
        if cycle.get("observation_status") != "OBSERVED":
            errors.append(f"CYCLE_{index}:OBSERVATION_STATUS")
        if cycle.get("identity_match_status") != "EXACT":
            errors.append(f"CYCLE_{index}:IDENTITY_STATUS")
        if cycle.get("second_ingest_observations_inserted") != 0:
            errors.append(f"CYCLE_{index}:SECOND_INGEST_NOT_ZERO")
        if cycle.get("execution_unit_count") != sum(
            row.get("run_id") == cycle.get("run_id") for row in observations
        ):
            errors.append(f"CYCLE_{index}:UNIT_COUNT_MISMATCH")
    policies = payload.get("policies") if isinstance(payload.get("policies"), dict) else {}
    learning_policy = policies.get("learning_policy")
    if not isinstance(learning_policy, dict) or content_hash(learning_policy) != policies.get(
        "learning_policy_hash"
    ):
        errors.append("LEARNING_POLICY_HASH_MISMATCH")
        learning_policy = {}
    if project_root is not None:
        catalog = _load_json(project_root / "config/research_parameter_catalog.json")
        eligibility_policy = _load_json(project_root / "config/research_eligibility_policy_v1.json")
        if content_hash(catalog) != policies.get("parameter_catalog_hash"):
            errors.append("PARAMETER_CATALOG_HASH_MISMATCH")
        if content_hash(eligibility_policy) != policies.get("eligibility_policy_hash"):
            errors.append("ELIGIBILITY_POLICY_HASH_MISMATCH")
    else:
        catalog = load_parameter_catalog()
    contrasts = recompute_contrasts(eligible_rows, catalog, learning_policy) if learning_policy else []
    supplied_learning = payload.get("learning_projection")
    supplied_contrasts = (
        supplied_learning.get("matched_contrasts") if isinstance(supplied_learning, dict) else None
    )
    if contrasts != supplied_contrasts:
        errors.append("MATCHED_CONTRAST_MISMATCH")
    supplied_eligibility = payload.get("eligibility_projection")
    eligibility_semantic_input = {
        "policy_hash": policies.get("eligibility_policy_hash"),
        "decisions": [
            {
                "observation_id": row.get("observation_id"),
                "status": (row.get("eligibility") or {}).get("status"),
                "evidence_weight": (row.get("eligibility") or {}).get("evidence_weight"),
                "reason_codes": (row.get("eligibility") or {}).get("reason_codes"),
            }
            for row in observations
            if isinstance(row, dict)
        ],
    }
    if not isinstance(supplied_eligibility, dict) or supplied_eligibility.get(
        "replay_semantic_hash"
    ) != content_hash(eligibility_semantic_input):
        errors.append("ELIGIBILITY_SEMANTIC_HASH_MISMATCH")
    scope_counts: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in contrasts:
        key = (row["parameter"], row["topic_family_id"], row["regime_id"])
        target = scope_counts.setdefault(key, {"contrasts": 0, "lineages": set()})
        target["contrasts"] += 1
        target["lineages"].add(row["lineage_id"])
    recomputed_scopes = [
        {
            "parameter": key[0],
            "topic_family_id": key[1],
            "regime_id": key[2],
            "matched_contrast_count": value["contrasts"],
            "distinct_lineage_count": len(value["lineages"]),
        }
        for key, value in sorted(scope_counts.items())
    ]
    learning_semantic_input = {
        "policy_hash": policies.get("learning_policy_hash"),
        "catalog_hash": policies.get("parameter_catalog_hash"),
        "eligible_evidence_unit_ids": sorted(row["evidence_unit_id"] for row in eligible_rows),
        "matched_contrasts": contrasts,
        "scope_evidence": recomputed_scopes,
    }
    if not isinstance(supplied_learning, dict) or supplied_learning.get(
        "replay_semantic_hash"
    ) != content_hash(learning_semantic_input):
        errors.append("LEARNING_SEMANTIC_HASH_MISMATCH")
    if isinstance(supplied_learning, dict) and supplied_learning.get("scope_evidence") != recomputed_scopes:
        errors.append("SCOPE_EVIDENCE_MISMATCH")
    expected_counts = {
        "cycles": len(cycles),
        "execution_units": len(observations),
        "observations": len(observations),
        "adaptive_eligible": recomputed_eligibility["ADAPTIVE_ELIGIBLE"],
        "distinct_lineages": len({row.get("lineage_id") for row in observations}),
        "matched_contrasts": len(contrasts),
    }
    if payload.get("counts") != expected_counts:
        errors.append("COUNT_MISMATCH")
    report = {
        "schema_version": VERIFICATION_SCHEMA,
        "status": "PASS" if not errors else "FAIL",
        "bundle_id": payload.get("bundle_id"),
        "errors": sorted(set(errors)),
        "recomputed_counts": expected_counts,
    }
    report["verification_hash"] = content_hash(report)
    return report
