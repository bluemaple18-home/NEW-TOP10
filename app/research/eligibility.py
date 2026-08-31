"""Research Ledger eligibility projection；只決定資料能否學，不做參數學習。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

from app.research.contracts import CANONICALIZATION_VERSION, content_hash
from app.research.observation_ingest import DEFAULT_LEDGER_PATH, input_corpus_hash, ledger_snapshot
from app.research.parameter_catalog import parameter_catalog_hash
from app.research.receipt_store import write_immutable_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = PROJECT_ROOT / "config/research_eligibility_policy_v1.json"
DEFAULT_ACTIVATION_EXCLUSIONS = (
    PROJECT_ROOT / "config/research_spine_activation_exclusions_v1.json"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts/autonomous_research/projections/eligibility"


DDL = """
CREATE TABLE IF NOT EXISTS eligibility_projection_runs (
 projection_id VARCHAR PRIMARY KEY, input_corpus_hash VARCHAR NOT NULL,
 ledger_snapshot_hash VARCHAR NOT NULL, policy_version VARCHAR NOT NULL,
 policy_hash VARCHAR NOT NULL, catalog_hash VARCHAR NOT NULL, status VARCHAR NOT NULL,
 output_artifact_path VARCHAR NOT NULL, canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS eligibility_decisions (
 projection_id VARCHAR NOT NULL, subject_type VARCHAR NOT NULL, subject_id VARCHAR NOT NULL,
 eligibility_status VARCHAR NOT NULL, evidence_weight BIGINT NOT NULL,
 decision_input_hash VARCHAR NOT NULL,
 PRIMARY KEY (projection_id, subject_type, subject_id)
);
CREATE TABLE IF NOT EXISTS eligibility_reason_codes (
 projection_id VARCHAR NOT NULL, subject_type VARCHAR NOT NULL, subject_id VARCHAR NOT NULL,
 reason_code VARCHAR NOT NULL,
 PRIMARY KEY (projection_id, subject_type, subject_id, reason_code)
);
"""


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "policy_version", "allowed_research_stages",
        "required_identity_match_status", "required_lineage_resolution_status",
        "required_sealed_usage_status", "forbidden_regime_ids",
        "legacy_adaptive_eligible_allowed",
    }
    if set(policy) != required or policy["schema_version"] != "research-eligibility-policy.v1":
        raise ValueError("INVALID_ELIGIBILITY_POLICY")
    if policy["legacy_adaptive_eligible_allowed"] is not False:
        raise ValueError("LEGACY_ELIGIBILITY_MUST_FAIL_CLOSED")
    if policy["required_identity_match_status"] != "EXACT":
        raise ValueError("ELIGIBILITY_IDENTITY_MUST_BE_EXACT")
    if policy["required_lineage_resolution_status"] != "VALID":
        raise ValueError("ELIGIBILITY_LINEAGE_MUST_BE_VALID")
    if policy["required_sealed_usage_status"] != "PROVEN_NON_SEALED":
        raise ValueError("ELIGIBILITY_SEALED_STATUS_MUST_BE_PROVEN_NON_SEALED")
    stages = policy["allowed_research_stages"]
    if not isinstance(stages, list) or not stages or any(
        not isinstance(value, str) or value not in {"DEVELOPMENT_SCREEN", "COARSE_SCREEN"}
        for value in stages
    ):
        raise ValueError("ELIGIBILITY_ALLOWED_STAGES_INVALID")
    forbidden = policy["forbidden_regime_ids"]
    if not isinstance(forbidden, list) or not {"", "UNKNOWN", "UNSCOPED"}.issubset(forbidden):
        raise ValueError("ELIGIBILITY_FORBIDDEN_REGIMES_INCOMPLETE")
    return policy


def load_activation_exclusions(
    path: Path = DEFAULT_ACTIVATION_EXCLUSIONS,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {
        "schema_version", "policy_version", "activation_success_allowed",
        "immutable_source_action", "entries",
    }:
        raise ValueError("INVALID_ACTIVATION_EXCLUSIONS")
    if payload["schema_version"] != "research-spine-activation-exclusions.v1":
        raise ValueError("INVALID_ACTIVATION_EXCLUSIONS_SCHEMA")
    if payload["activation_success_allowed"] is not False:
        raise ValueError("QUARANTINED_SOURCE_CANNOT_COUNT_AS_ACTIVATION_SUCCESS")
    if payload["immutable_source_action"] != "PRESERVE":
        raise ValueError("QUARANTINED_SOURCE_MUST_REMAIN_IMMUTABLE")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("INVALID_ACTIVATION_EXCLUSION_ENTRIES")
    seen: set[str] = set()
    required = {
        "receipt_id", "run_id", "source_topic_id", "classification", "reason_codes",
    }
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("INVALID_ACTIVATION_EXCLUSION_ENTRY")
        receipt_id = entry.get("receipt_id")
        if (
            not isinstance(receipt_id, str)
            or not receipt_id.startswith("sha256:")
            or len(receipt_id) != 71
            or receipt_id in seen
        ):
            raise ValueError("INVALID_ACTIVATION_EXCLUSION_RECEIPT_ID")
        seen.add(receipt_id)
        if entry.get("classification") != "TEST_FIXTURE_NON_OBSERVATION_POLLUTION":
            raise ValueError("INVALID_ACTIVATION_EXCLUSION_CLASSIFICATION")
        if not isinstance(entry.get("reason_codes"), list) or not entry["reason_codes"]:
            raise ValueError("INVALID_ACTIVATION_EXCLUSION_REASONS")
    return payload


def _native_decisions(connection: duckdb.DuckDBPyConnection, policy: dict[str, Any]) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT o.observation_id, r.terminal_status, r.observation_status,
               r.identity_match_status, u.lineage_resolution_status, u.sealed_usage_status,
               t.research_stage, t.regime_scope_json, t.dataset_hash, t.ranking_source_hash,
               t.parameters_json, o.total_return, o.max_drawdown, o.win_rate,
               o.avg_trade_return, o.trade_count, o.score, o.robust_neighbor_pass_count,
               o.evidence_unit_id
        FROM observations o
        JOIN run_receipts r ON r.receipt_id=o.receipt_id
        JOIN execution_units u ON u.execution_unit_id=o.execution_unit_id
        JOIN trial_specs t ON t.trial_spec_id=o.executed_trial_spec_id
        ORDER BY o.observation_id
        """
    ).fetchall()
    columns = [item[0] for item in connection.description]
    evidence_counts = Counter(row[-1] for row in rows)
    decisions = []
    for values in rows:
        row = dict(zip(columns, values))
        reasons: list[str] = []
        status = "ADAPTIVE_ELIGIBLE"
        if row["sealed_usage_status"] == "SEALED":
            status, reasons = "SEALED_VALIDATION_ONLY", ["SEALED_EVIDENCE_EXCLUDED"]
        else:
            checks = {
                "TERMINAL_EXECUTION_NOT_SUCCESSFUL": row["terminal_status"] != "SUCCEEDED",
                "EXECUTION_FACTS_NOT_OBSERVED": row["observation_status"] != "OBSERVED",
                "REQUESTED_EXECUTED_IDENTITY_NOT_EXACT": row["identity_match_status"] != policy["required_identity_match_status"],
                "INVALID_LINEAGE": row["lineage_resolution_status"] != policy["required_lineage_resolution_status"],
                "NON_SEALED_STATUS_NOT_PROVEN": row["sealed_usage_status"] != policy["required_sealed_usage_status"],
                "RESEARCH_STAGE_NOT_ALLOWED": row["research_stage"] not in policy["allowed_research_stages"],
            }
            regime = json.loads(row["regime_scope_json"])
            regime_id = str(regime.get("regime_id") or "")
            if not regime_id and isinstance(regime.get("base_regime"), str) and isinstance(
                regime.get("family_tags"), list
            ):
                regime_id = (
                    f"{regime['base_regime']}|"
                    f"{'+'.join(sorted(str(tag) for tag in regime['family_tags']))}"
                )
            checks["REGIME_IDENTITY_INVALID"] = regime_id in policy["forbidden_regime_ids"]
            parameters = json.loads(row["parameters_json"])
            checks["PARAMETER_IDENTITY_INCOMPLETE"] = (
                parameters.get("horizon") is None
                or any(
                    key not in parameters
                    for key in ("stop_loss_pct", "take_profit_pct", "max_group_exposure")
                )
            )
            checks["COVERAGE_ONLY_DIMENSION_EXECUTED"] = any(
                parameters.get(key) is not None for key in ("regime_gate", "risk_guard", "entry_filter")
            )
            checks["RESULT_METRICS_INCOMPLETE"] = any(
                row[key] is None for key in (
                    "total_return", "max_drawdown", "win_rate", "avg_trade_return",
                    "trade_count", "score", "robust_neighbor_pass_count",
                )
            )
            checks["DUPLICATE_SEMANTIC_EVIDENCE"] = evidence_counts[row["evidence_unit_id"]] != 1
            reasons = [reason for reason, failed in checks.items() if failed]
            if reasons:
                status = "INVALID_LINEAGE"
        decisions.append({
            "subject_type": "OBSERVATION", "subject_id": row["observation_id"],
            "eligibility_status": status, "evidence_weight": int(status == "ADAPTIVE_ELIGIBLE"),
            "reason_codes": reasons or ["ALL_ELIGIBILITY_GATES_PASSED"],
            "decision_input_hash": content_hash(row),
        })
    return decisions


def _non_observation_decisions(
    connection: duckdb.DuckDBPyConnection,
    exclusion_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    exclusions = {
        entry["receipt_id"]: entry for entry in exclusion_policy["entries"]
    }
    decisions: list[dict[str, Any]] = []
    for receipt_id, run_id, terminal, observation, identity in connection.execute(
        "SELECT receipt_id,run_id,terminal_status,observation_status,identity_match_status FROM run_receipts "
        "WHERE receipt_id NOT IN (SELECT DISTINCT receipt_id FROM observations) ORDER BY receipt_id"
    ).fetchall():
        reasons = ["NO_RESULT_OBSERVATION"]
        if terminal != "SUCCEEDED":
            reasons.append("EXECUTION_NOT_SUCCESSFUL")
        if observation == "UNKNOWN":
            reasons.append("EXECUTION_FACTS_UNKNOWN")
        exclusion = exclusions.get(receipt_id)
        if exclusion is not None:
            if exclusion["run_id"] != run_id:
                raise ValueError("ACTIVATION_EXCLUSION_RUN_ID_MISMATCH")
            reasons.extend(
                ["ACTIVATION_EVIDENCE_QUARANTINED", *exclusion["reason_codes"]]
            )
        decisions.append({
            "subject_type": "RUN_RECEIPT", "subject_id": receipt_id,
            "eligibility_status": "INVALID_LINEAGE", "evidence_weight": 0,
            "reason_codes": sorted(set(reasons)),
            "decision_input_hash": content_hash({
                "terminal": terminal, "observation": observation, "identity": identity,
                "activation_exclusion_policy_version": exclusion_policy["policy_version"],
                "activation_exclusion": exclusion,
            }),
        })
    return decisions


_IDENTITY_FIELDS = (
    "projection_schema_version", "input_corpus_hash", "ledger_snapshot_hash",
    "policy_version", "policy_hash", "parameter_catalog_hash",
    "canonicalization_version", "activation_exclusion_policy_version",
    "activation_exclusion_policy_hash",
)


def _validator(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version", "projection_id", *_IDENTITY_FIELDS, "status", "counts",
        "decisions", "legacy_decisions_materialized_in_ledger", "activation_exclusions",
    }
    if set(payload) != required:
        errors.append("invalid keys")
    if payload.get("schema_version") != "research-eligibility-projection.v1":
        errors.append("invalid schema")
    identity = {key: payload.get(key) for key in _IDENTITY_FIELDS}
    if payload.get("projection_id") != content_hash(identity):
        errors.append("invalid projection identity")
    decisions = payload.get("decisions")
    counts = payload.get("counts")
    legacy_count = payload.get("legacy_decisions_materialized_in_ledger")
    if (
        not isinstance(decisions, list)
        or not isinstance(counts, dict)
        or isinstance(legacy_count, bool)
        or not isinstance(legacy_count, int)
        or legacy_count < 0
    ):
        errors.append("invalid decisions or counts")
        return errors
    expected_decision_keys = {
        "subject_type", "subject_id", "eligibility_status", "evidence_weight",
        "reason_codes", "decision_input_hash",
    }
    valid_shapes = all(
        isinstance(item, dict)
        and set(item) == expected_decision_keys
        and all(isinstance(item[key], str) and item[key] for key in ("subject_type", "subject_id"))
        and isinstance(item["eligibility_status"], str)
        and item["evidence_weight"] == int(item["eligibility_status"] == "ADAPTIVE_ELIGIBLE")
        and isinstance(item["reason_codes"], list) and bool(item["reason_codes"])
        and all(isinstance(reason, str) and reason for reason in item["reason_codes"])
        and isinstance(item["decision_input_hash"], str)
        and item["decision_input_hash"].startswith("sha256:")
        for item in decisions
    )
    identities = [(item["subject_type"], item["subject_id"]) for item in decisions] if valid_shapes else []
    if not valid_shapes or len(identities) != len(set(identities)):
        errors.append("invalid or duplicate decisions")
    native_counts = Counter(item["eligibility_status"] for item in decisions) if valid_shapes else Counter()
    valid_counts = all(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
        for value in counts.values()
    )
    if (
        not valid_counts
        or sum(counts.values()) != len(decisions) + legacy_count
        or any(counts.get(status, 0) < count for status, count in native_counts.items())
    ):
        errors.append("invalid counts")
    expected_status = "OK" if counts.get("ADAPTIVE_ELIGIBLE", 0) else "NO_ELIGIBLE_OBSERVATIONS"
    if payload.get("status") != expected_status:
        errors.append("status/count mismatch")
    exclusions = payload.get("activation_exclusions")
    exclusion_keys = {
        "policy_version", "policy_hash", "immutable_source_action",
        "configured_receipt_count", "matched_receipt_count", "matched_receipt_ids",
        "activation_success_count",
    }
    if not isinstance(exclusions, dict) or set(exclusions) != exclusion_keys:
        errors.append("invalid activation exclusions")
    else:
        if exclusions["policy_version"] != payload.get("activation_exclusion_policy_version"):
            errors.append("activation exclusion policy version mismatch")
        if exclusions["policy_hash"] != payload.get("activation_exclusion_policy_hash"):
            errors.append("activation exclusion policy hash mismatch")
        matched_ids = exclusions.get("matched_receipt_ids")
        if not isinstance(matched_ids, list) or exclusions.get("matched_receipt_count") != len(matched_ids):
            errors.append("activation exclusion count mismatch")
        if exclusions.get("activation_success_count") != 0:
            errors.append("activation exclusion success must remain zero")
    return errors


def _native_db_rows(
    projection_id: str,
    decisions: list[dict[str, Any]],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    decision_rows = [
        (
            projection_id, decision["subject_type"], decision["subject_id"],
            decision["eligibility_status"], decision["evidence_weight"],
            decision["decision_input_hash"],
        )
        for decision in decisions
    ]
    reason_rows = [
        (projection_id, decision["subject_type"], decision["subject_id"], reason)
        for decision in decisions
        for reason in decision["reason_codes"]
    ]
    return sorted(decision_rows), sorted(reason_rows)


def _legacy_db_matches(connection: duckdb.DuckDBPyConnection, projection_id: str) -> bool:
    decision_delta = connection.execute(
        """SELECT count(*) FROM (
             SELECT migration_record_id,
                    CASE WHEN preliminary_classification IN (
                      'LEGACY_DIAGNOSTIC_ONLY','SEALED_VALIDATION_ONLY',
                      'TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE','UNSUPPORTED_NOT_AN_OBSERVATION',
                      'INVALID_LINEAGE') THEN preliminary_classification ELSE 'INVALID_LINEAGE' END status,
                    0 evidence_weight,mapped_payload_hash FROM migrated_records
             EXCEPT
             SELECT subject_id,eligibility_status,evidence_weight,decision_input_hash
             FROM eligibility_decisions WHERE projection_id=? AND subject_type='MIGRATED_RECORD'
             UNION ALL
             SELECT subject_id,eligibility_status,evidence_weight,decision_input_hash
             FROM eligibility_decisions WHERE projection_id=? AND subject_type='MIGRATED_RECORD'
             EXCEPT
             SELECT migration_record_id,
                    CASE WHEN preliminary_classification IN (
                      'LEGACY_DIAGNOSTIC_ONLY','SEALED_VALIDATION_ONLY',
                      'TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE','UNSUPPORTED_NOT_AN_OBSERVATION',
                      'INVALID_LINEAGE') THEN preliminary_classification ELSE 'INVALID_LINEAGE' END,
                    0,mapped_payload_hash FROM migrated_records
           )""",
        [projection_id, projection_id],
    ).fetchone()[0]
    reason_delta = connection.execute(
        """SELECT count(*) FROM (
             SELECT migration_record_id,'LEGACY_SOURCE_NOT_ELIGIBLE' FROM migrated_records
             EXCEPT
             SELECT subject_id,reason_code FROM eligibility_reason_codes
             WHERE projection_id=? AND subject_type='MIGRATED_RECORD'
               AND reason_code='LEGACY_SOURCE_NOT_ELIGIBLE'
             UNION ALL
             SELECT subject_id,reason_code FROM eligibility_reason_codes
             WHERE projection_id=? AND subject_type='MIGRATED_RECORD'
             EXCEPT SELECT migration_record_id,'LEGACY_SOURCE_NOT_ELIGIBLE' FROM migrated_records
           )""",
        [projection_id, projection_id],
    ).fetchone()[0]
    return decision_delta == reason_delta == 0


def build_projection(
    *, ledger_path: Path = DEFAULT_LEDGER_PATH, policy_path: Path = DEFAULT_POLICY,
    activation_exclusions_path: Path = DEFAULT_ACTIVATION_EXCLUSIONS,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    policy_hash = content_hash(policy)
    exclusion_policy = load_activation_exclusions(activation_exclusions_path)
    exclusion_policy_hash = content_hash(exclusion_policy)
    connection = duckdb.connect(str(ledger_path))
    try:
        connection.execute(DDL)
        corpus_hash = input_corpus_hash(connection)
        snapshot_hash = ledger_snapshot(connection)["snapshot_hash"]
        decisions = [
            *_native_decisions(connection, policy),
            *_non_observation_decisions(connection, exclusion_policy),
        ]
        decisions.sort(key=lambda item: (item["subject_type"], item["subject_id"]))
        identity = {
            "projection_schema_version": "research-eligibility-projection.v1",
            "input_corpus_hash": corpus_hash, "ledger_snapshot_hash": snapshot_hash,
            "policy_version": policy["policy_version"], "policy_hash": policy_hash,
            "parameter_catalog_hash": parameter_catalog_hash(),
            "canonicalization_version": CANONICALIZATION_VERSION,
            "activation_exclusion_policy_version": exclusion_policy["policy_version"],
            "activation_exclusion_policy_hash": exclusion_policy_hash,
        }
        projection_id = content_hash(identity)
        legacy_counts = dict(connection.execute(
            "SELECT preliminary_classification,count(*) FROM migrated_records GROUP BY 1"
        ).fetchall())
        counts = Counter(item["eligibility_status"] for item in decisions)
        counts.update(legacy_counts)
        excluded_ids = {entry["receipt_id"] for entry in exclusion_policy["entries"]}
        materialized_receipt_ids = {
            item["subject_id"]
            for item in decisions
            if item["subject_type"] == "RUN_RECEIPT"
        }
        matched_exclusions = sorted(excluded_ids & materialized_receipt_ids)
        payload = {
            "schema_version": "research-eligibility-projection.v1",
            "projection_id": projection_id, **identity,
            "status": "OK" if counts["ADAPTIVE_ELIGIBLE"] else "NO_ELIGIBLE_OBSERVATIONS",
            "counts": dict(sorted(counts.items())), "decisions": decisions,
            "legacy_decisions_materialized_in_ledger": sum(legacy_counts.values()),
            "activation_exclusions": {
                "policy_version": exclusion_policy["policy_version"],
                "policy_hash": exclusion_policy_hash,
                "immutable_source_action": exclusion_policy["immutable_source_action"],
                "configured_receipt_count": len(excluded_ids),
                "matched_receipt_count": len(matched_exclusions),
                "matched_receipt_ids": matched_exclusions,
                "activation_success_count": 0,
            },
        }
        target = output_root / f"{projection_id[7:]}.json"
        if target.is_file():
            existing_payload = json.loads(target.read_text(encoding="utf-8"))
            if existing_payload != payload:
                raise ValueError("ELIGIBILITY_PROJECTION_COLLISION")
        result = write_immutable_json(target, payload, validator=_validator)
        canonical_hash = content_hash(payload)
        expected_decisions, expected_reasons = _native_db_rows(projection_id, decisions)
        run_semantics = (
            projection_id, corpus_hash, snapshot_hash, policy["policy_version"], policy_hash,
            parameter_catalog_hash(), payload["status"], canonical_hash,
        )
        connection.execute("BEGIN TRANSACTION")
        try:
            existing_runs = connection.execute(
                "SELECT projection_id,input_corpus_hash,ledger_snapshot_hash,policy_version,"
                "policy_hash,catalog_hash,status,canonical_payload_hash "
                "FROM eligibility_projection_runs WHERE projection_id=?",
                [projection_id],
            ).fetchall()
            existing_decisions = sorted(connection.execute(
                "SELECT * FROM eligibility_decisions WHERE projection_id=? "
                "AND subject_type!='MIGRATED_RECORD'",
                [projection_id],
            ).fetchall())
            existing_reasons = sorted(connection.execute(
                "SELECT * FROM eligibility_reason_codes WHERE projection_id=? "
                "AND subject_type!='MIGRATED_RECORD'",
                [projection_id],
            ).fetchall())
            if existing_runs:
                if (
                    existing_runs != [run_semantics]
                    or existing_decisions != expected_decisions
                    or existing_reasons != expected_reasons
                    or not _legacy_db_matches(connection, projection_id)
                ):
                    raise ValueError("ELIGIBILITY_DB_PROJECTION_COLLISION")
            else:
                if existing_decisions or existing_reasons:
                    raise ValueError("ELIGIBILITY_DB_PROJECTION_COLLISION")
                connection.execute(
                    "INSERT INTO eligibility_projection_runs VALUES (?,?,?,?,?,?,?,?,?)",
                    [*run_semantics[:-1], str(result.path), run_semantics[-1]],
                )
                if expected_decisions:
                    connection.executemany(
                        "INSERT INTO eligibility_decisions VALUES (?,?,?,?,?,?)",
                        expected_decisions,
                    )
                if expected_reasons:
                    connection.executemany(
                        "INSERT INTO eligibility_reason_codes VALUES (?,?,?,?)",
                        expected_reasons,
                    )
                # 大型legacy分類維持set-based projection，避免逐筆materialize。
                connection.execute(
                    """INSERT INTO eligibility_decisions
                       SELECT ?, 'MIGRATED_RECORD', migration_record_id,
                              CASE WHEN preliminary_classification IN (
                                'LEGACY_DIAGNOSTIC_ONLY','SEALED_VALIDATION_ONLY',
                                'TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE','UNSUPPORTED_NOT_AN_OBSERVATION',
                                'INVALID_LINEAGE') THEN preliminary_classification ELSE 'INVALID_LINEAGE' END,
                              0, mapped_payload_hash FROM migrated_records""",
                    [projection_id],
                )
                connection.execute(
                    """INSERT INTO eligibility_reason_codes
                       SELECT ?, 'MIGRATED_RECORD', migration_record_id,
                              'LEGACY_SOURCE_NOT_ELIGIBLE' FROM migrated_records""",
                    [projection_id],
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        return payload
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument(
        "--activation-exclusions",
        type=Path,
        default=DEFAULT_ACTIVATION_EXCLUSIONS,
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = build_projection(
        ledger_path=args.ledger,
        policy_path=args.policy,
        activation_exclusions_path=args.activation_exclusions,
        output_root=args.output_root,
    )
    print(json.dumps({key: payload[key] for key in ("projection_id", "status", "counts")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
