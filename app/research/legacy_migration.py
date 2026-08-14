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
)
from app.research.receipt_store import publish_bytes_to_cas, publish_file_to_cas


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEGACY_ROOT = PROJECT_ROOT / "artifacts" / "autonomous_research"
DEFAULT_CORPUS_ROOT = DEFAULT_LEGACY_ROOT / "research_spine"
PARSER_VERSION = "legacy-research-parser.v1"
SEMANTIC_POLICY = "legacy-semantic-evidence.v1"
PRECLASSIFICATION_POLICY = "legacy-preclassification.v1"
AUTHORITY_ORDER_VERSION = "research-source-authority.v1"
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


def _json_rows(source: LegacySource) -> Iterable[tuple[str, dict[str, Any] | None]]:
    if source.source_type == "RUN_HISTORY_JSONL":
        for index, line in enumerate(source.path.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                value = json.loads(line)
                yield f"jsonl:{index}", value if isinstance(value, dict) else None
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
                yield f"json-pointer:/scenarios/{index}", None
        return
    rows = payload.get("history") or payload.get("runs") or payload.get("rows") or []
    if isinstance(rows, list):
        for index, value in enumerate(rows):
            yield f"json-pointer:/rows/{index}", value if isinstance(value, dict) else None


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
    *, source: LegacySource, artifact_id: str, locator: str, row: dict[str, Any]
) -> dict[str, Any]:
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
    core = {
        "schema_version": "research-migrated-record.v1",
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
        "reason_codes": reasons,
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
    record_root = corpus_root / "migration" / "records"
    record_root.mkdir(parents=True, exist_ok=True)
    for source in sources or discover_legacy_sources(legacy_root):
        artifact_id, cas_path = publish_file_to_cas(corpus_root, source.path)
        located = list(_json_rows(source))
        records = [
            map_record(source=source, artifact_id=artifact_id, locator=locator, row=row)
            for locator, row in located if row is not None
        ]
        excluded = sum(row is None for _, row in located)
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
        reasons = Counter(reason for record in records for reason in record["reason_codes"])
        entry = {
                "source_artifact_hash": artifact_id,
                "corpus_artifact_path": cas_path.relative_to(corpus_root).as_posix(),
                "source_type": source.source_type,
                "parser_version": PARSER_VERSION,
                "record_mapping_path": mapping_path.relative_to(corpus_root).as_posix(),
                "record_mapping_hash": mapping_id,
                "record_counts": {
                    "seen": len(located), "mapped": len(records), "excluded": excluded
                },
                "classification_counts": dict(sorted(classifications.items())),
                "reason_code_counts": dict(sorted(reasons.items())),
            }
        existing = source_entries_by_artifact.get(artifact_id)
        if existing is not None and existing != entry:
            raise ValueError("same source bytes produced inconsistent mapping")
        source_entries_by_artifact[artifact_id] = entry
        all_records.extend(records)
    identity = {
        "schema_version": "research-ledger-migration-manifest.v2",
        "parser_version": PARSER_VERSION,
        "semantic_identity_policy_version": SEMANTIC_POLICY,
        "eligibility_preclassification_policy_version": PRECLASSIFICATION_POLICY,
        "source_authority_order_version": AUTHORITY_ORDER_VERSION,
        "duplicate_policy": "SEMANTIC_EVIDENCE_DEWEIGHT",
        "conflict_policy": "FAIL_CLOSED_NO_WINNER",
        "sources": sorted(
            source_entries_by_artifact.values(), key=lambda item: item["source_artifact_hash"]
        ),
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
