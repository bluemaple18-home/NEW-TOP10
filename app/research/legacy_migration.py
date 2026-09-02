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
    validate_trial_spec, validate_legacy_mapping_authority, validate_run_receipt,
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


@dataclass(frozen=True)
class ParsedLegacyRow:
    locator: str
    value: Any
    parser_status: str


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


def _json_rows(source: LegacySource) -> Iterable[ParsedLegacyRow]:
    if source.source_type == "RUN_HISTORY_JSONL":
        lines = source.path.read_text(encoding="utf-8").splitlines()
        if not lines:
            yield ParsedLegacyRow("jsonl:$empty", None, "EMPTY_RESEARCH_ARTIFACT")
            return
        for index, line in enumerate(lines):
            if not line.strip():
                yield ParsedLegacyRow(f"jsonl:{index}", None, "EMPTY_JSONL_LINE")
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                yield ParsedLegacyRow(f"jsonl:{index}", None, "MALFORMED_JSON")
                continue
            yield ParsedLegacyRow(
                f"jsonl:{index}", value,
                "PARSED_OBJECT" if isinstance(value, dict) else "PARSED_NON_OBJECT",
            )
        return
    try:
        payload = json.loads(source.path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        yield ParsedLegacyRow("json-pointer:$document", None, "MALFORMED_JSON")
        return
    if not isinstance(payload, dict):
        yield ParsedLegacyRow("json-pointer:$document", payload, "PARSED_NON_OBJECT")
        return
    if source.source_type == "STRATEGY_MATRIX":
        scenarios = payload.get("scenarios") or []
        if not isinstance(scenarios, list) or not scenarios:
            yield ParsedLegacyRow(
                "json-pointer:/scenarios/$empty", None, "EMPTY_RESEARCH_ARTIFACT"
            )
            return
        for index, value in enumerate(scenarios):
            if isinstance(value, dict):
                yield ParsedLegacyRow(
                    f"json-pointer:/scenarios/{index}",
                    {
                        **value,
                        "_matrix_contract": payload.get("contract") or {},
                        "_matrix_inputs": payload.get("inputs") or {},
                    },
                    "PARSED_OBJECT",
                )
            else:
                yield ParsedLegacyRow(
                    f"json-pointer:/scenarios/{index}", value, "PARSED_NON_OBJECT"
                )
        return
    collection_name = next(
        (name for name in ("history", "runs", "rows") if name in payload), "rows"
    )
    rows = payload.get(collection_name, [])
    if not isinstance(rows, list):
        yield ParsedLegacyRow(
            f"json-pointer:/{collection_name}", rows, "NON_LIST_RESEARCH_COLLECTION"
        )
        return
    if not rows:
        yield ParsedLegacyRow(
            f"json-pointer:/{collection_name}/$empty", None, "EMPTY_RESEARCH_ARTIFACT"
        )
        return
    for index, value in enumerate(rows):
        yield ParsedLegacyRow(
            f"json-pointer:/{collection_name}/{index}", value,
            "PARSED_OBJECT" if isinstance(value, dict) else "PARSED_NON_OBJECT",
        )


def _mapping_authorities(corpus_root: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in sorted((corpus_root / "migration" / "authorities").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid legacy mapping authority: root must be object")
        errors = validate_legacy_mapping_authority(payload)
        if errors:
            raise ValueError("invalid legacy mapping authority: " + "; ".join(errors))
        authority_id = str(payload["authority_id"])
        if path.stem != authority_id.removeprefix("sha256:"):
            raise ValueError("LEGACY_MAPPING_AUTHORITY_PATH_IDENTITY_MISMATCH")
        key = (
            str(payload["source_artifact_id"]), str(payload["record_locator"]),
            str(payload["legacy_combo_id"]),
        )
        existing = result.get(key)
        if existing is not None and existing != payload:
            raise ValueError("LEGACY_MAPPING_AUTHORITY_COLLISION")
        result[key] = payload
    return result


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


def _canonical_receipts(corpus_root: Path) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    for path in sorted((corpus_root / "receipts").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            not isinstance(payload, dict) or validate_run_receipt(payload)
            or path.stem != str(payload.get("run_id") or "")
        ):
            continue
        receipts[str(payload["receipt_id"])] = payload
    return receipts


def _canonical_candidates(
    authority: dict[str, Any] | None,
    row: dict[str, Any],
    targets: dict[str, dict[str, Any]],
) -> tuple[str | None, str, list[str], list[str], list[dict[str, Any]], bool, str | None]:
    if authority is None:
        return None, "NOT_APPLICABLE", [], [], [], False, None
    mode = str(authority["mapping_mode"])
    confidence = str(authority["confidence"])
    reasons = list(authority["reason_codes"])
    authority_id = str(authority["authority_id"])
    refs = sorted(set([authority_id, *authority["evidence_refs"]]))
    candidates: list[dict[str, Any]] = []
    for raw in authority["candidates"]:
        if not isinstance(raw, dict):
            continue
        trial_id = str(raw.get("canonical_trial_spec_id") or "")
        if trial_id not in targets:
            continue
        target = targets[trial_id]
        if target.get("parameters") != _parameters(row):
            continue
        if row.get("topic_id") is not None and target.get("topic_id") != row.get("topic_id"):
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
            "evidence_refs": sorted(set([authority_id, *edge_refs])),
        })
    candidates.sort(key=lambda item: (item["combo_id"], item["canonical_trial_spec_id"]))
    unique = {(item["combo_id"], item["canonical_trial_spec_id"]): item for item in candidates}
    candidates = [unique[key] for key in sorted(unique)]
    all_targets_proven = authority["multi_target_resolution"] == "ALL_TARGETS_PROVEN"
    return mode, confidence, reasons, refs, candidates, all_targets_proven, authority_id


def _sealed_target_is_governed(
    *,
    authority: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    receipts: dict[str, dict[str, Any]],
) -> bool:
    if authority is None or not candidates:
        return False
    target_ids = {candidate["canonical_trial_spec_id"] for candidate in candidates}
    if any(targets[target_id].get("research_stage") != "SEALED_VALIDATION" for target_id in target_ids):
        return False
    governed: set[str] = set()
    for receipt_id in authority["governing_receipt_ids"]:
        receipt = receipts.get(receipt_id)
        if receipt is None:
            continue
        for unit in receipt.get("executed_units") or []:
            trial_id = unit.get("executed_trial_spec_id")
            if (
                trial_id in target_ids
                and unit.get("executed_research_stage") == "SEALED_VALIDATION"
                and unit.get("sealed_usage_status") == "SEALED"
            ):
                governed.add(str(trial_id))
    return governed == target_ids


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
    mapping_authority: dict[str, Any] | None = None,
    canonical_receipts: dict[str, dict[str, Any]] | None = None,
    parser_status: str = "PARSED_OBJECT",
) -> dict[str, Any]:
    targets = canonical_targets or {}
    if parser_status != "PARSED_OBJECT" or not isinstance(row, dict):
        disposition = (
            "LEGACY_UNRESOLVED" if parser_status == "MALFORMED_JSON"
            else "LEGACY_INCOMPLETE"
        )
        core = {
            "schema_version": "research-migrated-record.v2",
            "parser_version": PARSER_VERSION,
            "source": {"artifact_id": artifact_id, "source_type": source.source_type, "record_locator": locator},
            "record_kind": "UNRESOLVED_RECORD",
            "legacy_identity": {"combo_id": None, "topic_id": None, "scenario_id": None},
            "parameters": None,
            "metrics": None,
            "preliminary_classification": "INVALID_LINEAGE",
            "migration_disposition": disposition,
            "disposition_policy_version": DISPOSITION_POLICY,
            "inference_policy_version": "NOT_APPLICABLE",
            "confidence": "NOT_APPLICABLE",
            "reason_codes": [parser_status],
            "evidence_refs": [artifact_id],
            "mapping_authority_id": None,
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
        authority_id,
    ) = _canonical_candidates(mapping_authority, row, targets)
    authority_candidate_count = (
        len(mapping_authority["candidates"]) if mapping_authority is not None else 0
    )
    if mode == "EXCLUDE_NON_RESEARCH" and mapping_authority is not None:
        disposition = "EXCLUDED_NON_RESEARCH"
        disposition_confidence = "NOT_APPLICABLE"
        mapping_status = "UNMAPPED"
        kind = "NON_RESEARCH_RECORD"
        classification = "NOT_APPLICABLE_NON_OBSERVATION"
        parameters = None
        metrics = None
        semantic_id = None
        reasons = mapping_reasons
        inference_version = "NOT_APPLICABLE"
    elif (
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
    elif authority_candidate_count > 1 and not all_targets_proven:
        disposition = "LEGACY_UNRESOLVED"
        disposition_confidence = "NOT_APPLICABLE"
        mapping_status = "UNMAPPED"
        reasons = ["INVALID_OR_UNPROVEN_CANONICAL_TARGET_EVIDENCE"]
        inference_version = INFERENCE_POLICY
        candidates = []
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
    elif mapping_authority is not None:
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
        "mapping_authority_id": authority_id,
        "combo_mapping": {
            "mapping_status": mapping_status,
            "cardinality": "ZERO" if not candidates else "ONE" if len(candidates) == 1 else "ONE_TO_MANY",
            "candidates": candidates,
        },
        "semantic_evidence_id": semantic_id,
    }
    if kind == "PARAMETER_RESULT" and disposition in {"MIGRATED_EXACT", "MIGRATED_INFERRED"}:
        sealed_governed = _sealed_target_is_governed(
            authority=mapping_authority,
            candidates=candidates,
            targets=targets,
            receipts=canonical_receipts or {},
        )
        if sealed_governed:
            classification = "SEALED_VALIDATION_ONLY"
        else:
            classification = "LEGACY_DIAGNOSTIC_ONLY"
            if sealed_only:
                core_reason = "LEGACY_SEALED_CLAIM_NOT_GOVERNING"
                core["reason_codes"] = sorted(set([*core["reason_codes"], core_reason]))
        core["preliminary_classification"] = classification
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
    receipts = _canonical_receipts(corpus_root)
    authorities = _mapping_authorities(corpus_root)
    record_root = corpus_root / "migration" / "records"
    record_root.mkdir(parents=True, exist_ok=True)
    selected_sources = sources if sources is not None else discover_legacy_sources(legacy_root)
    for source in selected_sources:
        artifact_id, cas_path = publish_file_to_cas(corpus_root, source.path)
        located = list(_json_rows(source))
        records: list[dict[str, Any]] = []
        for located_row in located:
            combo_id = (
                str(located_row.value.get("combo_id") or "NOT_APPLICABLE")
                if isinstance(located_row.value, dict) else "NOT_APPLICABLE"
            )
            authority = authorities.get((artifact_id, located_row.locator, combo_id))
            records.append(map_record(
                source=source, artifact_id=artifact_id, locator=located_row.locator,
                row=located_row.value, canonical_targets=targets,
                mapping_authority=authority, canonical_receipts=receipts,
                parser_status=located_row.parser_status,
            ))
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


def ensure_current_migration(
    *, legacy_root: Path = DEFAULT_LEGACY_ROOT, corpus_root: Path = DEFAULT_CORPUS_ROOT,
) -> dict[str, Any]:
    """保留舊 manifest；僅在缺少目前 parser 的有效 manifest 時追加重建。"""

    manifest_dir = corpus_root / "migration" / "manifests"
    current: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(manifest_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("parser_version") != PARSER_VERSION:
            continue
        errors = validate_migration_manifest_v2(payload)
        if errors:
            raise ValueError("invalid current migration manifest: " + "; ".join(errors))
        current.append((path, payload))
    if current:
        path, manifest = current[-1]
        return {
            "action": "REUSED",
            "manifest": manifest,
            "manifest_path": path,
            "records": [],
        }
    result = build_migration(legacy_root=legacy_root, corpus_root=corpus_root)
    result["action"] = "BUILT"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build immutable legacy research migration corpus")
    parser.add_argument("--legacy-root", type=Path, default=DEFAULT_LEGACY_ROOT)
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument(
        "--ensure-current",
        action="store_true",
        help="目前 parser manifest 已存在時重用，否則以 append-only 方式建立",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    builder = ensure_current_migration if args.ensure_current else build_migration
    result = builder(legacy_root=args.legacy_root, corpus_root=args.corpus_root)
    counts = Counter(record["preliminary_classification"] for record in result["records"])
    print(json.dumps({
        "action": result.get("action", "BUILT"),
        "migration_id": result["manifest"]["migration_id"],
        "source_count": len(result["manifest"]["sources"]),
        "record_count": len(result["records"]),
        "classification_counts": dict(sorted(counts.items())),
        "manifest_path": str(result["manifest_path"]),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
