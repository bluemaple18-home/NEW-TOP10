"""發布 Card A search knowledge 與 PM-readable summary；不產queue。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

from app.research.contracts import content_hash
from app.research.eligibility import build_projection as build_eligibility
from app.research.failure_classification import build_projection as build_failure
from app.research.observation_ingest import DEFAULT_LEDGER_PATH, input_corpus_hash, ledger_snapshot
from app.research.parameter_catalog import load_parameter_catalog, parameter_catalog_hash
from app.research.parameter_learning import build_projection as build_learning
from app.research.receipt_store import write_immutable_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTO_ROOT = PROJECT_ROOT / "artifacts/autonomous_research"
CANONICAL_ROOT = AUTO_ROOT / "projections/search_knowledge"


def _atomic(path: Path, encoded: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _validator(payload: dict[str, Any]) -> list[str]:
    return [] if payload.get("schema_version") == "adaptive-search-knowledge.v1" else ["invalid schema"]


def _summary(knowledge: dict[str, Any]) -> str:
    funnel = knowledge["observation_funnel"]
    findings = knowledge["parameter_findings"]
    def selected(direction: str, edge: str | None = None) -> list[dict[str, Any]]:
        return [row for row in findings if row.get("direction") == direction and (edge is None or row.get("edge_behavior") == edge)]
    def names(rows: list[dict[str, Any]]) -> str:
        return "、".join(sorted({f"{row.get('parameter')} [{row.get('scope')}]" for row in rows})) or "目前不可判定"
    regimes = knowledge["regime_coverage"]
    single_regime = len(regimes) == 1
    lines = [
        "# Adaptive Learning Summary",
        "",
        f"- 狀態：`{knowledge['status']}`",
        "- Card B：`NOT_AUTHORIZED`",
        "",
        "## Q1 總歷史 records 有多少？",
        "",
        f"- Unique legacy records：{funnel['unique_legacy_records']}",
        f"- Legacy source record occurrences：{funnel['legacy_source_record_occurrences']}",
        f"- Native receipts：{funnel['native_receipts']}",
        f"- Native execution units：{funnel['native_execution_units']}",
        f"- Raw observations：{funnel['raw_result_observations']}",
        "",
        f"## Q2 ADAPTIVE_ELIGIBLE\n\n{funnel['adaptive_eligible']}",
        f"## Q3 LEGACY_DIAGNOSTIC_ONLY\n\n{funnel['legacy_diagnostic_only']}",
        f"## Q4 SEALED_VALIDATION_ONLY\n\n{funnel['sealed_validation_only']}",
        f"## Q5 哪些參數已有方向性？\n\n{names([row for row in findings if row.get('direction') in {'HIGHER_LOOKS_BETTER','LOWER_LOOKS_BETTER'}])}",
        f"## Q6 哪些參數可能太低？\n\n{names(selected('HIGHER_LOOKS_BETTER', 'BEST_AT_UPPER_BOUNDARY'))}",
        f"## Q7 哪些參數可能太高？\n\n{names(selected('LOWER_LOOKS_BETTER', 'BEST_AT_LOWER_BOUNDARY'))}",
        f"## Q8 哪些存在 interior peak？\n\n{names(selected('INTERIOR_PEAK'))}",
        f"## Q9 哪些 LOW_SENSITIVITY？\n\n{names([row for row in findings if 'LOW_SENSITIVITY' in row.get('flags', [])])}",
        f"## Q10 有哪些 robust basin？\n\n{knowledge['robust_regions'] or '目前不可判定'}",
        f"## Q11 有哪些 sharp peak？\n\n{knowledge['sharp_peaks'] or '目前不可判定'}",
        f"## Q12 evidence 是否主要集中於 RISK_OFF？\n\nRegimes：{regimes or '無 eligible regime evidence'}",
        f"## Q13 哪些結論禁止泛化？\n\n{'所有單一 regime findings；GLOBAL_NOT_ESTIMABLE。' if single_regime or not regimes else '依各 finding scope。'}",
        "",
        "## 安全界線",
        "",
        "- production ranking change：NO",
        "- production model change：NO",
        "- adaptive queue change：NO",
    ]
    return "\n".join(lines) + "\n"


def publish(*, run_date: str, ledger_path: Path = DEFAULT_LEDGER_PATH, output_root: Path = AUTO_ROOT) -> dict[str, Any]:
    eligibility = build_eligibility(ledger_path=ledger_path, output_root=output_root / "projections/eligibility")
    failure = build_failure(
        ledger_path=ledger_path, eligibility_output_root=output_root / "projections/eligibility",
        output_root=output_root / "projections/failure",
    )
    learning = build_learning(
        ledger_path=ledger_path, eligibility_output_root=output_root / "projections/eligibility",
        output_root=output_root / "projections/learning",
    )
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        snapshot = ledger_snapshot(connection)
        corpus_hash = input_corpus_hash(connection)
        native_receipts = connection.execute("SELECT count(*) FROM run_receipts").fetchone()[0]
        units = connection.execute("SELECT count(*) FROM execution_units").fetchone()[0]
        observations = connection.execute("SELECT count(*) FROM observations").fetchone()[0]
        unique_legacy_records = connection.execute("SELECT count(*) FROM migrated_records").fetchone()[0]
        legacy_occurrences = connection.execute("SELECT coalesce(sum(records_seen),0) FROM migration_sources").fetchone()[0]
    finally:
        connection.close()
    counts = Counter(eligibility["counts"])
    regimes = sorted({
        str(item.get("regime_id")) for item in learning["parameter_findings"]
        if item.get("scope") == "TOPIC_X_REGIME" and item.get("regime_id")
    })
    identity = {
        "schema_version": "adaptive-search-knowledge.v1", "as_of_date": run_date,
        "provenance": {
            "ledger_snapshot_hash": snapshot["snapshot_hash"], "input_corpus_hash": corpus_hash,
            "parameter_catalog_version": load_parameter_catalog()["schema_version"],
            "parameter_catalog_hash": parameter_catalog_hash(),
            "eligibility_projection_id": eligibility["projection_id"],
            "failure_projection_id": failure["projection_id"],
            "learning_projection_id": learning["projection_id"],
        },
        "observation_funnel": {
            "unique_legacy_records": int(unique_legacy_records),
            "legacy_source_record_occurrences": int(legacy_occurrences),
            "native_receipts": native_receipts,
            "native_execution_units": units, "raw_result_observations": observations,
            "deduplicated_evidence_units": observations,
            "adaptive_eligible": counts["ADAPTIVE_ELIGIBLE"],
            "legacy_diagnostic_only": counts["LEGACY_DIAGNOSTIC_ONLY"],
            "sealed_validation_only": counts["SEALED_VALIDATION_ONLY"],
            "topic_level_not_parameter_evidence": counts["TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE"],
            "unsupported_not_an_observation": counts["UNSUPPORTED_NOT_AN_OBSERVATION"],
            "invalid_lineage": counts["INVALID_LINEAGE"],
            "independent_matched_contrasts": learning["counts"]["matched_contrasts"],
        },
        "regime_coverage": regimes,
        "parameter_findings": learning["parameter_findings"],
        "interaction_findings": learning["interaction_findings"],
        "robust_regions": learning["robust_regions"],
        "sharp_peaks": [row for row in learning["parameter_findings"] if "SHARP_PEAK" in row.get("flags", [])],
        "failure_summary": failure["counts"],
        "limitations": [
            "Legacy lineage未證明者只供diagnostic", "單一regime不得泛化GLOBAL",
            "本卡不含Adaptive Queue、Optuna、Dynamic Refinement、Production promotion",
        ],
    }
    semantic_knowledge = {
        **identity,
        "status": learning["status"],
        "research_only_contract": {
            "does_not_train_model": True, "does_not_change_production_ranking": True,
            "production_promotion_allowed": False, "queue_change_allowed": False,
        },
        "next_phase_gate": {
            "card_b_allowed": False,
            "reason_codes": ["PM_APPROVAL_REQUIRED", *(["INSUFFICIENT_NATIVE_EVIDENCE"] if not counts["ADAPTIVE_ELIGIBLE"] else [])],
        },
    }
    knowledge_id = content_hash(semantic_knowledge)
    knowledge = {**semantic_knowledge, "knowledge_id": knowledge_id}
    canonical = output_root / "projections/search_knowledge" / f"{knowledge_id[7:]}.json"
    write_immutable_json(canonical, knowledge, validator=_validator)
    canonical_hash = "sha256:" + hashlib.sha256(canonical.read_bytes()).hexdigest()
    summary_bytes = _summary(knowledge).encode("utf-8")
    pointer = {
        "schema_version": "search-knowledge-pointer.v1", "as_of_date": run_date,
        "knowledge_id": knowledge_id,
        "artifact_path": canonical.relative_to(PROJECT_ROOT).as_posix() if canonical.is_relative_to(PROJECT_ROOT) else str(canonical),
        "artifact_hash": canonical_hash,
        "summary_hash": "sha256:" + hashlib.sha256(summary_bytes).hexdigest(),
    }
    encoded_pointer = (json.dumps(pointer, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    _atomic(output_root / f"search_knowledge_{run_date}.json", encoded_pointer)
    _atomic(output_root / "search_knowledge_latest.json", encoded_pointer)
    _atomic(output_root / f"adaptive_learning_summary_{run_date}.md", summary_bytes)
    return knowledge


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--output-root", type=Path, default=AUTO_ROOT)
    args = parser.parse_args()
    result = publish(run_date=args.date, ledger_path=args.ledger, output_root=args.output_root)
    print(json.dumps({"knowledge_id": result["knowledge_id"], "status": result["status"], "observation_funnel": result["observation_funnel"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
