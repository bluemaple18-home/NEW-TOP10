"""A6 closure gate：重建 Research Spine 並驗證 legacy bridge 退場條件。"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import tempfile
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
DEFAULT_TEMP_OUTPUT = Path(tempfile.gettempdir()) / "new-top10-a6-closure-output"
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
SOURCE_DERIVED_BRIDGE_SURFACES = {
    "history_compatibility_projection": ("app/research/history_compatibility_projection.py", "run_history.jsonl"),
    "legacy_run_history_jsonl_migration": ("app/research/legacy_migration.py", "RUN_HISTORY_JSONL"),
    "legacy_run_history_json_migration": ("app/research/legacy_migration.py", "RUN_HISTORY_JSON"),
    "research_map_run_history_backfill": ("scripts/backfill_research_map_run_history.py", "run_history.jsonl"),
    "research_map_backfill_verifier": ("scripts/verify_research_map_run_history_backfill.py", "backfill_rows"),
    "fog_map_run_history_reader": ("app/research/fog_map_domain.py", "apply_run_history"),
    "campaign_progress_run_history_reader": ("scripts/build_research_campaign_progress.py", "apply_run_history"),
    "weekend_training_run_history_reader": ("scripts/weekend_training_common.py", "apply_run_history"),
    "liquidity_v2_run_history_reader": ("scripts/build_liquidity_replay_v2_stage2.py", "RUN_HISTORY_PATH"),
    "legacy_run_history_appenders": ("scripts/run_weekend_representative_replay.py", "append_history"),
    "liquidity_v2_batch_run_history_bridge": ("scripts/run_liquidity_replay_v2_batch.py", "RUN_HISTORY_PATH"),
    "research_fog_map_verifier_reader": ("scripts/verify_research_fog_map.py", "run_history"),
    "combo_effectiveness_run_history_reader": ("scripts/build_5913_combo_effectiveness_review.py", "RUN_HISTORY_PATH"),
}
SOURCE_SURFACE_MANIFEST = {
    "app/research/contracts.py": "legacy_run_history_jsonl_migration",
    "app/research/batch_owner.py": "legacy_run_history_appenders",
    "app/research/fog_map_domain.py": "fog_map_run_history_reader",
    "app/research/fog_map_render.py": "fog_map_run_history_reader",
    "app/research/history_compatibility_projection.py": "history_compatibility_projection",
    "app/research/legacy_migration.py": "legacy_run_history_jsonl_migration",
    "app/research/map_contract.py": "fog_map_run_history_reader",
    "app/research/observation_ingest.py": "legacy_run_history_jsonl_migration",
    "scripts/backfill_research_map_run_history.py": "research_map_run_history_backfill",
    "scripts/build_5913_combo_effectiveness_review.py": "combo_effectiveness_run_history_reader",
    "scripts/build_liquidity_replay_v2_stage2.py": "liquidity_v2_run_history_reader",
    "scripts/build_research_campaign_progress.py": "campaign_progress_run_history_reader",
    "scripts/build_research_fog_map.py": "fog_map_run_history_reader",
    "scripts/build_weekend_readiness_audit.py": "weekend_training_run_history_reader",
    "scripts/build_weekend_universe_inventory.py": "weekend_training_run_history_reader",
    "scripts/fog_authority_contracts.py": "fog_map_run_history_reader",
    "scripts/research_map_linkage_smoke.py": "research_map_run_history_backfill",
    "scripts/run_autonomous_research.py": "legacy_run_history_appenders",
    "scripts/run_controlled_grid_drain_host_runner.py": "legacy_run_history_appenders",
    "scripts/run_liquidity_replay_v2_batch.py": "liquidity_v2_batch_run_history_bridge",
    "scripts/run_representative_replay_drain_worker.py": "legacy_run_history_appenders",
    "scripts/run_top10_fog_map_handoff.py": "fog_map_run_history_reader",
    "scripts/run_weekend_representative_replay.py": "legacy_run_history_appenders",
    "scripts/run_weekend_survivor_deep_replay.py": "legacy_run_history_appenders",
    "scripts/verify_autonomous_research.py": "legacy_run_history_appenders",
    "scripts/verify_feature_group_regime_walkforward.py": "legacy_run_history_appenders",
    "scripts/verify_liquidity_replay_v2_batch.py": "liquidity_v2_run_history_reader",
    "scripts/verify_research_fog_map.py": "research_fog_map_verifier_reader",
    "scripts/verify_research_map_run_history_backfill.py": "research_map_backfill_verifier",
    "scripts/verify_research_map_v2_schema.py": "fog_map_run_history_reader",
    "scripts/verify_weekend_representative_replay.py": "legacy_run_history_appenders",
    "scripts/weekend_training_common.py": "weekend_training_run_history_reader",
}
REMOVAL_TEST_MODULE = "tests/test_research_spine_a6_bridge_removals.py"


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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_history_compatibility_projection_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_legacy_run_history_jsonl_migration_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_legacy_run_history_json_migration_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_research_map_run_history_backfill_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_research_map_backfill_verifier_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_fog_map_run_history_reader_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_campaign_progress_run_history_reader_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_weekend_training_run_history_reader_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_liquidity_v2_run_history_reader_removal_evidence",
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
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_legacy_run_history_appenders_removal_evidence",
            "target_stage": "CARD_C_CONTROL_CUTOVER",
            "status": "ACTIVE_LEGACY_WRITER",
        },
        {
            "bridge_id": "liquidity_v2_batch_run_history_bridge",
            "owner": "liquidity-replay-v2",
            "direction": "run_history_jsonl_to_and_from_liquidity_batch",
            "authority": "DERIVED_COMPATIBILITY_READ_WRITE",
            "read_write_mode": "legacy_read_append_only",
            "removal_condition": "Liquidity v2 batch 改用 ledger-backed compatibility projection。",
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_liquidity_v2_batch_run_history_bridge_removal_evidence",
            "target_stage": "POST_A6_LEGACY_REPLAY_RETIREMENT",
            "status": "ACTIVE_LEGACY_WRITER",
        },
        {
            "bridge_id": "research_fog_map_verifier_reader",
            "owner": "fog-map",
            "direction": "run_history_jsonl_to_fog_map_verification",
            "authority": "DERIVED_COMPATIBILITY_READ_MODEL",
            "read_write_mode": "read_only",
            "removal_condition": "Fog Map verifier 改讀 ledger-backed projection。",
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_research_fog_map_verifier_reader_removal_evidence",
            "target_stage": "CARD_C_CONTROL_CUTOVER",
            "status": "ACTIVE_BRIDGE",
        },
        {
            "bridge_id": "combo_effectiveness_run_history_reader",
            "owner": "research-effectiveness-review",
            "direction": "run_history_jsonl_to_combo_effectiveness_review",
            "authority": "DERIVED_COMPATIBILITY_READ_MODEL",
            "read_write_mode": "read_only",
            "removal_condition": "5913 effectiveness review 改讀 ledger-backed projection 或退役。",
            "removal_test": f"{REMOVAL_TEST_MODULE}::test_combo_effectiveness_run_history_reader_removal_evidence",
            "target_stage": "POST_A6_LEGACY_REPLAY_RETIREMENT",
            "status": "ACTIVE_BRIDGE",
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
        if not _removal_test_exists(str(row.get("removal_test") or ""), bridge_id):
            errors.append({"bridge_id": entity, "reason": "REMOVAL_TEST_NOT_EXECUTABLE"})
    expected_ids = set(SOURCE_DERIVED_BRIDGE_SURFACES)
    actual_ids = {str(row.get("bridge_id") or "") for row in rows}
    for bridge_id in sorted(expected_ids - actual_ids):
        errors.append({"bridge_id": bridge_id, "reason": "MISSING_SOURCE_BRIDGE"})
    for bridge_id, (relative_path, marker) in SOURCE_DERIVED_BRIDGE_SURFACES.items():
        source = PROJECT_ROOT / relative_path
        if not source.is_file() or marker not in source.read_text(encoding="utf-8"):
            errors.append({"bridge_id": bridge_id, "reason": "SOURCE_SURFACE_UNVERIFIABLE"})
    source_scan = scan_source_surfaces()
    for match in source_scan["matches"]:
        if match["bridge_id"] not in actual_ids:
            errors.append({"bridge_id": match["bridge_id"], "reason": "SURFACE_BRIDGE_UNINVENTORIED"})
    errors.extend(
        {"bridge_id": path, "reason": "UNMAPPED_SOURCE_SURFACE"}
        for path in source_scan["unmapped"]
    )
    return {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "row_count": len(rows),
        "required_fields": sorted(REQUIRED_BRIDGE_FIELDS),
        "error_codes": sorted({error["reason"] for error in errors}),
        "errors": errors,
        "source_scan": source_scan,
    }


def _removal_test_exists(test_ref: str, bridge_id: str) -> bool:
    """只接受可定位的 bridge-specific pytest function，禁止 inventory 自我證明。"""
    try:
        relative_path, function = test_ref.split("::", 1)
    except ValueError:
        return False
    if relative_path != REMOVAL_TEST_MODULE or function != f"test_{bridge_id}_removal_evidence":
        return False
    path = PROJECT_ROOT / relative_path
    if not path.is_file():
        return False
    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    return any(isinstance(node, ast.FunctionDef) and node.name == function for node in module.body)


def scan_source_surfaces(
    *, manifest: dict[str, str] | None = None, project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """只掃 production source；每個 run_history function/module surface 必須有 bridge 映射。"""
    active_manifest = manifest if manifest is not None else SOURCE_SURFACE_MANIFEST
    matches: list[dict[str, str]] = []
    for relative_path in sorted(active_manifest):
        path = project_root / relative_path
        if not path.is_file():
            matches.append({"path": relative_path, "function": "<missing>", "bridge_id": ""})
            continue
        source_lines = path.read_text(encoding="utf-8").splitlines()
        tree = ast.parse("\n".join(source_lines))
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        names = {
            node.name for node in functions
            if any("run_history" in line.lower() for line in source_lines[node.lineno - 1:node.end_lineno])
        }
        for function in sorted(names or ({"<module>"} if any("run_history" in line.lower() for line in source_lines) else set())):
            matches.append({"path": relative_path, "function": function, "bridge_id": active_manifest[relative_path]})
    discovered = sorted(
        str(path.relative_to(project_root))
        for directory in (project_root / "app/research", project_root / "scripts")
        for path in directory.rglob("*.py")
        if path != Path(__file__) and "run_history" in path.read_text(encoding="utf-8").lower()
    )
    unmapped = sorted(set(discovered) - set(active_manifest))
    return {
        "inputs": {"roots": ["app/research", "scripts"], "matcher": "casefold:run_history", "manifest_paths": sorted(active_manifest)},
        "matches": matches,
        "unmapped": unmapped,
        "status": "PASS" if not unmapped and all(match["bridge_id"] for match in matches) else "FAIL",
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
    intents = membership["intents"]
    for run_id, attempt in attempts.items():
        intent_id = str(attempt.get("intent_id") or "")
        if intent_id not in intents:
            membership["errors"].append({"entity": run_id, "reason": "ATTEMPT_INTENT_MEMBERSHIP_MISMATCH"})
    for run_id, receipt in receipts.items():
        attempt = attempts.get(run_id)
        if attempt is None:
            membership["errors"].append({"entity": run_id, "reason": "RECEIPT_ATTEMPT_MEMBERSHIP_MISMATCH"})
            continue
        if receipt.get("intent_id") != attempt.get("intent_id"):
            membership["errors"].append({"entity": run_id, "reason": "RECEIPT_INTENT_MEMBERSHIP_MISMATCH"})
        if receipt.get("attempt_event_id") != attempt.get("attempt_event_id"):
            membership["errors"].append({"entity": run_id, "reason": "RECEIPT_ATTEMPT_EVENT_MEMBERSHIP_MISMATCH"})
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
    for ancestor in (resolved_output, *resolved_output.parents):
        if (ancestor / ".git").exists():
            raise ValueError("A6_OUTPUT_ROOT_REPOSITORY_CHILD")
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
    marker = output_root / ".a6-closure-generated-root"
    if output_root.exists() and not marker.is_file():
        raise ValueError("A6_OUTPUT_ROOT_MARKER_REQUIRED")
    if output_root.exists():
        shutil.rmtree(output_root)


def scope_guards(*, base_ref: str, candidate_ref: str, repo_root: Path = PROJECT_ROOT) -> dict[str, bool]:
    """由 base..candidate 的實際差異判定，拒絕用常數宣告 scope 安全。"""
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", f"{base_ref}..{candidate_ref}"],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode:
        raise ValueError("A6_SCOPE_DIFF_UNAVAILABLE")
    changed = {line for line in completed.stdout.splitlines() if line}
    return {
        "card_b_started": any(path.startswith(("app/research/card_b", "docs/tasks/CARD-B")) for path in changed),
        "card_c_started": any(path.startswith(("app/research/card_c", "docs/tasks/CARD-C")) for path in changed),
        "production_changed": any(path.startswith(("models/", "app/agent_b_ranking.py", "config/signals")) for path in changed),
        "scheduler_changed": any(path.endswith(".plist") or "scheduler" in path for path in changed),
        "ranking_or_backtest_math_changed": any(path.startswith(("indicators.py", "fundamental_data.py", "reason_generator.py", "app/modeling/")) for path in changed),
    }


def canonical_closure_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """移除 fixture runtime timestamp 導出的 identities，保留可驗收 closure 語義。"""
    rebuild = receipt["rebuild"]
    return {
        "schema_version": receipt["schema_version"],
        "status": receipt["status"],
        "scope_guards": receipt["scope_guards"],
        "rebuild": {"status": rebuild["status"], "checks": rebuild["checks"], "counts": rebuild["first"]["counts"]},
        "new_run_truth": receipt["new_run_truth"]["counts"],
        "bridge_inventory": receipt["bridge_inventory"],
        "error_codes": receipt["error_codes"],
    }


def verify_a6_closure(
    *, corpus_root: Path, output_root: Path, base_ref: str = "bb617e98aabefcc52bbf7cb1834fb5fba715d60a", candidate_ref: str = "HEAD"
) -> dict[str, Any]:
    _reset_output_root(output_root, corpus_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / ".a6-closure-generated-root").write_text("research-spine-a6\n", encoding="utf-8")
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
    guards = scope_guards(base_ref=base_ref, candidate_ref=candidate_ref)
    if any(guards.values()):
        error_codes.append("SCOPE_GUARD_NO_GO")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not error_codes else "FAIL",
        "issue": 8,
        "scope_guards": guards,
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
    parser.add_argument("--output-root", type=Path, default=DEFAULT_TEMP_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--base-ref", default="bb617e98aabefcc52bbf7cb1834fb5fba715d60a")
    parser.add_argument("--candidate-ref", default="HEAD")
    args = parser.parse_args()
    del args.ledger  # 保留 CLI 相容欄位；A6 closure 永遠使用 isolated output root。
    result = verify_a6_closure(
        corpus_root=args.corpus_root, output_root=args.output_root,
        base_ref=args.base_ref, candidate_ref=args.candidate_ref,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "output": str(args.output)}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
