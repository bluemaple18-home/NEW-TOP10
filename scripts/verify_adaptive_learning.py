#!/usr/bin/env python3
"""Card A final verifier：驗證knowledge、sealed隔離、PM Q1-Q13與production safety。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from app.research.contracts import content_hash
from app.research.knowledge_artifacts import _summary
from app.research.observation_ingest import input_corpus_hash, ledger_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def verify(*, run_date: str, ledger: Path, output_root: Path) -> dict:
    errors = []
    pointer_path = output_root / f"search_knowledge_{run_date}.json"
    latest_path = output_root / "search_knowledge_latest.json"
    summary_path = output_root / f"adaptive_learning_summary_{run_date}.md"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "schema_version": "adaptive-learning-verification.v1", "status": "FAIL",
            "date": run_date, "knowledge_id": None, "observation_funnel": {},
            "errors": [f"POINTER_READ_ERROR:{type(error).__name__}"],
        }
    if pointer != latest:
        errors.append("DATED_LATEST_POINTER_MISMATCH")
    artifact_path = Path(str(pointer.get("artifact_path") or ""))
    canonical = PROJECT_ROOT / artifact_path if not artifact_path.is_absolute() else artifact_path
    expected_root = (output_root / "projections/search_knowledge").resolve()
    try:
        canonical = canonical.resolve()
        canonical.relative_to(expected_root)
    except ValueError:
        errors.append("CANONICAL_KNOWLEDGE_PATH_OUTSIDE_EXPECTED_ROOT")
    if not canonical.is_file() or "sha256:" + hashlib.sha256(canonical.read_bytes()).hexdigest() != pointer.get("artifact_hash"):
        errors.append("CANONICAL_KNOWLEDGE_HASH_MISMATCH")
        knowledge = {}
    else:
        try:
            knowledge = json.loads(canonical.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            knowledge = {}
            errors.append("CANONICAL_KNOWLEDGE_JSON_INVALID")
    knowledge_id = str(knowledge.get("knowledge_id") or "")
    if knowledge and knowledge_id != content_hash(knowledge, omit={"knowledge_id"}):
        errors.append("KNOWLEDGE_IDENTITY_MISMATCH")
    if canonical.stem != knowledge_id.removeprefix("sha256:") or pointer.get("knowledge_id") != knowledge_id:
        errors.append("KNOWLEDGE_PATH_OR_POINTER_IDENTITY_MISMATCH")
    if knowledge.get("research_only_contract") != {
        "does_not_train_model": True, "does_not_change_production_ranking": True,
        "production_promotion_allowed": False, "queue_change_allowed": False,
    }:
        errors.append("RESEARCH_ONLY_CONTRACT_INVALID")
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        current_snapshot_hash = ledger_snapshot(connection)["snapshot_hash"]
        current_corpus_hash = input_corpus_hash(connection)
        leaked = connection.execute(
            """SELECT count(*) FROM eligibility_decisions e
               JOIN execution_units u ON u.execution_unit_id IN (
                 SELECT execution_unit_id FROM observations WHERE observation_id=e.subject_id)
               WHERE e.subject_type='OBSERVATION' AND e.eligibility_status='ADAPTIVE_ELIGIBLE'
                 AND u.sealed_usage_status!='PROVEN_NON_SEALED'"""
        ).fetchone()[0]
    finally:
        connection.close()
    if leaked:
        errors.append("SEALED_OR_UNKNOWN_ELIGIBILITY_LEAK")
    provenance = knowledge.get("provenance") or {}
    if provenance.get("ledger_snapshot_hash") != current_snapshot_hash:
        errors.append("KNOWLEDGE_LEDGER_SNAPSHOT_STALE")
    if provenance.get("input_corpus_hash") != current_corpus_hash:
        errors.append("KNOWLEDGE_INPUT_CORPUS_STALE")
    try:
        summary = summary_path.read_text(encoding="utf-8")
    except OSError:
        summary = ""
        errors.append("PM_SUMMARY_MISSING")
    expected_summary = _summary(knowledge) if knowledge else ""
    if summary != expected_summary:
        errors.append("PM_SUMMARY_CONTENT_MISMATCH")
    if "sha256:" + hashlib.sha256(summary.encode("utf-8")).hexdigest() != pointer.get("summary_hash"):
        errors.append("PM_SUMMARY_HASH_MISMATCH")
    for number in range(1, 14):
        if f"Q{number} " not in summary:
            errors.append(f"PM_SUMMARY_Q{number}_MISSING")
    forbidden = [
        output_root / "adaptive_queue_latest.json",
        PROJECT_ROOT / "models/latest_lgbm.pkl.adaptive",
    ]
    if any(path.exists() for path in forbidden):
        errors.append("FORBIDDEN_ADAPTIVE_OR_PRODUCTION_ARTIFACT")
    return {
        "schema_version": "adaptive-learning-verification.v1",
        "status": "PASS" if not errors else "FAIL",
        "date": run_date, "knowledge_id": knowledge.get("knowledge_id"),
        "observation_funnel": knowledge.get("observation_funnel", {}), "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--ledger", type=Path, default=PROJECT_ROOT / "data/research/research_ledger.duckdb")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "artifacts/autonomous_research")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(run_date=args.date, ledger=args.ledger, output_root=args.output_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
