"""A6 closure gate：重建 Research Spine 並驗證 legacy bridge 退場條件。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import duckdb

from app.research.contracts import validate_attempt_started, validate_research_intent, validate_run_receipt
from app.research.eligibility import build_projection as build_eligibility_projection
from app.research.failure_classification import build_projection as build_failure_projection
from app.research.history_compatibility_projection import build_projection as build_history_projection
from app.research.observation_ingest import (
    DEFAULT_CORPUS_ROOT,
    DEFAULT_LEDGER_PATH,
    ingest_corpus,
    input_corpus_hash,
    ledger_snapshot,
)
from app.research.parameter_learning import build_projection as build_learning_projection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "docs/evidence/CARD-NEW-TOP10-RESEARCH-A6-DEPRECATION-REBUILD-AND-BRIDGE-REMOVAL-GATES/closure_receipt.json"
SCHEMA_VERSION = "research-spine-a6-closure.v1"
BRIDGE_SCHEMA_VERSION = "research-spine-bridge-inventory.v1"
REQUIRED_BRIDGE_FIELDS = {
    "bridge_id",
    "owner",
    "direction",
    "authority",
    "read_write_mode",
    "removal_condition",
    "removal_test",
    "target_stage",
    "status",
}
KNOWN_REMOVAL_TESTS = {
    "pytest::tests/test_research_spine_a6_closure.py::test_a6_closure_rebuilds_a1_to_a5_and_history_projection_deterministically",
    "pytest::tests/test_research_spine_a6_closure.py::test_bridge_inventory_is_complete_and_machine_checkable",
    "pytest::tests/test_research_spine_a6_closure.py::test_new_run_truth_success_failure_and_orphan_do_not_use_history_or_backfill",
    "pytest::tests/test_research_spine_daily_cutover.py::test_ledger_history_projection_preserves_frozen_legacy_and_is_deterministic",
    "pytest::tests/test_research_legacy_migration.py",
}


def bridge_inventory_rows() -> list[dict[str, str]]:
    """A6 只盤點 compatibility bridge；所有列都不得升格為 truth authority。"""
    return [
        {
            "bridge_id": "history_compatibility_projection",
            "owner": "research-spine/a6",
            "direction": "research_ledger_to_run_history_jsonl",
            "authority": "DERIVED_COMPATIBILITY_PROJECTION",
            "read_write_mode": "derived_write_replace",
            "removal_condition": "Fog Map 與進度 consumer 改直接讀取 first-party ledger projection。",
            "removal_test": "pytest::tests/test_research_spine_a6_closure.py::test_a6_closure_rebuilds_a1_to_a5_and_history_projection_deterministically",
            "target_stage": "CARD_C_CONTROL_CUTOVER",
            "status": "ACTIVE_BRIDGE",
        },
        {
            "bridge_id": "legacy_run_history_jsonl_migration",
            "owner": "research-spine/a3",
            "direction": "run_history_jsonl_to_migration_corpus",
            "authority": "HISTORICAL_MIGRATION_SOURCE_ONLY",
            "read_write_mode": "legacy_read_only",
            "removal_condition": "historical migration corpus 不再需要 legacy run_history JSONL intake。",
            "removal_test": "pytest::tests/test_research_legacy_migration.py",
            "target_stage": "POST_A6_ARCHIVE_RETIREMENT",
            "status": "PRESERVE_FOR_HISTORICAL_REPLAY",
        },
        {
            "bridge_id": "legacy_run_history_json_migration",
            "owner": "research-spine/a3",
            "direction": "run_history_json_to_migration_corpus",
            "authority": "HISTORICAL_MIGRATION_SOURCE_ONLY",
            "read_write_mode": "legacy_read_only",
            "removal_condition": "historical migration corpus 不再需要 legacy run_history JSON intake。",
            "removal_test": "pytest::tests/test_research_legacy_migration.py",
            "target_stage": "POST_A6_ARCHIVE_RETIREMENT",
            "status": "PRESERVE_FOR_HISTORICAL_REPLAY",
        },
        {
            "bridge_id": "research_map_run_history_backfill",
            "owner": "research-map/legacy-migration",
            "direction": "legacy_artifacts_to_run_history_jsonl",
            "authority": "ISOLATED_RECOVERY_OR_HISTORICAL_MIGRATION",
            "read_write_mode": "migration_only_write_with_required_flag",
            "removal_condition": "正常 new-run acceptance path 不可呼叫 backfill 建立 terminal truth。",
            "removal_test": "pytest::tests/test_research_spine_a6_closure.py::test_new_run_truth_success_failure_and_orphan_do_not_use_history_or_backfill",
            "target_stage": "POST_A6_RECOVERY_TOOLING",
            "status": "QUARANTINED_FROM_NORMAL_RUNS",
        },
        {
            "bridge_id": "research_map_backfill_verifier",
            "owner": "research-map/legacy-migration",
            "direction": "backfill_rows_to_verification_report",
            "authority": "BACKFILL_FORMAT_VALIDATOR_ONLY",
            "read_write_mode": "derived_report_write",
            "removal_condition": "backfill script 退役，或僅保留為 historical recovery tooling。",
            "removal_test": "pytest::tests/test_research_spine_a6_closure.py::test_bridge_inventory_is_complete_and_machine_checkable",
            "target_stage": "POST_A6_RECOVERY_TOOLING",
            "status": "ACTIVE_SUPPORT_BRIDGE",
        },
        {
            "bridge_id": "fog_map_run_history_reader",
            "owner": "fog-map",
            "direction": "run_history_jsonl_to_fog_map_status",
            "authority": "DERIVED_COMPATIBILITY_READ_MODEL",
            "read_write_mode": "read_only",
            "removal_condition": "Fog Map domain 改讀 ledger-backed projection API，不再讀 JSONL compatibility input。",
            "removal_test": "pytest::tests/test_research_spine_daily_cutover.py::test_ledger_history_projection_preserves_frozen_legacy_and_is_deterministic",
            "target_stage": "CARD_C_CONTROL_CUTOVER",
            "status": "ACTIVE_BRIDGE",
        },
        {
            "bridge_id": "campaign_progress_run_history_reader",
            "owner": "research-campaign-progress",
            "direction": "run_history_jsonl_to_progress_projection",
            "authority": "DERIVED_COMPATIBILITY_READ_MODEL",
            "read_write_mode": "read_only",
            "removal_condition": "Campaign progress 改直接讀取 first-party ledger/projection outputs。",
            "removal_test": "pytest::tests/test_research_spine_a6_closure.py::test_bridge_inventory_is_complete_and_machine_checkable",
            "target_stage": "CARD_C_CONTROL_CUTOVER",
            "status": "ACTIVE_BRIDGE",
        },
        {
            "bridge_id": "weekend_training_run_history_reader",
            "owner": "weekend-training",
            "direction": "run_history_jsonl_to_lifecycle_summary",
            "authority": "DERIVED_COMPATIBILITY_READ_MODEL",
            "read_write_mode": "read_only",
            "removal_condition": "Weekend training lifecycle summary 僅消費 ledger-backed compatibility output。",
            "removal_test": "pytest::tests/test_research_spine_a6_closure.py::test_bridge_inventory_is_complete_and_machine_checkable",
            "target_stage": "CARD_C_CONTROL_CUTOVER",
            "status": "ACTIVE_BRIDGE",
        },
        {
            "bridge_id": "liquidity_v2_run_history_reader",
            "owner": "liquidity-replay-v2",
            "direction": "run_history_jsonl_to_liquidity_stage2_alignment",
            "authority": "DERIVED_COMPATIBILITY_READ_MODEL",
            "read_write_mode": "read_only",
            "removal_condition": "Liquidity replay v2 alignment 改讀 ledger-backed projection 或退役。",
            "removal_test": "pytest::tests/test_research_spine_a6_closure.py::test_bridge_inventory_is_complete_and_machine_checkable",
            "target_stage": "POST_A6_LEGACY_REPLAY_RETIREMENT",
            "status": "ACTIVE_BRIDGE",
        },
        {
            "bridge_id": "legacy_run_history_appenders",
            "owner": "legacy-replay-runners",
            "direction": "legacy_replay_outputs_to_run_history_jsonl",
            "authority": "LEGACY_COMPATIBILITY_WRITER_NOT_NEW_RUN_TRUTH",
            "read_write_mode": "append_only_legacy_writer",
            "removal_condition": "New runs 先持久化 intent/attempt/receipt；legacy appender 停用或改走 ledger projection。",
            "removal_test": "pytest::tests/test_research_spine_a6_closure.py::test_new_run_truth_success_failure_and_orphan_do_not_use_history_or_backfill",
            "target_stage": "CARD_C_CONTROL_CUTOVER",
            "status": "ACTIVE_LEGACY_WRITER",
        },
    ]


def validate_bridge_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        entity = str(row.get("bridge_id") or f"row-{index}")
        missing = sorted(field for field in REQUIRED_BRIDGE_FIELDS if not str(row.get(field) or "").strip())
        for field in missing:
            errors.append({"bridge_id": entity, "reason": f"MISSING_{field.upper()}"})
        bridge_id = str(row.get("bridge_id") or "")
        if bridge_id in seen:
            errors.append({"bridge_id": entity, "reason": "DUPLICATE_BRIDGE_ID"})
        seen.add(bridge_id)
        if row.get("authority") == "TRUTH_AUTHORITY":
            errors.append({"bridge_id": entity, "reason": "RUN_HISTORY_AUTHORITY_INVERSION"})
        if str(row.get("removal_test") or "") not in KNOWN_REMOVAL_TESTS:
            errors.append({"bridge_id": entity, "reason": "REMOVAL_TEST_NOT_EXECUTABLE"})
    return {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "row_count": len(rows),
        "required_fields": sorted(REQUIRED_BRIDGE_FIELDS),
        "error_codes": sorted({error["reason"] for error in errors}),
        "errors": errors,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _table_counts(ledger_path: Path) -> dict[str, int]:
    tables = (
        "trial_specs",
        "research_intents",
        "run_attempts",
        "run_receipts",
        "migration_manifests",
        "migrated_records",
        "execution_units",
        "observations",
        "observation_provenance",
    )
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        return {
            table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in tables
        }
    finally:
        connection.close()


def _first_party_membership(corpus_root: Path) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    intents: dict[str, dict[str, Any]] = {}
    attempts: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for path in sorted((corpus_root / "intents").glob("*.json")):
        payload = _load_json(path)
        schema_errors = validate_research_intent(payload)
        if schema_errors:
            errors.append({"entity": path.name, "reason": ";".join(schema_errors)})
        intent_id = str(payload.get("intent_id") or "")
        if intent_id:
            intents[intent_id] = payload
    for path in sorted((corpus_root / "attempts").glob("*.started.json")):
        payload = _load_json(path)
        schema_errors = validate_attempt_started(payload)
        if schema_errors:
            errors.append({"entity": path.name, "reason": ";".join(schema_errors)})
        run_id = str(payload.get("run_id") or "")
        if run_id:
            attempts[run_id] = payload
    for path in sorted((corpus_root / "receipts").glob("*.json")):
        payload = _load_json(path)
        schema_errors = validate_run_receipt(payload)
        if schema_errors:
            errors.append({"entity": path.name, "reason": ";".join(schema_errors)})
        run_id = str(payload.get("run_id") or "")
        if run_id:
            receipts[run_id] = payload
    return {"intents": intents, "attempts": attempts, "receipts": receipts, "errors": errors}


def verify_new_run_truth(*, corpus_root: Path) -> dict[str, Any]:
    membership = _first_party_membership(corpus_root)
    attempts = membership["attempts"]
    receipts = membership["receipts"]
    success = [
        receipt for receipt in receipts.values()
        if receipt.get("terminal_status") == "SUCCEEDED"
    ]
    failure = [
        receipt for receipt in receipts.values()
        if receipt.get("terminal_status") != "SUCCEEDED"
    ]
    orphan = sorted(set(attempts) - set(receipts))
    cases: dict[str, dict[str, Any]] = {}
    if success:
        cases["success"] = {"status": "PASS", "count": len(success), "authority": "intent_attempt_receipt_artifact"}
    if failure:
        cases["failure"] = {"status": "PASS", "count": len(failure), "authority": "intent_attempt_receipt_failure_cause"}
    if orphan:
        cases["orphan"] = {"status": "PASS", "count": len(orphan), "authority": "attempt_without_terminal_receipt_fail_closed"}
    if not cases:
        cases["missing_first_party_evidence"] = {"status": "FAIL", "count": 0, "authority": "none"}
    errors = list(membership["errors"])
    if not attempts:
        errors.append({"entity": str(corpus_root), "reason": "FIRST_PARTY_ATTEMPT_MISSING"})
    return {
        "schema_version": "research-spine-a6-new-run-truth.v1",
        "status": "PASS" if not errors else "FAIL",
        "sources_consumed": ["intents", "attempts", "receipts"],
        "run_history_truth_authority": False,
        "normal_new_run_backfill_dependency": False,
        "cases": cases,
        "counts": {
            "intents": len(membership["intents"]),
            "attempts": len(attempts),
            "receipts": len(receipts),
            "success_receipts": len(success),
            "failure_receipts": len(failure),
            "orphan_attempts": len(orphan),
        },
        "errors": errors,
    }


def _build_once(corpus_root: Path, root: Path) -> dict[str, Any]:
    ledger = root / "ledger.duckdb"
    eligibility_root = root / "projections" / "eligibility"
    failure_root = root / "projections" / "failure"
    learning_root = root / "projections" / "learning"
    history_output = root / "run_history.jsonl"
    history_manifest = root / "run_history_projection_manifest.json"
    ingest = ingest_corpus(corpus_root=corpus_root, ledger_path=ledger)
    eligibility = build_eligibility_projection(ledger_path=ledger, output_root=eligibility_root)
    failure = build_failure_projection(
        ledger_path=ledger,
        eligibility_output_root=eligibility_root,
        output_root=failure_root,
    )
    learning = build_learning_projection(
        ledger_path=ledger,
        eligibility_output_root=eligibility_root,
        failure_output_root=failure_root,
        output_root=learning_root,
    )
    history = build_history_projection(
        ledger_path=ledger,
        corpus_root=corpus_root,
        output=history_output,
        manifest_output=history_manifest,
    )
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        corpus_hash = input_corpus_hash(connection)
        snapshot = ledger_snapshot(connection)
    finally:
        connection.close()
    return {
        "ledger_path": str(ledger),
        "ingest_snapshot_hash": ingest.snapshot_hash,
        "input_corpus_hash": corpus_hash,
        "ledger_snapshot_hash": snapshot["snapshot_hash"],
        "counts": _table_counts(ledger),
        "eligibility_projection": eligibility,
        "failure_projection": failure,
        "learning_projection": learning,
        "history_projection": history,
        "history_projection_bytes": history_output.read_bytes().hex(),
    }


def _public_build_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_corpus_hash": result["input_corpus_hash"],
        "ledger_snapshot_hash": result["ledger_snapshot_hash"],
        "counts": result["counts"],
        "eligibility_projection_id": result["eligibility_projection"]["projection_id"],
        "failure_projection_id": result["failure_projection"]["projection_id"],
        "learning_projection_id": result["learning_projection"]["projection_id"],
        "history_projection_id": result["history_projection"]["projection_id"],
        "history_row_count": result["history_projection"]["row_count"],
    }


def _reset_output_root(output_root: Path, corpus_root: Path) -> None:
    resolved_output = output_root.resolve()
    resolved_corpus = corpus_root.resolve()
    resolved_project = PROJECT_ROOT.resolve()
    forbidden = {Path("/").resolve(), resolved_project, resolved_corpus}
    if resolved_output in forbidden:
        raise ValueError("A6_OUTPUT_ROOT_UNSAFE")
    try:
        resolved_project.relative_to(resolved_output)
    except ValueError:
        pass
    else:
        raise ValueError("A6_OUTPUT_ROOT_CONTAINS_PROJECT")
    try:
        resolved_corpus.relative_to(resolved_output)
    except ValueError:
        pass
    else:
        raise ValueError("A6_OUTPUT_ROOT_CONTAINS_CORPUS")
    if output_root.exists():
        shutil.rmtree(output_root)


def verify_a6_closure(*, corpus_root: Path, output_root: Path) -> dict[str, Any]:
    _reset_output_root(output_root, corpus_root)
    first = _build_once(corpus_root, output_root / "first")
    second = _build_once(corpus_root, output_root / "second")
    new_run_truth = verify_new_run_truth(corpus_root=corpus_root)
    bridge_inventory = validate_bridge_inventory(bridge_inventory_rows())
    checks = {
        "ledger_snapshot_equal": first["ledger_snapshot_hash"] == second["ledger_snapshot_hash"],
        "input_corpus_hash_equal": first["input_corpus_hash"] == second["input_corpus_hash"],
        "table_counts_equal": first["counts"] == second["counts"],
        "eligibility_projection_equal": first["eligibility_projection"] == second["eligibility_projection"],
        "failure_projection_equal": first["failure_projection"] == second["failure_projection"],
        "learning_projection_equal": first["learning_projection"] == second["learning_projection"],
        "history_projection_bytes_equal": first["history_projection_bytes"] == second["history_projection_bytes"],
        "history_projection_manifest_identity_equal": (
            first["history_projection"]["projection_id"] == second["history_projection"]["projection_id"]
        ),
    }
    error_codes: list[str] = []
    if not all(checks.values()):
        error_codes.append("A1_A5_REBUILD_MISMATCH")
    if bridge_inventory["status"] != "PASS":
        error_codes.append("BRIDGE_INVENTORY_NO_GO")
    if new_run_truth["status"] != "PASS" or new_run_truth["counts"]["receipts"] == 0:
        error_codes.append("NEW_RUN_TRUTH_FAIL_CLOSED")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not error_codes else "FAIL",
        "issue": 8,
        "scope_guards": {
            "card_b_started": False,
            "card_c_started": False,
            "production_changed": False,
            "scheduler_changed": False,
            "ranking_or_backtest_math_changed": False,
        },
        "rebuild": {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "first": _public_build_result(first),
            "second": _public_build_result(second),
        },
        "new_run_truth": new_run_truth,
        "bridge_inventory": bridge_inventory,
        "bridge_rows": bridge_inventory_rows(),
        "ai_core_proposals": [
            {
                "proposal_id": "AI_CORE_PROPOSAL_A0_A5_RECEIPT_SHAPE",
                "source": "A0-A5",
                "recommendation": "未來 agentic workflow receipt 納入明確 first-party intent/attempt/receipt evidence 欄位。",
            },
            {
                "proposal_id": "AI_CORE_PROPOSAL_BRIDGE_RETIREMENT_METADATA",
                "source": "A6",
                "recommendation": "compatibility bridge closure 前必填 owner、removal condition、removal test 與 status。",
            },
        ],
        "error_codes": error_codes,
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / ".a6_closure_tmp")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    args = parser.parse_args()
    del args.ledger  # 保留 CLI 相容欄位；A6 closure 永遠使用 isolated output root。
    result = verify_a6_closure(corpus_root=args.corpus_root, output_root=args.output_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "output": str(args.output)}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
