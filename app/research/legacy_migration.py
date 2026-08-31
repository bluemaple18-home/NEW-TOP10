"""Legacy research sources 的一次性、fail-closed migration corpus builder。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.research.contracts import (
    content_hash, validate_migrated_record, validate_migration_manifest_v2,
    validate_trial_spec,
)
from app.research.receipt_store import publish_bytes_to_cas, publish_file_to_cas


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEGACY_ROOT = PROJECT_ROOT / "artifacts" / "autonomous_research"
DEFAULT_CORPUS_ROOT = DEFAULT_LEGACY_ROOT / "research_spine"
PARSER_VERSION = "legacy-research-parser.v2"
SEMANTIC_POLICY = "legacy-semantic-evidence.v1"
PRECLASSIFICATION_POLICY = "legacy-preclassification.v1"
AUTHORITY_ORDER_VERSION = "research-source-authority.v1"
DISPOSITION_POLICY = "legacy-migration-disposition.v1"
INFERENCE_POLICY = "legacy-canonical-target-inference.v1"
METRICS = (
    "total_return", "max_drawdown", "win_rate", "avg_trade_return", "trade_count",
    "score", "p_value", "robust_neighbor_pass_count",
)


@dataclass(frozen=True)
class LegacySource:
    path: Path
    source_type: str


def discover_legacy_sources(root: Path) -> list[LegacySource]:
    sources: list[LegacySource] = []
    for name, kind in (("run_history.jsonl", "RUN_HISTORY_JSONL"), ("run_history.json", "RUN_HISTORY_JSON")):
        path = root / name
        if path.is_file():
            sources.append(LegacySource(path, kind))
    for path in sorted(root.glob("run_*/**/*_strategy_matrix.json")):
        if "research_spine" not in path.parts:
            sources.append(LegacySource(path, "STRATEGY_MATRIX"))
    return sources


def _json_rows(source: LegacySource) -> Iterable[tuple[str, Any]]:
    if source.source_type == "RUN_HISTORY_JSONL":
        for index, line in enumerate(source.path.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                value = json.loads(line)
                yield f"jsonl:{index}", value
        return
    payload = json.loads(source.path.read_text(encoding="utf-8"))
    if source.source_type == "STRATEGY_MATRIX":
        for index, value in enumerate(payload.get("scenarios") or []):
            if isinstance(value, dict):
                yield f"json-pointer:/scenarios/{index}", {
                    **value,
                    "_matrix_contract": payload.get("contract") or {},
                    "_matrix_inputs": payload.get("inputs") or {},
                }
            else:
                yield f"json-pointer:/scenarios/{index}", value
        return
    rows = payload.get("history") or payload.get("runs") or payload.get("rows") or []
    if isinstance(rows, list):
        for index, value in enumerate(rows):
            yield f"json-pointer:/rows/{index}", value


def _canonical_targets(corpus_root: Path) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for path in sorted((corpus_root / "trial_specs").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        errors = validate_trial_spec(payload)
        trial_id = str(payload.get("trial_spec_id") or "")
        if errors or path.stem != trial_id.removeprefix("sha256:"):
            continue
        targets[trial_id] = payload
    return targets


def _canonical_candidates(
    row: dict[str, Any], targets: dict[str, dict[str, Any]]
) -> tuple[str | None, str, list[str], list[str], list[dict[str, Any]], bool]:
    evidence = row.get("migration_evidence")
    if not isinstance(evidence, dict):
        return None, "NOT_APPLICABLE", [], [], [], False
    mode = str(evidence.get("mapping_mode") or "")
    confidence = str(evidence.get("confidence") or "")
    reasons = sorted(set(value for value in evidence.get("reason_codes") or [] if isinstance(value, str) and value))
    refs = sorted(set(value for value in evidence.get("evidence_refs") or [] if isinstance(value, str) and value))
    candidates: list[dict[str, Any]] = []
    for raw in evidence.get("candidates") or []:
        if not isinstance(raw, dict):
            continue
        trial_id = str(raw.get("canonical_trial_spec_id") or "")
        if trial_id not in targets:
            continue
        target = targets[trial_id]
        if target.get("parameters") != _parameters(row) or target.get("topic_id") != row.get("topic_id"):
            continue
        combo_id = str(raw.get("combo_id") or "")
        edge_reasons = sorted(set(
            value for value in raw.get("reason_codes") or [] if isinstance(value, str) and value
        ))
        edge_refs = sorted(set(
            value for value in raw.get("evidence_refs") or [] if isinstance(value, str) and value
        ))
        if not combo_id or not edge_reasons or trial_id not in edge_refs:
            continue
        candidates.append({
            "combo_id": combo_id,
            "canonical_trial_spec_id": trial_id,
            "reason_codes": edge_reasons,
            "evidence_refs": edge_refs,
        })
    candidates.sort(key=lambda item: (item["combo_id"], item["canonical_trial_spec_id"]))
    unique = {(item["combo_id"], item["canonical_trial_spec_id"]): item for item in candidates}
    candidates = [unique[key] for key in sorted(unique)]
    all_targets_proven = evidence.get("multi_target_resolution") == "ALL_TARGETS_PROVEN"
    return mode, confidence, reasons, refs, candidates, all_targets_proven


def _parameters(row: dict[str, Any]) -> dict[str, Any] | None:
    dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
    values = {
        "horizon": row.get("horizon", dimensions.get("horizon")),
        "stop_loss_pct": row.get("stop_loss_pct", dimensions.get("stop_loss")),
        "take_profit_pct": row.get("take_profit_pct", dimensions.get("take_profit")),
        "max_group_exposure": row.get("max_group_exposure", dimensions.get("group_exposure")),
        "regime_gate": None,
        "risk_guard": None,
        "entry_filter": None,
    }
    if any(values[key] is None for key in tuple(values)[:4]):
        return None
    try:
        values["horizon"] = int(values["horizon"])
    except (TypeError, ValueError):
        return None
    return values


def _metrics(row: dict[str, Any]) -> dict[str, Any] | None:
    result = {key: row.get(key) for key in METRICS}
    if all(value is None for value in result.values()):
        return None
    return result


def map_record(
    *, source: LegacySource, artifact_id: str, locator: str, row: Any,
    canonical_targets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = canonical_targets or {}
    if not isinstance(row, dict):
        core = {
            "schema_version": "research-migrated-record.v2",
            "parser_version": PARSER_VERSION,
            "source": {"artifact_id": artifact_id, "source_type": source.source_type, "record_locator": locator},
            "record_kind": "NON_RESEARCH_RECORD",
            "legacy_identity": {"combo_id": None, "topic_id": None, "scenario_id": None},
            "parameters": None,
            "metrics": None,
            "preliminary_classification": "NOT_APPLICABLE_NON_OBSERVATION",
            "migration_disposition": "EXCLUDED_NON_RESEARCH",
            "disposition_policy_version": DISPOSITION_POLICY,
            "inference_policy_version": "NOT_APPLICABLE",
            "confidence": "NOT_APPLICABLE",
            "reason_codes": ["JSON_ROW_IS_NOT_OBJECT"],
            "evidence_refs": [artifact_id],
            "combo_mapping": {"mapping_status": "UNMAPPED", "cardinality": "ZERO", "candidates": []},
            "semantic_evidence_id": None,
        }
        core["migration_record_id"] = content_hash(
            {"policy_version": PARSER_VERSION, "artifact_id": artifact_id, "locator": locator, "record": core}
        )
        return core
    parameters = _parameters(row)
    metrics = _metrics(row)
    matrix_contract = (
        row.get("_matrix_contract")
        if isinstance(row.get("_matrix_contract"), dict)
        else {}
    )
    sealed_only = (
        matrix_contract.get("research_stage") == "SEALED_VALIDATION"
        or matrix_contract.get("sealed_data_read_allowed") is True
    )
    unsupported = str(row.get("status") or "").upper() in {"UNSUPPORTED", "RULE_PRUNED"}
    if unsupported:
        kind = "UNSUPPORTED_COORDINATE"
        classification = "UNSUPPORTED_NOT_AN_OBSERVATION"
        reasons = ["LEGACY_UNSUPPORTED_IS_NOT_FAILURE"]
    elif parameters is None:
        kind = "TOPIC_SUMMARY"
        classification = "TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE"
        reasons = ["MISSING_COMPLETE_PARAMETER_IDENTITY"]
    elif metrics is None:
        kind = "UNRESOLVED_RECORD"
        classification = "LEGACY_DIAGNOSTIC_ONLY"
        reasons = ["MISSING_RESULT_METRICS"]
    elif sealed_only:
        kind = "PARAMETER_RESULT"
        classification = "SEALED_VALIDATION_ONLY"
        reasons = ["LEGACY_SOURCE_DECLARED_SEALED_VALIDATION"]
    else:
        kind = "PARAMETER_RESULT"
        classification = "LEGACY_DIAGNOSTIC_ONLY"
        reasons = ["UNPROVEN_DATASET_REGIME_STAGE_AND_SEALED_LINEAGE"]
    semantic_id = None
    if kind == "PARAMETER_RESULT":
        semantic_id = content_hash(
            {
                "policy_version": SEMANTIC_POLICY,
                "parameters": parameters,
                "topic_id": row.get("topic_id"),
                "scenario_id": row.get("scenario_id"),
                "metrics_policy": "strategy-matrix-metrics.v1",
            }
        )
    (
        mode, confidence, mapping_reasons, mapping_refs, candidates, all_targets_proven,
    ) = _canonical_candidates(row, targets)
    if (
        kind == "PARAMETER_RESULT" and len(candidates) > 1 and all_targets_proven
        and mode == "EXACT" and confidence == "EXACT" and mapping_reasons
    ):
        disposition = "MIGRATED_EXACT"
        disposition_confidence = "EXACT"
        mapping_status = "RESOLVED_ONE_TO_MANY"
        reasons = mapping_reasons
        inference_version = "NOT_APPLICABLE"
    elif (
        kind == "PARAMETER_RESULT" and len(candidates) > 1 and all_targets_proven
        and mode == "INFERRED" and confidence in {"HIGH", "MEDIUM", "LOW"}
        and mapping_reasons
    ):
        disposition = "MIGRATED_INFERRED"
        disposition_confidence = confidence
        mapping_status = "RESOLVED_ONE_TO_MANY"
        reasons = mapping_reasons
        inference_version = INFERENCE_POLICY
        if classification == "SEALED_VALIDATION_ONLY":
            classification = "LEGACY_DIAGNOSTIC_ONLY"
    elif len(candidates) > 1:
        disposition = "LEGACY_UNRESOLVED"
        disposition_confidence = "NOT_APPLICABLE"
        mapping_status = "AMBIGUOUS_NO_WINNER"
        reasons = mapping_reasons or ["AMBIGUOUS_CANONICAL_TARGET"]
        inference_version = INFERENCE_POLICY
        if classification == "SEALED_VALIDATION_ONLY":
            classification = "LEGACY_DIAGNOSTIC_ONLY"
    elif (
        kind == "PARAMETER_RESULT" and len(candidates) == 1
        and mode == "EXACT" and confidence == "EXACT" and mapping_reasons
    ):
        disposition = "MIGRATED_EXACT"
        disposition_confidence = "EXACT"
        mapping_status = "RESOLVED"
        reasons = mapping_reasons
        inference_version = "NOT_APPLICABLE"
    elif (
        kind == "PARAMETER_RESULT" and len(candidates) == 1 and mode == "INFERRED"
        and confidence in {"HIGH", "MEDIUM", "LOW"} and mapping_reasons
    ):
        disposition = "MIGRATED_INFERRED"
        disposition_confidence = confidence
        mapping_status = "RESOLVED"
        reasons = mapping_reasons
        inference_version = INFERENCE_POLICY
        if classification == "SEALED_VALIDATION_ONLY":
            classification = "LEGACY_DIAGNOSTIC_ONLY"
    elif isinstance(row.get("migration_evidence"), dict):
        disposition = "LEGACY_UNRESOLVED"
        disposition_confidence = "NOT_APPLICABLE"
        mapping_status = "UNMAPPED"
        reasons = ["INVALID_OR_UNPROVEN_CANONICAL_TARGET_EVIDENCE"]
        inference_version = INFERENCE_POLICY
        candidates = []
        if classification == "SEALED_VALIDATION_ONLY":
            classification = "LEGACY_DIAGNOSTIC_ONLY"
    else:
        disposition = "LEGACY_INCOMPLETE"
        disposition_confidence = "NOT_APPLICABLE"
        mapping_status = "UNMAPPED"
        reasons = sorted(set(reasons + ["MISSING_CANONICAL_LINEAGE_EVIDENCE"]))
        inference_version = "NOT_APPLICABLE"
        candidates = []
        if classification == "SEALED_VALIDATION_ONLY":
            classification = "LEGACY_DIAGNOSTIC_ONLY"
    core = {
        "schema_version": "research-migrated-record.v2",
        "parser_version": PARSER_VERSION,
        "source": {
            "artifact_id": artifact_id,
            "source_type": source.source_type,
            "record_locator": locator,
        },
        "record_kind": kind,
        "legacy_identity": {
            "combo_id": row.get("combo_id"),
            "topic_id": row.get("topic_id"),
            "scenario_id": row.get("scenario_id"),
        },
        "parameters": parameters,
        "metrics": metrics,
        "preliminary_classification": classification,
        "migration_disposition": disposition,
        "disposition_policy_version": DISPOSITION_POLICY,
        "inference_policy_version": inference_version,
        "confidence": disposition_confidence,
        "reason_codes": reasons,
        "evidence_refs": sorted(set([artifact_id, *mapping_refs])),
        "combo_mapping": {
            "mapping_status": mapping_status,
            "cardinality": "ZERO" if not candidates else "ONE" if len(candidates) == 1 else "ONE_TO_MANY",
            "candidates": candidates,
        },
        "semantic_evidence_id": semantic_id,
    }
    core["migration_record_id"] = content_hash(
        {"policy_version": PARSER_VERSION, "artifact_id": artifact_id, "locator": locator, "record": core}
    )
    return core


def _canonical_lines(records: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for record in sorted(records, key=lambda item: item["migration_record_id"])
        )
        + "\n"
    ).encode("utf-8")


def build_migration(
    *, legacy_root: Path = DEFAULT_LEGACY_ROOT, corpus_root: Path = DEFAULT_CORPUS_ROOT,
    sources: list[LegacySource] | None = None,
) -> dict[str, Any]:
    source_entries_by_artifact: dict[str, dict[str, Any]] = {}
    all_records: list[dict[str, Any]] = []
    targets = _canonical_targets(corpus_root)
    record_root = corpus_root / "migration" / "records"
    record_root.mkdir(parents=True, exist_ok=True)
    selected_sources = sources if sources is not None else discover_legacy_sources(legacy_root)
    for source in selected_sources:
        artifact_id, cas_path = publish_file_to_cas(corpus_root, source.path)
        located = list(_json_rows(source))
        records = [
            map_record(
                source=source, artifact_id=artifact_id, locator=locator, row=row,
                canonical_targets=targets,
            )
            for locator, row in located
        ]
        excluded = sum(
            record["migration_disposition"] == "EXCLUDED_NON_RESEARCH" for record in records
        )
        for record in records:
            errors = validate_migrated_record(record)
            if errors:
                raise ValueError("invalid migrated record: " + "; ".join(errors))
        encoded = _canonical_lines(records)
        mapping_id, mapping_cas = publish_bytes_to_cas(corpus_root, encoded)
        mapping_path = record_root / f"{mapping_id[7:]}.jsonl"
        if mapping_path.exists() and mapping_path.read_bytes() != encoded:
            raise ValueError("migration mapping collision")
        if not mapping_path.exists():
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            mapping_path.hardlink_to(mapping_cas)
        classifications = Counter(record["preliminary_classification"] for record in records)
        dispositions = Counter(record["migration_disposition"] for record in records)
        reasons = Counter(reason for record in records for reason in record["reason_codes"])
        artifact_disposition = (
            "EXCLUDED_NON_RESEARCH" if records and excluded == len(records)
            else "LEGACY_UNRESOLVED" if dispositions["LEGACY_UNRESOLVED"]
            else "LEGACY_INCOMPLETE" if dispositions["LEGACY_INCOMPLETE"]
            else "MIGRATED_INFERRED" if dispositions["MIGRATED_INFERRED"]
            else "MIGRATED_EXACT" if records
            else "EXCLUDED_NON_RESEARCH"
        )
        artifact_record = {
            "source_artifact_id": artifact_id,
            "source_type": source.source_type,
            "record_locator": "$artifact",
            "record_kind": "SOURCE_ARTIFACT",
            "migration_disposition": artifact_disposition,
            "preliminary_classification": "NOT_APPLICABLE_NON_OBSERVATION",
            "disposition_policy_version": DISPOSITION_POLICY,
            "inference_policy_version": "NOT_APPLICABLE",
            "confidence": "NOT_APPLICABLE",
            "reason_codes": ["ARTIFACT_ROWS_INVENTORIED" if records else "ARTIFACT_HAS_NO_ROWS"],
            "evidence_refs": [artifact_id],
            "combo_mapping": {
                "mapping_status": "UNMAPPED", "cardinality": "ZERO", "candidates": []
            },
        }
        artifact_record["artifact_disposition_id"] = content_hash(artifact_record)
        edges = sum(len(record["combo_mapping"]["candidates"]) for record in records)
        observation_like = sum(record["record_kind"] == "PARAMETER_RESULT" for record in records)
        nonexcluded = len(records) - excluded
        reconciliation = {
            "source_artifacts_seen": 1,
            "source_artifact_disposition_counts": {artifact_disposition: 1},
            "rows_seen": len(records),
            "legacy_run_rows": len(records) if source.source_type.startswith("RUN_HISTORY") else 0,
            "legacy_observation_like_rows": observation_like,
            "mapping_edges_emitted": edges,
            "new_migrated_records": nonexcluded,
            "excluded_disposition_records": excluded,
            "projected_observations": 0,
            "typed_gaps": {
                "excluded": excluded,
                "incomplete": dispositions["LEGACY_INCOMPLETE"],
                "unresolved": dispositions["LEGACY_UNRESOLVED"],
                "deduplicated": 0,
                "one_to_many_expansion": sum(
                    max(len(record["combo_mapping"]["candidates"]) - 1, 0)
                    for record in records
                ),
                "not_observation": len(records),
            },
            "unexplained_delta": 0,
        }
        entry = {
                "source_artifact_hash": artifact_id,
                "corpus_artifact_path": cas_path.relative_to(corpus_root).as_posix(),
                "source_type": source.source_type,
                "parser_version": PARSER_VERSION,
                "record_mapping_path": mapping_path.relative_to(corpus_root).as_posix(),
                "record_mapping_hash": mapping_id,
                "record_counts": {
                    "seen": len(records), "mapped": nonexcluded, "excluded": excluded
                },
                "classification_counts": dict(sorted(classifications.items())),
                "disposition_counts": dict(sorted(dispositions.items())),
                "reason_code_counts": dict(sorted(reasons.items())),
                "artifact_disposition_record": artifact_record,
                "reconciliation": reconciliation,
            }
        existing = source_entries_by_artifact.get(artifact_id)
        if existing is not None and existing != entry:
            raise ValueError("same source bytes produced inconsistent mapping")
        source_entries_by_artifact[artifact_id] = entry
        all_records.extend(records)
    sources_sorted = sorted(
        source_entries_by_artifact.values(), key=lambda item: item["source_artifact_hash"]
    )
    total_dispositions = Counter()
    total_artifact_dispositions = Counter()
    totals = Counter()
    total_gaps = Counter()
    for source in sources_sorted:
        total_dispositions.update(source["disposition_counts"])
        total_artifact_dispositions.update(
            source["reconciliation"]["source_artifact_disposition_counts"]
        )
        for field in (
            "source_artifacts_seen", "rows_seen", "legacy_run_rows",
            "legacy_observation_like_rows", "mapping_edges_emitted", "new_migrated_records",
            "excluded_disposition_records", "projected_observations", "unexplained_delta",
        ):
            totals[field] += source["reconciliation"][field]
        total_gaps.update(source["reconciliation"]["typed_gaps"])
    for field in (
        "source_artifacts_seen", "rows_seen", "legacy_run_rows",
        "legacy_observation_like_rows", "mapping_edges_emitted", "new_migrated_records",
        "excluded_disposition_records", "projected_observations", "unexplained_delta",
    ):
        totals.setdefault(field, 0)
    for field in (
        "excluded", "incomplete", "unresolved", "deduplicated",
        "one_to_many_expansion", "not_observation",
    ):
        total_gaps.setdefault(field, 0)
    quality = {
        "schema_version": "research-migration-quality-report.v1",
        "disposition_policy_version": DISPOSITION_POLICY,
        "inference_policy_version": INFERENCE_POLICY,
        "source_artifact_disposition_counts": dict(sorted(total_artifact_dispositions.items())),
        "row_disposition_counts": dict(sorted(total_dispositions.items())),
        "totals": {**dict(totals), "typed_gaps": dict(sorted(total_gaps.items()))},
    }
    quality["quality_report_id"] = content_hash(quality)
    quality_encoded = json.dumps(quality, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    quality_hash, quality_cas = publish_bytes_to_cas(corpus_root, quality_encoded)
    quality_dir = corpus_root / "migration" / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    quality_path = quality_dir / f"{quality_hash[7:]}.json"
    if quality_path.exists() and quality_path.read_bytes() != quality_encoded:
        raise ValueError("migration quality report collision")
    if not quality_path.exists():
        quality_path.hardlink_to(quality_cas)
    identity = {
        "schema_version": "research-ledger-migration-manifest.v2",
        "parser_version": PARSER_VERSION,
        "semantic_identity_policy_version": SEMANTIC_POLICY,
        "eligibility_preclassification_policy_version": PRECLASSIFICATION_POLICY,
        "source_authority_order_version": AUTHORITY_ORDER_VERSION,
        "disposition_policy_version": DISPOSITION_POLICY,
        "inference_policy_version": INFERENCE_POLICY,
        "duplicate_policy": "SEMANTIC_EVIDENCE_DEWEIGHT",
        "conflict_policy": "FAIL_CLOSED_NO_WINNER",
        "quality_report_path": quality_path.relative_to(corpus_root).as_posix(),
        "quality_report_hash": quality_hash,
        "sources": sources_sorted,
    }
    identity["migration_id"] = content_hash(identity)
    errors = validate_migration_manifest_v2(identity)
    if errors:
        raise ValueError("invalid migration manifest: " + "; ".join(errors))
    manifest_dir = corpus_root / "migration" / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{identity['migration_id'][7:]}.json"
    encoded_manifest = json.dumps(identity, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    if manifest_path.exists() and manifest_path.read_bytes() != encoded_manifest:
        raise ValueError("migration manifest collision")
    _, manifest_cas = publish_bytes_to_cas(corpus_root, encoded_manifest)
    if not manifest_path.exists():
        manifest_path.hardlink_to(manifest_cas)
    return {
        "manifest": identity,
        "manifest_path": manifest_path,
        "records": all_records,
        "quality_report": quality,
        "quality_report_path": quality_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build immutable legacy research migration corpus")
    parser.add_argument("--legacy-root", type=Path, default=DEFAULT_LEGACY_ROOT)
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_migration(legacy_root=args.legacy_root, corpus_root=args.corpus_root)
    counts = Counter(record["preliminary_classification"] for record in result["records"])
    print(json.dumps({
        "migration_id": result["manifest"]["migration_id"],
        "source_count": len(result["manifest"]["sources"]),
        "record_count": len(result["records"]),
        "classification_counts": dict(sorted(counts.items())),
        "manifest_path": str(result["manifest_path"]),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
