"""將 immutable Research Spine corpus 投影成可刪除重建的 DuckDB ledger。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

import duckdb

from app.research.contracts import (
    content_hash,
    validate_attempt_started,
    validate_observation_identity,
    validate_research_intent,
    validate_run_receipt,
    validate_trial_spec,
    validate_migrated_record,
    validate_migration_manifest_v2,
    validate_migration_quality_report,
    validate_legacy_mapping_authority,
)
from app.research.legacy_migration import PARSER_VERSION as CURRENT_LEGACY_PARSER_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_ROOT = PROJECT_ROOT / "artifacts" / "autonomous_research" / "research_spine"
DEFAULT_LEDGER_PATH = PROJECT_ROOT / "data" / "research" / "research_ledger.duckdb"
SCHEMA_VERSION = "research-ledger.v1"
OBSERVATION_IDENTITY_POLICY = "executed-trial-lineage-result-unit.v1"
METRIC_POLICY_VERSION = "strategy-matrix-metrics.v1"
ATTEMPT_INCLUSION_POLICY = "terminal-receipts-all-statuses.v1"


DDL = """
CREATE TABLE IF NOT EXISTS ledger_metadata (
    key VARCHAR PRIMARY KEY,
    value VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_specs (
    trial_spec_id VARCHAR PRIMARY KEY,
    topic_id VARCHAR NOT NULL,
    topic_family_id VARCHAR NOT NULL,
    research_stage VARCHAR NOT NULL,
    regime_scope_json VARCHAR NOT NULL,
    dataset_hash VARCHAR NOT NULL,
    ranking_source_hash VARCHAR NOT NULL,
    parameters_json VARCHAR NOT NULL,
    execution_profile_json VARCHAR NOT NULL,
    parameter_catalog_hash VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_parameters (
    trial_spec_id VARCHAR NOT NULL,
    parameter_id VARCHAR NOT NULL,
    value_type VARCHAR NOT NULL,
    integer_value BIGINT,
    decimal_value DECIMAL(24, 12),
    categorical_value VARCHAR,
    PRIMARY KEY (trial_spec_id, parameter_id)
);
CREATE TABLE IF NOT EXISTS research_intents (
    intent_id VARCHAR PRIMARY KEY,
    requested_at VARCHAR NOT NULL,
    request_source VARCHAR NOT NULL,
    selection_reason_json VARCHAR NOT NULL,
    trial_spec_ids_json VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS run_attempts (
    run_id VARCHAR PRIMARY KEY,
    attempt_event_id VARCHAR UNIQUE NOT NULL,
    intent_id VARCHAR NOT NULL,
    started_at VARCHAR NOT NULL,
    executor_json VARCHAR NOT NULL,
    invocation_hash VARCHAR NOT NULL,
    trial_spec_ids_json VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS run_receipts (
    receipt_id VARCHAR PRIMARY KEY,
    run_id VARCHAR UNIQUE NOT NULL,
    intent_id VARCHAR NOT NULL,
    terminal_status VARCHAR NOT NULL,
    observation_status VARCHAR NOT NULL,
    identity_match_status VARCHAR NOT NULL,
    started_at VARCHAR NOT NULL,
    completed_at VARCHAR NOT NULL,
    receipt_payload_hash VARCHAR NOT NULL,
    receipt_corpus_path VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS run_artifacts (
    artifact_id VARCHAR NOT NULL,
    receipt_id VARCHAR NOT NULL,
    corpus_path VARCHAR NOT NULL,
    provenance_path VARCHAR NOT NULL,
    validation_status VARCHAR NOT NULL,
    PRIMARY KEY (artifact_id, receipt_id)
);
CREATE TABLE IF NOT EXISTS execution_units (
    execution_unit_id VARCHAR PRIMARY KEY,
    receipt_id VARCHAR NOT NULL,
    requested_trial_spec_id VARCHAR NOT NULL,
    executed_trial_spec_id VARCHAR NOT NULL,
    lineage_id VARCHAR NOT NULL,
    sealed_usage_status VARCHAR NOT NULL,
    lineage_resolution_status VARCHAR NOT NULL,
    episode_ids_json VARCHAR NOT NULL,
    artifact_refs_json VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS execution_unit_parameters (
    execution_unit_id VARCHAR NOT NULL,
    parameter_id VARCHAR NOT NULL,
    value_type VARCHAR NOT NULL,
    integer_value BIGINT,
    decimal_value DECIMAL(24, 12),
    categorical_value VARCHAR,
    PRIMARY KEY (execution_unit_id, parameter_id)
);
CREATE TABLE IF NOT EXISTS execution_unit_episodes (
    execution_unit_id VARCHAR NOT NULL,
    episode_id VARCHAR NOT NULL,
    PRIMARY KEY (execution_unit_id, episode_id)
);
CREATE TABLE IF NOT EXISTS observations (
    observation_id VARCHAR PRIMARY KEY,
    execution_unit_id VARCHAR NOT NULL,
    receipt_id VARCHAR NOT NULL,
    executed_trial_spec_id VARCHAR NOT NULL,
    lineage_id VARCHAR NOT NULL,
    result_unit_id VARCHAR NOT NULL,
    evidence_unit_id VARCHAR NOT NULL,
    scenario_id VARCHAR,
    total_return DOUBLE,
    max_drawdown DOUBLE,
    win_rate DOUBLE,
    avg_trade_return DOUBLE,
    trade_count BIGINT,
    score DOUBLE,
    p_value DOUBLE,
    robust_neighbor_pass_count BIGINT,
    result_payload_hash VARCHAR NOT NULL,
    identity_policy_version VARCHAR NOT NULL,
    metric_policy_version VARCHAR NOT NULL,
    attempt_inclusion_policy_version VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS observation_provenance (
    observation_id VARCHAR NOT NULL,
    artifact_id VARCHAR NOT NULL,
    receipt_id VARCHAR NOT NULL,
    source_corpus_path VARCHAR NOT NULL,
    PRIMARY KEY (observation_id, artifact_id, receipt_id)
);
CREATE TABLE IF NOT EXISTS ingestion_conflicts (
    conflict_id VARCHAR PRIMARY KEY,
    entity_type VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    existing_hash VARCHAR NOT NULL,
    incoming_hash VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS ingestion_rejections (
    rejection_id VARCHAR PRIMARY KEY,
    source_type VARCHAR NOT NULL,
    source_identity VARCHAR NOT NULL,
    source_content_hash VARCHAR NOT NULL,
    reason_codes_json VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS ingestion_files (
    source_type VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    corpus_path VARCHAR NOT NULL,
    PRIMARY KEY (source_type, source_id)
);
CREATE TABLE IF NOT EXISTS projection_runs (
    projection_id VARCHAR PRIMARY KEY,
    projection_type VARCHAR NOT NULL,
    input_corpus_hash VARCHAR NOT NULL,
    policy_versions_json VARCHAR NOT NULL,
    output_artifact_hash VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS migration_manifests (
    migration_id VARCHAR PRIMARY KEY,
    parser_version VARCHAR NOT NULL,
    semantic_identity_policy_version VARCHAR NOT NULL,
    eligibility_preclassification_policy_version VARCHAR NOT NULL,
    source_authority_order_version VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS migration_sources (
    migration_id VARCHAR NOT NULL,
    source_artifact_id VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    record_mapping_hash VARCHAR NOT NULL,
    records_seen BIGINT NOT NULL,
    records_mapped BIGINT NOT NULL,
    records_excluded BIGINT NOT NULL,
    PRIMARY KEY (migration_id, source_artifact_id)
);
CREATE TABLE IF NOT EXISTS migrated_records (
    migration_record_id VARCHAR PRIMARY KEY,
    first_seen_migration_id VARCHAR NOT NULL,
    source_artifact_id VARCHAR NOT NULL,
    record_locator VARCHAR NOT NULL,
    record_kind VARCHAR NOT NULL,
    preliminary_classification VARCHAR NOT NULL,
    semantic_evidence_id VARCHAR,
    metrics_hash VARCHAR,
    mapped_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS migration_manifest_records (
    migration_id VARCHAR NOT NULL,
    migration_record_id VARCHAR NOT NULL,
    source_artifact_id VARCHAR NOT NULL,
    PRIMARY KEY (migration_id, migration_record_id)
);
CREATE TABLE IF NOT EXISTS migrated_record_reasons (
    migration_record_id VARCHAR NOT NULL,
    reason_code VARCHAR NOT NULL,
    PRIMARY KEY (migration_record_id, reason_code)
);
CREATE TABLE IF NOT EXISTS migration_quality_reports (
    quality_report_id VARCHAR PRIMARY KEY,
    migration_id VARCHAR NOT NULL,
    report_hash VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS migration_artifact_dispositions (
    artifact_disposition_id VARCHAR PRIMARY KEY,
    migration_id VARCHAR NOT NULL,
    source_artifact_id VARCHAR NOT NULL,
    migration_disposition VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS migration_record_dispositions (
    migration_record_id VARCHAR PRIMARY KEY,
    migration_disposition VARCHAR NOT NULL,
    confidence VARCHAR NOT NULL,
    disposition_policy_version VARCHAR NOT NULL,
    inference_policy_version VARCHAR NOT NULL,
    mapping_authority_id VARCHAR,
    combo_mapping_status VARCHAR NOT NULL,
    combo_cardinality VARCHAR NOT NULL,
    canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS migration_combo_edges (
    migration_record_id VARCHAR NOT NULL,
    combo_id VARCHAR NOT NULL,
    canonical_trial_spec_id VARCHAR NOT NULL,
    evidence_refs_json VARCHAR NOT NULL,
    reason_codes_json VARCHAR NOT NULL,
    PRIMARY KEY (migration_record_id, combo_id, canonical_trial_spec_id)
);
CREATE TABLE IF NOT EXISTS legacy_semantic_evidence (
    semantic_evidence_id VARCHAR PRIMARY KEY,
    metrics_hash VARCHAR NOT NULL,
    conflict_status VARCHAR NOT NULL,
    evidence_weight BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS legacy_semantic_provenance (
    semantic_evidence_id VARCHAR NOT NULL,
    migration_record_id VARCHAR NOT NULL,
    source_artifact_id VARCHAR NOT NULL,
    PRIMARY KEY (semantic_evidence_id, migration_record_id)
);
"""


@dataclass(frozen=True)
class IngestResult:
    receipts_seen: int
    receipts_inserted: int
    observations_inserted: int
    conflicts: int
    rejections: int
    snapshot_hash: str


class InvalidSourceSchema(ValueError):
    def __init__(self, source_identity: str, source_hash: str, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.source_identity = source_identity
        self.source_hash = source_hash
        self.errors = errors


class CorpusIntegrityError(ValueError):
    pass


def _expected_identity(entity: str, path: Path) -> str:
    if entity == "trial_spec":
        return path.stem
    if entity == "attempt":
        return path.name.removesuffix(".started.json")
    return path.stem


def _source_state(
    connection: duckdb.DuckDBPyConnection,
    *,
    source_type: str,
    source_id: str,
    path: Path,
) -> str:
    digest = _file_hash(path)
    existing = connection.execute(
        "SELECT content_hash FROM ingestion_files WHERE source_type = ? AND source_id = ?",
        [source_type, source_id],
    ).fetchone()
    if existing is None:
        connection.execute(
            "INSERT INTO ingestion_files VALUES (?, ?, ?, ?)",
            [source_type, source_id, digest, path.name],
        )
        return "NEW"
    if existing[0] == digest:
        return "UNCHANGED"
    conflict = {
        "entity_type": source_type,
        "entity_id": source_id,
        "existing_hash": existing[0],
        "incoming_hash": digest,
        "source_path": path.name,
    }
    connection.execute(
        "INSERT OR IGNORE INTO ingestion_conflicts VALUES (?, ?, ?, ?, ?, ?)",
        [content_hash(conflict), *conflict.values()],
    )
    return "MUTATED"


def _assert_path_identity(entity: str, path: Path, payload: dict[str, Any]) -> None:
    fields = {
        "trial_spec": "trial_spec_id",
        "intent": "intent_id",
        "attempt": "run_id",
        "receipt": "run_id",
    }
    expected = _expected_identity(entity, path)
    actual = str(payload.get(fields[entity]) or "")
    comparable = actual.removeprefix("sha256:") if entity == "trial_spec" else actual
    if expected != comparable:
        raise InvalidSourceSchema(expected, _file_hash(path), ["CORPUS_PATH_IDENTITY_MISMATCH"])


def _record_rejection(
    connection: duckdb.DuckDBPyConnection,
    *,
    source_type: str,
    source_identity: str,
    source_hash: str,
    reasons: list[str],
) -> None:
    rejection = {
        "source_type": source_type,
        "source_identity": source_identity,
        "source_content_hash": source_hash,
        "reason_codes": reasons,
    }
    connection.execute(
        "INSERT OR IGNORE INTO ingestion_rejections VALUES (?, ?, ?, ?, ?)",
        [
            content_hash(rejection), source_type, source_identity, source_hash,
            _json(reasons),
        ],
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root 必須是 object：{path}")
    return payload


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _verify_cas(corpus_root: Path, corpus_path_value: str, artifact_id: str) -> Path:
    path = corpus_root / corpus_path_value
    expected = Path("source_corpus") / "sha256" / artifact_id.removeprefix("sha256:")
    if Path(corpus_path_value) != expected or not path.is_file() or _file_hash(path) != artifact_id:
        raise CorpusIntegrityError(f"CAS artifact mismatch: {artifact_id}")
    return path


def input_corpus_hash(connection: duckdb.DuckDBPyConnection) -> str:
    sources = {
        "trial_specs": ("trial_spec_id", "canonical_payload_hash"),
        "research_intents": ("intent_id", "canonical_payload_hash"),
        "run_attempts": ("run_id", "canonical_payload_hash"),
        "run_receipts": ("receipt_id", "receipt_payload_hash"),
        "migration_manifests": ("migration_id", "canonical_payload_hash"),
    }
    entries: list[dict[str, str]] = []
    for table, columns in sources.items():
        for identity, digest in connection.execute(
            f"SELECT {columns[0]}, {columns[1]} FROM {table} ORDER BY {columns[0]}"
        ).fetchall():
            entries.append({"entity": table, "identity": identity, "content_hash": digest})
    return content_hash({"policy_version": "research-corpus-inventory.v1", "entries": entries})


def _migration_authority(corpus_root: Path, authority_id: str) -> dict[str, Any]:
    path = corpus_root / "migration" / "authorities" / f"{authority_id.removeprefix('sha256:')}.json"
    if not path.is_file():
        raise ValueError("MIGRATION_MAPPING_AUTHORITY_MISSING")
    payload = _load_json(path)
    errors = validate_legacy_mapping_authority(payload)
    if errors or payload.get("authority_id") != authority_id:
        raise ValueError("MIGRATION_MAPPING_AUTHORITY_INVALID")
    return payload


def _migration_trial_target(corpus_root: Path, trial_id: str) -> dict[str, Any]:
    path = corpus_root / "trial_specs" / f"{trial_id.removeprefix('sha256:')}.json"
    if not path.is_file():
        raise ValueError("MIGRATION_CANONICAL_TARGET_MISSING")
    payload = _load_json(path)
    errors = validate_trial_spec(payload)
    if errors or payload.get("trial_spec_id") != trial_id:
        raise ValueError("MIGRATION_CANONICAL_TARGET_INVALID")
    return payload


def _migration_receipts(corpus_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in _paths(corpus_root, "receipts"):
        try:
            payload = _load_json(path)
        except (ValueError, json.JSONDecodeError):
            continue
        errors = validate_run_receipt(payload)
        if errors or path.stem != str(payload.get("run_id") or ""):
            continue
        result[str(payload["receipt_id"])] = payload
    return result


def _validate_migration_record_authority(
    corpus_root: Path,
    record: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
) -> None:
    disposition = record["migration_disposition"]
    authority_id = record.get("mapping_authority_id")
    if authority_id is None:
        if disposition in {"MIGRATED_EXACT", "MIGRATED_INFERRED", "EXCLUDED_NON_RESEARCH"}:
            raise ValueError("MIGRATION_MAPPING_AUTHORITY_REQUIRED")
        if record["evidence_refs"] != [record["source"]["artifact_id"]]:
            raise ValueError("MIGRATION_EVIDENCE_REF_MISMATCH")
        return
    authority = _migration_authority(corpus_root, authority_id)
    expected_combo = str(record["legacy_identity"].get("combo_id") or "NOT_APPLICABLE")
    if (
        authority["source_artifact_id"] != record["source"]["artifact_id"]
        or authority["record_locator"] != record["source"]["record_locator"]
        or authority["legacy_combo_id"] != expected_combo
    ):
        raise ValueError("MIGRATION_MAPPING_AUTHORITY_BINDING_MISMATCH")
    mode = authority["mapping_mode"]
    if mode == "EXACT" and disposition != "MIGRATED_EXACT":
        unresolved_no_winner = (
            disposition == "LEGACY_UNRESOLVED"
            and len(authority["candidates"]) > 1
            and authority["multi_target_resolution"] != "ALL_TARGETS_PROVEN"
            and record["combo_mapping"]["mapping_status"] == "AMBIGUOUS_NO_WINNER"
        )
        if not unresolved_no_winner:
            raise ValueError("MIGRATION_MAPPING_AUTHORITY_DISPOSITION_MISMATCH")
    if mode == "INFERRED" and disposition not in {"MIGRATED_INFERRED", "LEGACY_UNRESOLVED"}:
        raise ValueError("MIGRATION_MAPPING_AUTHORITY_DISPOSITION_MISMATCH")
    if mode == "EXCLUDE_NON_RESEARCH" and disposition != "EXCLUDED_NON_RESEARCH":
        raise ValueError("MIGRATION_MAPPING_AUTHORITY_DISPOSITION_MISMATCH")
    expected_refs = sorted(set([authority_id, *authority["evidence_refs"]]))
    if record["evidence_refs"] != expected_refs:
        raise ValueError("MIGRATION_EVIDENCE_REF_MISMATCH")
    record_candidates = record["combo_mapping"]["candidates"]
    authority_candidates = authority["candidates"]
    if len(record_candidates) != len(authority_candidates):
        raise ValueError("MIGRATION_CANONICAL_TARGET_COUNT_MISMATCH")
    targets: dict[str, dict[str, Any]] = {}
    for record_edge, authority_edge in zip(record_candidates, authority_candidates, strict=True):
        trial_id = str(authority_edge["canonical_trial_spec_id"])
        target = _migration_trial_target(corpus_root, trial_id)
        targets[trial_id] = target
        expected_edge = {
            **authority_edge,
            "evidence_refs": sorted(set([authority_id, *authority_edge["evidence_refs"]])),
        }
        if record_edge != expected_edge:
            raise ValueError("MIGRATION_CANONICAL_TARGET_EDGE_MISMATCH")
        if target.get("parameters") != record.get("parameters"):
            raise ValueError("MIGRATION_CANONICAL_TARGET_PARAMETER_MISMATCH")
        topic_id = record["legacy_identity"].get("topic_id")
        if topic_id is not None and target.get("topic_id") != topic_id:
            raise ValueError("MIGRATION_CANONICAL_TARGET_TOPIC_MISMATCH")
    for receipt_id in authority["governing_receipt_ids"]:
        if receipt_id not in receipts:
            raise ValueError("MIGRATION_GOVERNING_RECEIPT_MISSING")
    if record["preliminary_classification"] == "SEALED_VALIDATION_ONLY":
        governed: set[str] = set()
        for receipt_id in authority["governing_receipt_ids"]:
            for unit in receipts[receipt_id].get("executed_units") or []:
                trial_id = unit.get("executed_trial_spec_id")
                if (
                    trial_id in targets
                    and targets[str(trial_id)].get("research_stage") == "SEALED_VALIDATION"
                    and unit.get("executed_research_stage") == "SEALED_VALIDATION"
                    and unit.get("sealed_usage_status") == "SEALED"
                ):
                    governed.add(str(trial_id))
        if governed != set(targets):
            raise ValueError("MIGRATION_SEALED_GOVERNANCE_MISMATCH")


def _ingest_migrations(connection: duckdb.DuckDBPyConnection, corpus_root: Path) -> None:
    canonical_receipts = _migration_receipts(corpus_root)
    manifest_paths = sorted((corpus_root / "migration" / "manifests").glob("*.json"))
    manifests = [(path, _load_json(path)) for path in manifest_paths]
    current_manifests = [
        (path, manifest)
        for path, manifest in manifests
        if manifest.get("parser_version") == CURRENT_LEGACY_PARSER_VERSION
    ]
    if manifests and not current_manifests:
        raise ValueError(
            "MIGRATION_CURRENT_MANIFEST_MISSING: "
            f"expected parser_version={CURRENT_LEGACY_PARSER_VERSION}"
        )
    for manifest_path, manifest in current_manifests:
        manifest_errors = validate_migration_manifest_v2(manifest)
        if manifest_errors:
            raise ValueError("invalid migration manifest: " + "; ".join(manifest_errors))
        migration_id = str(manifest.get("migration_id") or "")
        if manifest_path.stem != migration_id.removeprefix("sha256:"):
            raise ValueError("MIGRATION_MANIFEST_PATH_IDENTITY_MISMATCH")
        if content_hash(manifest, omit={"migration_id"}) != migration_id:
            raise ValueError("MIGRATION_MANIFEST_IDENTITY_MISMATCH")
        manifest_hash = content_hash(manifest)
        existing = connection.execute(
            "SELECT canonical_payload_hash FROM migration_manifests WHERE migration_id = ?",
            [migration_id],
        ).fetchone()
        if existing and existing[0] != manifest_hash:
            raise ValueError("MIGRATION_MANIFEST_COLLISION")
        quality_path = corpus_root / manifest["quality_report_path"]
        if (
            not quality_path.is_file()
            or _file_hash(quality_path) != manifest["quality_report_hash"]
        ):
            raise ValueError("MIGRATION_QUALITY_REPORT_HASH_MISMATCH")
        quality = _load_json(quality_path)
        quality_errors = validate_migration_quality_report(quality)
        if quality_errors:
            raise ValueError("invalid migration quality report: " + "; ".join(quality_errors))
        if quality.get("disposition_policy_version") != manifest.get("disposition_policy_version"):
            raise ValueError("MIGRATION_QUALITY_DISPOSITION_POLICY_MISMATCH")
        if quality.get("inference_policy_version") != manifest.get("inference_policy_version"):
            raise ValueError("MIGRATION_QUALITY_INFERENCE_POLICY_MISMATCH")
        staged_sources: list[tuple[Any, ...]] = []
        staged_records: list[dict[str, Any]] = []
        observed_dispositions: Counter[str] = Counter()
        observed_artifact_dispositions: Counter[str] = Counter()
        observed_totals: Counter[str] = Counter()
        observed_gaps: Counter[str] = Counter()
        for source in manifest.get("sources") or []:
            artifact_id = source["source_artifact_hash"]
            _verify_cas(corpus_root, source["corpus_artifact_path"], artifact_id)
            mapping_path = corpus_root / source["record_mapping_path"]
            if not mapping_path.is_file() or _file_hash(mapping_path) != source["record_mapping_hash"]:
                raise ValueError("MIGRATION_MAPPING_HASH_MISMATCH")
            records = [json.loads(line) for line in mapping_path.read_text().splitlines() if line]
            counts = source["record_counts"]
            if counts["seen"] != counts["mapped"] + counts["excluded"] or len(records) != counts["seen"]:
                raise ValueError("MIGRATION_RECORD_COUNT_MISMATCH")
            for record in records:
                record_errors = validate_migrated_record(record)
                if record_errors:
                    raise ValueError("invalid migrated record: " + "; ".join(record_errors))
                if record["source"]["artifact_id"] != artifact_id:
                    raise ValueError("MIGRATION_RECORD_SOURCE_MISMATCH")
                record_id = record.get("migration_record_id")
                expected = content_hash(
                    {
                        "policy_version": record["parser_version"],
                        "artifact_id": artifact_id,
                        "locator": record["source"]["record_locator"],
                        "record": {k: v for k, v in record.items() if k != "migration_record_id"},
                    }
                )
                if record_id != expected:
                    raise ValueError("MIGRATION_RECORD_IDENTITY_MISMATCH")
                _validate_migration_record_authority(
                    corpus_root, record, canonical_receipts
                )
                staged_records.append(record)
            observed_classifications = Counter(
                record["preliminary_classification"] for record in records
            )
            observed_reasons = Counter(reason for record in records for reason in record["reason_codes"])
            if dict(sorted(observed_classifications.items())) != source["classification_counts"]:
                raise ValueError("MIGRATION_CLASSIFICATION_COUNTS_MISMATCH")
            if dict(sorted(observed_reasons.items())) != source["reason_code_counts"]:
                raise ValueError("MIGRATION_REASON_COUNTS_MISMATCH")
            source_dispositions = Counter(record["migration_disposition"] for record in records)
            if dict(sorted(source_dispositions.items())) != source["disposition_counts"]:
                raise ValueError("MIGRATION_DISPOSITION_COUNTS_MISMATCH")
            artifact_record = source["artifact_disposition_record"]
            if artifact_record["artifact_disposition_id"] != content_hash(
                artifact_record, omit={"artifact_disposition_id"}
            ):
                raise ValueError("MIGRATION_ARTIFACT_DISPOSITION_IDENTITY_MISMATCH")
            observed_dispositions.update(source_dispositions)
            observed_artifact_dispositions[artifact_record["migration_disposition"]] += 1
            reconciliation = source["reconciliation"]
            expected_reconciliation = {
                "source_artifacts_seen": 1,
                "source_artifact_disposition_counts": {
                    artifact_record["migration_disposition"]: 1
                },
                "rows_seen": len(records),
                "legacy_run_rows": len(records) if source["source_type"].startswith("RUN_HISTORY") else 0,
                "legacy_observation_like_rows": sum(
                    record["record_kind"] == "PARAMETER_RESULT" for record in records
                ),
                "mapping_edges_emitted": sum(
                    len(record["combo_mapping"]["candidates"]) for record in records
                ),
                "new_migrated_records": sum(
                    record["migration_disposition"] != "EXCLUDED_NON_RESEARCH"
                    for record in records
                ),
                "excluded_disposition_records": source_dispositions["EXCLUDED_NON_RESEARCH"],
                "projected_observations": 0,
                "typed_gaps": {
                    "excluded": source_dispositions["EXCLUDED_NON_RESEARCH"],
                    "incomplete": source_dispositions["LEGACY_INCOMPLETE"],
                    "unresolved": source_dispositions["LEGACY_UNRESOLVED"],
                    "deduplicated": 0,
                    "one_to_many_expansion": sum(
                        max(len(record["combo_mapping"]["candidates"]) - 1, 0)
                        for record in records
                    ),
                    "not_observation": len(records),
                },
                "unexplained_delta": 0,
            }
            if reconciliation != expected_reconciliation:
                raise ValueError("MIGRATION_SOURCE_RECONCILIATION_MISMATCH")
            for field in (
                "source_artifacts_seen", "rows_seen", "legacy_run_rows",
                "legacy_observation_like_rows", "mapping_edges_emitted", "new_migrated_records",
                "excluded_disposition_records", "projected_observations", "unexplained_delta",
            ):
                observed_totals[field] += reconciliation[field]
            observed_gaps.update(reconciliation["typed_gaps"])
            staged_sources.append((
                migration_id, artifact_id, source["source_type"], source["record_mapping_hash"],
                counts["seen"], counts["mapped"], counts["excluded"],
            ))
        for field in (
            "source_artifacts_seen", "rows_seen", "legacy_run_rows",
            "legacy_observation_like_rows", "mapping_edges_emitted", "new_migrated_records",
            "excluded_disposition_records", "projected_observations", "unexplained_delta",
        ):
            observed_totals.setdefault(field, 0)
        for field in (
            "excluded", "incomplete", "unresolved", "deduplicated",
            "one_to_many_expansion", "not_observation",
        ):
            observed_gaps.setdefault(field, 0)
        expected_quality_totals = {
            **dict(observed_totals), "typed_gaps": dict(sorted(observed_gaps.items()))
        }
        if dict(sorted(observed_dispositions.items())) != quality["row_disposition_counts"]:
            raise ValueError("MIGRATION_QUALITY_ROW_DISPOSITIONS_MISMATCH")
        if dict(sorted(observed_artifact_dispositions.items())) != quality["source_artifact_disposition_counts"]:
            raise ValueError("MIGRATION_QUALITY_ARTIFACT_DISPOSITIONS_MISMATCH")
        if expected_quality_totals != quality["totals"]:
            raise ValueError("MIGRATION_QUALITY_TOTALS_MISMATCH")
        if not existing:
            connection.execute(
                "INSERT INTO migration_manifests VALUES (?, ?, ?, ?, ?, ?)",
                [
                    migration_id, manifest["parser_version"],
                    manifest["semantic_identity_policy_version"],
                    manifest["eligibility_preclassification_policy_version"],
                    manifest["source_authority_order_version"], manifest_hash,
                ],
            )
        for row in staged_sources:
            connection.execute(
                "INSERT OR IGNORE INTO migration_sources VALUES (?, ?, ?, ?, ?, ?, ?)", row
            )
        quality_hash = content_hash(quality)
        existing_quality = connection.execute(
            "SELECT canonical_payload_hash FROM migration_quality_reports WHERE quality_report_id = ?",
            [quality["quality_report_id"]],
        ).fetchone()
        if existing_quality and existing_quality[0] != quality_hash:
            raise ValueError("MIGRATION_QUALITY_REPORT_COLLISION")
        connection.execute(
            "INSERT OR IGNORE INTO migration_quality_reports VALUES (?, ?, ?, ?)",
            [quality["quality_report_id"], migration_id, manifest["quality_report_hash"], quality_hash],
        )
        for source in manifest.get("sources") or []:
            artifact = source["artifact_disposition_record"]
            artifact_hash = content_hash(artifact)
            existing_artifact = connection.execute(
                "SELECT canonical_payload_hash FROM migration_artifact_dispositions WHERE artifact_disposition_id = ?",
                [artifact["artifact_disposition_id"]],
            ).fetchone()
            if existing_artifact and existing_artifact[0] != artifact_hash:
                raise ValueError("MIGRATION_ARTIFACT_DISPOSITION_COLLISION")
            connection.execute(
                "INSERT OR IGNORE INTO migration_artifact_dispositions VALUES (?, ?, ?, ?, ?)",
                [artifact["artifact_disposition_id"], migration_id, artifact["source_artifact_id"],
                 artifact["migration_disposition"], artifact_hash],
            )
        for record in staged_records:
            record_id = record["migration_record_id"]
            record_hash = content_hash(record)
            existing_record = connection.execute(
                "SELECT mapped_payload_hash FROM migrated_records WHERE migration_record_id = ?",
                [record_id],
            ).fetchone()
            if existing_record and existing_record[0] != record_hash:
                raise ValueError("MIGRATION_RECORD_COLLISION")
            metrics_hash = content_hash(record["metrics"]) if record["semantic_evidence_id"] else None
            connection.execute(
                "INSERT OR IGNORE INTO migrated_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [record_id, migration_id, record["source"]["artifact_id"],
                 record["source"]["record_locator"], record["record_kind"],
                 record["preliminary_classification"], record["semantic_evidence_id"],
                 metrics_hash, record_hash],
            )
            connection.execute(
                "INSERT OR IGNORE INTO migration_manifest_records VALUES (?, ?, ?)",
                [migration_id, record_id, record["source"]["artifact_id"]],
            )
            for reason in record["reason_codes"]:
                connection.execute(
                    "INSERT OR IGNORE INTO migrated_record_reasons VALUES (?, ?)",
                    [record_id, reason],
                )
            combo = record["combo_mapping"]
            connection.execute(
                "INSERT OR IGNORE INTO migration_record_dispositions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [record_id, record["migration_disposition"], record["confidence"],
                 record["disposition_policy_version"], record["inference_policy_version"],
                 record["mapping_authority_id"],
                 combo["mapping_status"], combo["cardinality"], record_hash],
            )
            for edge in combo["candidates"]:
                connection.execute(
                    "INSERT OR IGNORE INTO migration_combo_edges VALUES (?, ?, ?, ?, ?)",
                    [record_id, edge["combo_id"], edge["canonical_trial_spec_id"],
                     _json(edge["evidence_refs"]), _json(edge["reason_codes"])],
                )
        # Semantic evidence由canonical record facts集合式重建；copy不加權，衝突weight=0。
        connection.execute("DELETE FROM legacy_semantic_evidence")
        connection.execute("DELETE FROM legacy_semantic_provenance")
        connection.execute(
            """INSERT INTO legacy_semantic_evidence
               SELECT semantic_evidence_id, min(metrics_hash),
                      CASE WHEN count(DISTINCT metrics_hash)>1 THEN 'CONFLICTED' ELSE 'CONSISTENT' END,
                      CASE WHEN count(DISTINCT metrics_hash)>1 THEN 0 ELSE 1 END
               FROM migrated_records WHERE semantic_evidence_id IS NOT NULL
               GROUP BY semantic_evidence_id"""
        )
        connection.execute(
            """INSERT INTO legacy_semantic_provenance
               SELECT semantic_evidence_id,migration_record_id,source_artifact_id
               FROM migrated_records WHERE semantic_evidence_id IS NOT NULL"""
        )
        expected_relations = sum(row[4] for row in staged_sources)
        actual_relations = connection.execute(
            "SELECT count(*) FROM migration_manifest_records WHERE migration_id = ?",
            [migration_id],
        ).fetchone()[0]
        if actual_relations != expected_relations:
            raise ValueError("MIGRATION_MANIFEST_RECORD_RELATION_COUNT_MISMATCH")


def _init(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(DDL)
    connection.execute(
        "INSERT OR REPLACE INTO ledger_metadata VALUES ('schema_version', ?)",
        [SCHEMA_VERSION],
    )


def _insert_content_addressed(
    connection: duckdb.DuckDBPyConnection,
    *,
    table: str,
    id_field: str,
    identity: str,
    canonical_hash: str,
    columns: list[str],
    values: list[Any],
    source_path: str,
) -> bool:
    existing = connection.execute(
        f"SELECT canonical_payload_hash FROM {table} WHERE {id_field} = ?", [identity]
    ).fetchone()
    if existing:
        if existing[0] != canonical_hash:
            conflict = {
                "entity_type": table,
                "entity_id": identity,
                "existing_hash": existing[0],
                "incoming_hash": canonical_hash,
                "source_path": source_path,
            }
            conflict_id = content_hash(conflict)
            connection.execute(
                "INSERT OR IGNORE INTO ingestion_conflicts VALUES (?, ?, ?, ?, ?, ?)",
                [conflict_id, table, identity, existing[0], canonical_hash, source_path],
            )
        return False
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values
    )
    return True


def _ingest_trial_spec(
    connection: duckdb.DuckDBPyConnection, path: Path, payload: dict[str, Any]
) -> None:
    _assert_path_identity("trial_spec", path, payload)
    errors = validate_trial_spec(payload)
    if errors:
        raise ValueError(f"invalid TrialSpec {path}: {'; '.join(errors)}")
    identity = str(payload["trial_spec_id"])
    canonical_hash = content_hash(payload)
    inserted = _insert_content_addressed(
        connection,
        table="trial_specs",
        id_field="trial_spec_id",
        identity=identity,
        canonical_hash=canonical_hash,
        columns=[
            "trial_spec_id", "topic_id", "topic_family_id", "research_stage",
            "regime_scope_json", "dataset_hash", "ranking_source_hash", "parameters_json",
            "execution_profile_json", "parameter_catalog_hash", "canonical_payload_hash",
        ],
        values=[
            identity, payload["topic_id"], payload["topic_family_id"], payload["research_stage"],
            _json(payload["regime_scope"]), payload["dataset_authority"]["dataset_hash"],
            payload["ranking_source_authority"]["ranking_source_hash"],
            _json(payload["parameters"]), _json(payload["execution_profile"]),
            payload["parameter_catalog_hash"], canonical_hash,
        ],
        source_path=path.as_posix(),
    )
    if inserted:
        for parameter_id, value in payload["parameters"].items():
            connection.execute(
                "INSERT INTO trial_parameters VALUES (?, ?, ?, ?, ?, ?)",
                [identity, parameter_id, *_typed_parameter(parameter_id, value)],
            )


def _typed_parameter(parameter_id: str, value: Any) -> tuple[Any, Any, Any, Any]:
    if value is None:
        return "NOT_EXECUTED", None, None, None
    if parameter_id == "horizon":
        return "INTEGER", int(value), None, None
    if parameter_id in {"stop_loss_pct", "take_profit_pct", "max_group_exposure"}:
        return "CATEGORICAL" if value == "none" else "DECIMAL", None, (
            None if value == "none" else str(value)
        ), ("none" if value == "none" else None)
    return "CATEGORICAL", None, None, str(value)


def _ingest_intent(
    connection: duckdb.DuckDBPyConnection, path: Path, payload: dict[str, Any]
) -> None:
    _assert_path_identity("intent", path, payload)
    errors = validate_research_intent(payload)
    if errors:
        raise ValueError(f"invalid Intent {path}: {'; '.join(errors)}")
    requested_ids = set(payload["requested_trial_spec_ids"])
    available = {
        row[0]
        for row in connection.execute(
            "SELECT trial_spec_id FROM trial_specs WHERE trial_spec_id IN (SELECT unnest(?))",
            [list(requested_ids)],
        ).fetchall()
    }
    if available != requested_ids:
        raise ValueError("DANGLING_INTENT_TRIAL_SPEC")
    identity = str(payload["intent_id"])
    canonical_hash = content_hash(payload)
    _insert_content_addressed(
        connection,
        table="research_intents",
        id_field="intent_id",
        identity=identity,
        canonical_hash=canonical_hash,
        columns=[
            "intent_id", "requested_at", "request_source", "selection_reason_json",
            "trial_spec_ids_json", "canonical_payload_hash",
        ],
        values=[
            identity, payload["requested_at"], payload["request_source"],
            _json(payload["selection_reason"]), _json(payload["requested_trial_spec_ids"]),
            canonical_hash,
        ],
        source_path=path.as_posix(),
    )


def _ingest_attempt(
    connection: duckdb.DuckDBPyConnection, path: Path, payload: dict[str, Any]
) -> None:
    _assert_path_identity("attempt", path, payload)
    errors = validate_attempt_started(payload)
    if errors:
        raise ValueError(f"invalid AttemptStarted {path}: {'; '.join(errors)}")
    intent = connection.execute(
        "SELECT trial_spec_ids_json FROM research_intents WHERE intent_id = ?",
        [payload["intent_id"]],
    ).fetchone()
    if intent is None:
        raise ValueError("DANGLING_ATTEMPT_INTENT")
    requested_ids = set(payload["requested_trial_spec_ids"])
    if set(json.loads(intent[0])) != requested_ids:
        raise ValueError("ATTEMPT_INTENT_TRIAL_SPEC_MISMATCH")
    available = {
        row[0]
        for row in connection.execute(
            "SELECT trial_spec_id FROM trial_specs WHERE trial_spec_id IN (SELECT unnest(?))",
            [list(requested_ids)],
        ).fetchall()
    }
    if available != requested_ids:
        raise ValueError("DANGLING_ATTEMPT_TRIAL_SPEC")
    identity = str(payload["run_id"])
    canonical_hash = content_hash(payload)
    _insert_content_addressed(
        connection,
        table="run_attempts",
        id_field="run_id",
        identity=identity,
        canonical_hash=canonical_hash,
        columns=[
            "run_id", "attempt_event_id", "intent_id", "started_at", "executor_json",
            "invocation_hash", "trial_spec_ids_json", "canonical_payload_hash",
        ],
        values=[
            identity, payload["attempt_event_id"], payload["intent_id"], payload["started_at"],
            _json(payload["executor"]), payload["invocation_hash"],
            _json(payload["requested_trial_spec_ids"]), canonical_hash,
        ],
        source_path=path.as_posix(),
    )


def _scenario_for_unit(
    corpus_root: Path, unit: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    parameters = unit["executed_parameters"]
    base_keys = ("horizon", "stop_loss_pct", "take_profit_pct", "max_group_exposure")
    matches: list[tuple[dict[str, Any], str, str]] = []
    for artifact_id in unit["artifact_refs"]:
        artifact = artifacts.get(artifact_id)
        if not artifact or artifact["validation_status"] != "VALID":
            continue
        path = _verify_cas(corpus_root, artifact["corpus_path"], artifact_id)
        try:
            payload = _load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if payload.get("schema_version") != "backtest-strategy-matrix.v1":
            continue
        for row in payload.get("scenarios") or []:
            metric_keys = {
                "total_return", "max_drawdown", "win_rate", "avg_trade_return",
                "trade_count", "score", "p_value",
            }
            if metric_keys.issubset(row) and all(
                _same_scalar(row.get(key), parameters.get(key)) for key in base_keys
            ):
                matches.append((row, artifact_id, artifact["corpus_path"]))
    if len(matches) != 1:
        return None, None, None
    return matches[0]


def _same_scalar(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError):
        return left == right


def _observation_payload(
    receipt: dict[str, Any], unit: dict[str, Any], row: dict[str, Any]
) -> dict[str, Any]:
    result = {
        field: row.get(field)
        for field in (
            "scenario_id", "total_return", "max_drawdown", "win_rate", "avg_trade_return",
            "trade_count", "score", "p_value", "exit_reason_counts",
            "robust_neighbor_pass_count", "robust_neighbor_lineage",
        )
    }
    for field in (
        "total_return", "max_drawdown", "win_rate", "avg_trade_return", "score", "p_value"
    ):
        value = result[field]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        ):
            raise ValueError(f"INVALID_METRIC:{field}")
    if not isinstance(result["trade_count"], int) or isinstance(result["trade_count"], bool):
        raise ValueError("INVALID_METRIC:trade_count")
    result_payload_hash = content_hash(result)
    result_unit_id = str(row.get("scenario_id") or result_payload_hash)
    identity = {
        "schema_version": "research-observation-identity.v1",
        "identity_policy_version": OBSERVATION_IDENTITY_POLICY,
        "origin_execution_id": unit["execution_unit_id"],
        "executed_trial_identity": unit["executed_trial_spec_id"],
        "executed_lineage_id": unit["lineage"]["lineage_id"],
        "evidence_unit_id": content_hash(
            {
                "executed_trial_spec_id": unit["executed_trial_spec_id"],
                "lineage_id": unit["lineage"]["lineage_id"],
                "result_unit_id": result_unit_id,
                "metric_policy_version": METRIC_POLICY_VERSION,
            }
        ),
        "result_unit_id": result_unit_id,
        "metric_policy_version": METRIC_POLICY_VERSION,
        "attempt_inclusion_policy_version": ATTEMPT_INCLUSION_POLICY,
    }
    identity["observation_id"] = content_hash(identity)
    errors = validate_observation_identity(identity)
    if errors:
        raise ValueError(f"invalid observation identity: {'; '.join(errors)}")
    return {**identity, "result": result, "result_payload_hash": result_payload_hash}


def _ingest_receipt(
    connection: duckdb.DuckDBPyConnection, corpus_root: Path, path: Path, receipt: dict[str, Any]
) -> tuple[bool, int]:
    _assert_path_identity("receipt", path, receipt)
    errors = validate_run_receipt(receipt)
    if errors:
        raise InvalidSourceSchema(path.stem, _file_hash(path), errors)
    if connection.execute(
        "SELECT count(*) FROM research_intents WHERE intent_id = ?", [receipt["intent_id"]]
    ).fetchone()[0] != 1:
        raise ValueError(f"dangling receipt intent: {receipt['intent_id']}")
    attempt = connection.execute(
        "SELECT attempt_event_id, intent_id, trial_spec_ids_json FROM run_attempts WHERE run_id = ?",
        [receipt["run_id"]],
    ).fetchone()
    expected_attempt = (
        receipt["attempt_event_id"], receipt["intent_id"],
        _json(receipt["requested"]["trial_spec_ids"]),
    )
    if attempt != expected_attempt:
        raise ValueError(f"dangling or mismatched receipt attempt: {receipt['run_id']}")
    requested_ids = set(receipt["requested"]["trial_spec_ids"])
    available_ids = {
        row[0]
        for row in connection.execute(
            "SELECT trial_spec_id FROM trial_specs WHERE trial_spec_id IN (SELECT unnest(?))",
            [list(requested_ids)],
        ).fetchall()
    }
    if requested_ids != available_ids:
        raise ValueError("receipt references missing requested TrialSpec")
    intent_trials = connection.execute(
        "SELECT trial_spec_ids_json FROM research_intents WHERE intent_id = ?",
        [receipt["intent_id"]],
    ).fetchone()[0]
    if set(json.loads(intent_trials)) != requested_ids:
        raise ValueError("receipt requested TrialSpecs mismatch Intent")
    executed_ids = {unit["executed_trial_spec_id"] for unit in receipt["executed_units"]}
    if executed_ids:
        found_executed = {
            row[0]
            for row in connection.execute(
                "SELECT trial_spec_id FROM trial_specs WHERE trial_spec_id IN (SELECT unnest(?))",
                [list(executed_ids)],
            ).fetchall()
        }
        if found_executed != executed_ids:
            raise ValueError("receipt references missing executed TrialSpec")
    receipt_id = str(receipt["receipt_id"])
    existing = connection.execute(
        "SELECT receipt_payload_hash FROM run_receipts WHERE receipt_id = ?", [receipt_id]
    ).fetchone()
    receipt_hash = content_hash(receipt)
    if existing:
        if existing[0] != receipt_hash:
            raise ValueError(f"receipt identity collision: {receipt_id}")
        return False, 0
    connection.execute(
        "INSERT INTO run_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            receipt_id, receipt["run_id"], receipt["intent_id"], receipt["terminal_status"],
            receipt["execution_observation_status"], receipt["identity_match_status"],
            receipt["started_at"], receipt["completed_at"], receipt_hash,
            path.relative_to(corpus_root).as_posix(),
        ],
    )
    artifacts = {item["artifact_id"]: item for item in receipt["artifacts"]}
    for artifact in receipt["artifacts"]:
        _verify_cas(corpus_root, artifact["corpus_path"], artifact["artifact_id"])
        connection.execute(
            "INSERT OR IGNORE INTO run_artifacts VALUES (?, ?, ?, ?, ?)",
            [
                artifact["artifact_id"], receipt_id, artifact["corpus_path"],
                artifact["provenance_path"], artifact["validation_status"],
            ],
        )
    observation_count = 0
    for unit in receipt["executed_units"]:
        unit_hash = content_hash(unit)
        inserted_unit = _insert_content_addressed(
            connection,
            table="execution_units",
            id_field="execution_unit_id",
            identity=unit["execution_unit_id"],
            canonical_hash=unit_hash,
            columns=[
                "execution_unit_id", "receipt_id", "requested_trial_spec_id",
                "executed_trial_spec_id", "lineage_id", "sealed_usage_status",
                "lineage_resolution_status", "episode_ids_json", "artifact_refs_json",
                "canonical_payload_hash",
            ],
            values=[
                unit["execution_unit_id"], receipt_id, unit["requested_trial_spec_id"],
                unit["executed_trial_spec_id"], unit["lineage"]["lineage_id"],
                unit["lineage"]["sealed_usage_status"], unit["lineage_resolution_status"],
                _json(unit["lineage"]["episode_ids"]), _json(unit["artifact_refs"]), unit_hash,
            ],
            source_path=path.as_posix(),
        )
        if inserted_unit:
            for parameter_id, value in unit["executed_parameters"].items():
                connection.execute(
                    "INSERT INTO execution_unit_parameters VALUES (?, ?, ?, ?, ?, ?)",
                    [unit["execution_unit_id"], parameter_id, *_typed_parameter(parameter_id, value)],
                )
            for episode_id in unit["lineage"]["episode_ids"]:
                connection.execute(
                    "INSERT INTO execution_unit_episodes VALUES (?, ?)",
                    [unit["execution_unit_id"], episode_id],
                )
        row, artifact_id, corpus_path_value = _scenario_for_unit(corpus_root, unit, artifacts)
        if row is None or artifact_id is None or corpus_path_value is None:
            continue
        observation = _observation_payload(receipt, unit, row)
        existing_observation = connection.execute(
            "SELECT result_payload_hash FROM observations WHERE observation_id = ?",
            [observation["observation_id"]],
        ).fetchone()
        if existing_observation:
            if existing_observation[0] != observation["result_payload_hash"]:
                conflict = {
                    "entity_type": "observations",
                    "entity_id": observation["observation_id"],
                    "existing_hash": existing_observation[0],
                    "incoming_hash": observation["result_payload_hash"],
                    "source_path": path.as_posix(),
                }
                connection.execute(
                    "INSERT OR IGNORE INTO ingestion_conflicts VALUES (?, ?, ?, ?, ?, ?)",
                    [content_hash(conflict), *conflict.values()],
                )
            continue
        semantic_collision = connection.execute(
            "SELECT observation_id, result_payload_hash FROM observations WHERE evidence_unit_id = ?",
            [observation["evidence_unit_id"]],
        ).fetchone()
        if semantic_collision:
            if semantic_collision[1] == observation["result_payload_hash"]:
                connection.execute(
                    "INSERT OR IGNORE INTO observation_provenance VALUES (?, ?, ?, ?)",
                    [semantic_collision[0], artifact_id, receipt_id, corpus_path_value],
                )
                continue
            conflict = {
                "entity_type": "semantic_evidence",
                "entity_id": observation["evidence_unit_id"],
                "existing_hash": semantic_collision[1],
                "incoming_hash": observation["result_payload_hash"],
                "source_path": path.as_posix(),
            }
            connection.execute(
                "INSERT OR IGNORE INTO ingestion_conflicts VALUES (?, ?, ?, ?, ?, ?)",
                [content_hash(conflict), *conflict.values()],
            )
            continue
        result = observation["result"]
        connection.execute(
            "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                observation["observation_id"], unit["execution_unit_id"], receipt_id,
                unit["executed_trial_spec_id"], unit["lineage"]["lineage_id"],
                observation["result_unit_id"], observation["evidence_unit_id"],
                result.get("scenario_id"), result.get("total_return"), result.get("max_drawdown"),
                result.get("win_rate"), result.get("avg_trade_return"), result.get("trade_count"),
                result.get("score"), result.get("p_value"),
                result.get("robust_neighbor_pass_count"), observation["result_payload_hash"],
                OBSERVATION_IDENTITY_POLICY, METRIC_POLICY_VERSION, ATTEMPT_INCLUSION_POLICY,
            ],
        )
        connection.execute(
            "INSERT INTO observation_provenance VALUES (?, ?, ?, ?)",
            [observation["observation_id"], artifact_id, receipt_id, corpus_path_value],
        )
        observation_count += 1
    return True, observation_count


def _paths(root: Path, entity: str) -> Iterable[Path]:
    return sorted((root / entity).glob("*.json"))


def ledger_snapshot(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    tables = (
        "trial_specs", "trial_parameters", "research_intents", "run_attempts", "run_receipts",
        "run_artifacts", "execution_units", "execution_unit_parameters",
        "execution_unit_episodes", "observations", "observation_provenance",
        "ingestion_conflicts", "ingestion_rejections",
        "migration_manifests", "migration_sources", "migrated_records",
        "migration_manifest_records",
        "migrated_record_reasons",
        "migration_quality_reports", "migration_artifact_dispositions",
        "migration_record_dispositions", "migration_combo_edges",
        "legacy_semantic_evidence", "legacy_semantic_provenance",
    )
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "tables": {}}
    for table in tables:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall()]
        excluded = {
            "run_receipts": {"receipt_corpus_path"},
            "run_artifacts": {"provenance_path"},
            "ingestion_conflicts": {"source_path"},
        }.get(table, set())
        logical_columns = [column for column in columns if column not in excluded]
        rows = connection.execute(
            f"SELECT {', '.join(logical_columns)} FROM {table} ORDER BY ALL"
        ).fetchall()
        payload["tables"][table] = {
            "row_count": len(rows),
            "content_hash": content_hash(
                {"columns": logical_columns, "rows": [list(row) for row in rows]}
            ),
        }
    payload["snapshot_hash"] = content_hash(payload)
    return payload


def ingest_corpus(
    *, corpus_root: Path = DEFAULT_CORPUS_ROOT, ledger_path: Path = DEFAULT_LEDGER_PATH,
    run_date: str | None = None, rebuild: bool = False,
) -> IngestResult:
    if rebuild:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = ledger_path.with_name(f".{ledger_path.name}.{uuid.uuid4().hex}.rebuild")
        try:
            result = ingest_corpus(
                corpus_root=corpus_root,
                ledger_path=temporary,
                run_date=None,
                rebuild=False,
            )
            descriptor = os.open(temporary, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, ledger_path)
            directory = os.open(ledger_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return result
        finally:
            temporary.unlink(missing_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(ledger_path))
    try:
        _init(connection)
        loaders = (
            ("trial_spec", "trial_specs", _ingest_trial_spec),
            ("intent", "intents", _ingest_intent),
            ("attempt", "attempts", _ingest_attempt),
        )
        for source_type, directory, loader in loaders:
            for path in _paths(corpus_root, directory):
                source_id = _expected_identity(source_type, path)
                connection.execute("BEGIN TRANSACTION")
                try:
                    state = _source_state(
                        connection,
                        source_type=source_type,
                        source_id=source_id,
                        path=path,
                    )
                    if state == "NEW":
                        loader(connection, path, _load_json(path))
                    connection.execute("COMMIT")
                except Exception as error:
                    connection.execute("ROLLBACK")
                    connection.execute("BEGIN TRANSACTION")
                    _record_rejection(
                        connection,
                        source_type=source_type,
                        source_identity=source_id,
                        source_hash=_file_hash(path),
                        reasons=[type(error).__name__, str(error)],
                    )
                    connection.execute("COMMIT")
        receipts_seen = receipts_inserted = observations_inserted = 0
        for path in _paths(corpus_root, "receipts"):
            receipts_seen += 1
            connection.execute("BEGIN TRANSACTION")
            try:
                state = _source_state(
                    connection,
                    source_type="receipt",
                    source_id=path.stem,
                    path=path,
                )
                inserted = False
                observations = 0
                if state == "NEW":
                    inserted, observations = _ingest_receipt(
                        connection, corpus_root, path, _load_json(path)
                    )
                connection.execute("COMMIT")
                receipts_inserted += int(inserted)
                observations_inserted += observations
            except Exception as error:
                connection.execute("ROLLBACK")
                if isinstance(error, CorpusIntegrityError):
                    raise
                connection.execute("BEGIN TRANSACTION")
                _record_rejection(
                    connection,
                    source_type="receipt",
                    source_identity=path.stem,
                    source_hash=_file_hash(path),
                    reasons=[type(error).__name__, str(error)],
                )
                connection.execute("COMMIT")
        connection.execute("BEGIN TRANSACTION")
        try:
            _ingest_migrations(connection, corpus_root)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        corpus_hash = input_corpus_hash(connection)
        connection.execute("BEGIN TRANSACTION")
        connection.execute(
            "INSERT OR REPLACE INTO ledger_metadata VALUES ('input_corpus_hash', ?)",
            [corpus_hash],
        )
        connection.execute("COMMIT")
        conflicts = connection.execute("SELECT count(*) FROM ingestion_conflicts").fetchone()[0]
        rejections = connection.execute("SELECT count(*) FROM ingestion_rejections").fetchone()[0]
        snapshot = ledger_snapshot(connection)
        return IngestResult(
            receipts_seen, receipts_inserted, observations_inserted, conflicts, rejections,
            snapshot["snapshot_hash"],
        )
    except Exception:
        raise
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ingest immutable Research Spine receipts")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.verify:
        connection = duckdb.connect(str(args.ledger), read_only=True)
        try:
            print(json.dumps(ledger_snapshot(connection), ensure_ascii=False, sort_keys=True))
        finally:
            connection.close()
        return 0
    result = ingest_corpus(
        corpus_root=args.corpus_root,
        ledger_path=args.ledger,
        run_date=args.date,
        rebuild=args.rebuild,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
