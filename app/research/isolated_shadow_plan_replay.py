"""隔離執行已核准的 horizon 10 -> 20 development-only replay。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import duckdb

from app.research.batch_owner import (
    build_batch_intent,
    publish_batch_intent,
    validate_batch_intent,
    verify_batch_owner_authority,
)
from app.research.contracts import canonical_json_bytes, content_hash, validate_run_receipt
from app.research.observation_ingest import ingest_corpus
from app.research.receipt_store import write_immutable_json
from app.research.shadow_plan_proposal import (
    DEFAULT_OUTPUT_RELATIVE as PROPOSAL_RELATIVE,
    load_json,
    snapshot_protected_surfaces,
    verify_proposal,
)
from scripts import run_autonomous_research as formal_runner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "isolated-shadow-plan-replay.v1"
PLAN_SCHEMA_VERSION = "isolated-shadow-execution-plan.v1"
RECEIPT_SCHEMA_VERSION = "isolated-shadow-execution-receipt.v1"
EXPECTED_SOURCE_COMMIT = "28708ee3956fd0b6c9400dc21ecfb72920b46312"
EXPECTED_PROPOSAL_SET_ID = "sha256:1a1867a6097a92264c75f094c11e7248fdcd99900bd4b3d66d9642b699ac565a"
EXPECTED_PROPOSAL_ID = "sha256:6cf375eba0a52aa95f41ed807d346ed96999cd9636848b063515ebdbe55b4101"
EXPECTED_SEMANTIC_HASH = "sha256:a6f1ba6711cf8a3b0ea32c1075781ac916b4140b82ee66fc6bd701a94b484d96"
EXPECTED_SCOPE = "NARROW_LEADER|BIG_BULL"
HORIZONS = (10, 20)
FIXED_PARAMETERS = {
    "stop_loss_pct": 0.08,
    "take_profit_pct": 0.15,
    "max_group_exposure": 0.35,
}
MAX_UNITS = 4
MAX_BYTES = 64 * 1024**2
MAX_FILES = 250
MIN_HOST_RESERVE_BYTES = 20 * 1024**3
CAPACITY_SOURCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1/"
    "adaptive_shadow_queue_projection.json"
)
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1"
)
POLICY_PATH = PROJECT_ROOT / "config/research_shadow_queue_policy_v1.json"
CATALOG_PATH = PROJECT_ROOT / "config/research_parameter_catalog.json"
SCHEDULER_PATH = PROJECT_ROOT / "scripts/run_daily_research_quota.sh"


class IsolatedReplayError(RuntimeError):
    """表示 replay 必須 fail closed 的結構化原因。"""


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes()) if path.is_file() else "ABSENT"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _require_exact_proposal(path: Path) -> dict[str, Any]:
    raw = path.as_posix()
    expected = PROJECT_ROOT / PROPOSAL_RELATIVE
    if (
        path.is_absolute()
        or ".." in PurePosixPath(raw).parts
        or raw != PROPOSAL_RELATIVE.as_posix()
    ):
        raise IsolatedReplayError("PROPOSAL_NOT_COMMITTED_PATH")
    if expected.is_symlink() or expected.resolve() != expected.absolute():
        raise IsolatedReplayError("PROPOSAL_SYMLINK_ESCAPE")
    committed = _git("show", f"HEAD:{PROPOSAL_RELATIVE.as_posix()}")
    if committed.returncode != 0 or committed.stdout.encode() != expected.read_bytes():
        raise IsolatedReplayError("PROPOSAL_NOT_EXACT_HEAD_BLOB")
    ancestry = _git("merge-base", "--is-ancestor", EXPECTED_SOURCE_COMMIT, "HEAD")
    if ancestry.returncode != 0:
        raise IsolatedReplayError("PROPOSAL_SOURCE_COMMIT_NOT_ANCESTOR")
    payload = load_json(expected)
    verification = verify_proposal(payload)
    if verification.get("status") != "PASS":
        raise IsolatedReplayError("PROPOSAL_VERIFICATION_FAILED")
    proposals = payload.get("proposals") if isinstance(payload.get("proposals"), list) else []
    row = proposals[0] if len(proposals) == 1 and isinstance(proposals[0], dict) else {}
    checks = {
        "status": payload.get("status") == "PASS",
        "proposal_set": payload.get("proposal_set_id") == EXPECTED_PROPOSAL_SET_ID,
        "semantic_hash": payload.get("semantic_hash") == EXPECTED_SEMANTIC_HASH,
        "proposal_id": row.get("proposal_id") == EXPECTED_PROPOSAL_ID,
        "parameter": row.get("parameter") == "horizon",
        "values": (row.get("current_value"), row.get("proposed_next_value")) == HORIZONS,
        "scope": (row.get("scope") or {}).get("regime_id") == EXPECTED_SCOPE,
        "boundary": row.get("boundary")
        == {
            "canonical_queue_write_allowed": False,
            "execution_allowed": False,
            "production_change_allowed": False,
            "scheduler_change_allowed": False,
        },
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise IsolatedReplayError("PROPOSAL_IDENTITY_MISMATCH:" + ",".join(failed))
    return payload


def _authorize_isolated_root(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise IsolatedReplayError("ISOLATED_ROOT_INSIDE_PROJECT")
    if path.is_symlink() or resolved == Path(resolved.anchor):
        raise IsolatedReplayError("ISOLATED_ROOT_UNSAFE")
    if resolved.exists() and any(resolved.iterdir()):
        raise IsolatedReplayError("ISOLATED_ROOT_NOT_EMPTY")
    return resolved


def _authorize_evidence_root(path: Path) -> Path:
    raw = path.as_posix()
    if (
        path.is_absolute()
        or ".." in PurePosixPath(raw).parts
        or raw != EVIDENCE_RELATIVE.as_posix()
    ):
        raise IsolatedReplayError("EVIDENCE_ROOT_NOT_CARD_PATH")
    expected = PROJECT_ROOT / EVIDENCE_RELATIVE
    if expected.is_symlink() or expected.resolve(strict=False) != expected.absolute():
        raise IsolatedReplayError("EVIDENCE_ROOT_SYMLINK_ESCAPE")
    return expected


def _tree_usage(root: Path) -> dict[str, int]:
    files = [path for path in root.rglob("*") if path.is_file() and not path.is_symlink()]
    return {"bytes": sum(path.stat().st_size for path in files), "file_count": len(files)}


def capacity_preflight(root: Path) -> dict[str, Any]:
    source = load_json(PROJECT_ROOT / CAPACITY_SOURCE_RELATIVE)
    samples = list((source.get("capacity_receipt") or {}).get("observed_cycles") or [])
    observed_bytes = max((int(row.get("bytes") or 0) for row in samples), default=0)
    observed_files = max((int(row.get("file_count") or 0) for row in samples), default=0)
    disk = shutil.disk_usage(root.parent)
    reserve = max(MIN_HOST_RESERVE_BYTES, int(disk.total * 0.10))
    reasons: list[str] = []
    if not samples or observed_bytes <= 0 or observed_files <= 0:
        reasons.append("CAPACITY_ESTIMATE_UNAVAILABLE")
    if observed_bytes > MAX_BYTES or observed_files > MAX_FILES:
        reasons.append("SOURCE_OBSERVATION_EXCEEDS_BUDGET")
    if disk.free - MAX_BYTES < reserve:
        reasons.append("HOST_RESERVE_INSUFFICIENT")
    return {
        "status": "GO" if not reasons else "NO-GO_CAPACITY",
        "reason_codes": reasons,
        "budget": {"max_units": MAX_UNITS, "max_bytes": MAX_BYTES, "max_files": MAX_FILES},
        "estimate": {
            "bytes": observed_bytes,
            "file_count": observed_files,
            "sample_count": len(samples),
            "fallback_source": CAPACITY_SOURCE_RELATIVE.as_posix(),
            "error_bound": "upper_bound_is_hard_budget",
        },
        "host": {"total_bytes": disk.total, "free_bytes": disk.free, "reserve_bytes": reserve},
    }


def build_execution_plan(
    *, baseline_dir: Path, candidate_dir: Path, features: Path, regime_history: Path,
    execution_date: str,
) -> dict[str, Any]:
    sources = {
        "baseline": baseline_dir.resolve(),
        "candidate": candidate_dir.resolve(),
        "features": features.resolve(),
        "regime_history": regime_history.resolve(),
    }
    if not sources["features"].is_file() or not sources["regime_history"].is_file():
        raise IsolatedReplayError("REAL_DATA_INPUT_MISSING")
    for role in ("baseline", "candidate"):
        files = sorted(sources[role].glob("ranking_*.csv"))
        if len(files) < 3:
            raise IsolatedReplayError(f"REAL_RANKING_INPUT_MISSING:{role}")
    units: list[dict[str, Any]] = []
    for role in ("baseline", "candidate"):
        # plan 綁定來源 bytes；正式 receipt 另由 run_receipts 綁定 execution manifest。
        ranking_files = sorted(sources[role].glob("ranking_*.csv"))[-8:]
        ranking_hash = content_hash(
            {
                "files": [
                    {"name": path.name, "sha256": _sha256_file(path)}
                    for path in ranking_files
                ]
            }
        )
        for horizon in HORIZONS:
            identity = {
                "role": role,
                "horizon": horizon,
                "scope": EXPECTED_SCOPE,
                "ranking_source_hash": ranking_hash,
                "dataset_hash": _sha256_file(sources["features"]),
                **FIXED_PARAMETERS,
            }
            units.append({**identity, "unit_id": content_hash(identity)})
    plan: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_id": "",
        "proposal_set_id": EXPECTED_PROPOSAL_SET_ID,
        "proposal_id": EXPECTED_PROPOSAL_ID,
        "research_stage": "DEVELOPMENT_SCREEN",
        "scope": EXPECTED_SCOPE,
        "execution_date": execution_date,
        "matrix": units,
        "boundary": {
            "development_only": True,
            "sealed_data_read_allowed": False,
            "canonical_queue_write_allowed": False,
            "scheduler_write_allowed": False,
            "production_write_allowed": False,
        },
    }
    plan["plan_id"] = content_hash(plan, omit={"plan_id"})
    return plan


def validate_execution_plan(plan: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        errors.append("INVALID_PLAN_SCHEMA")
    if plan.get("plan_id") != content_hash(plan, omit={"plan_id"}):
        errors.append("PLAN_ID_MISMATCH")
    matrix = plan.get("matrix") if isinstance(plan.get("matrix"), list) else []
    pairs = [(row.get("role"), row.get("horizon")) for row in matrix if isinstance(row, Mapping)]
    expected = [(role, horizon) for role in ("baseline", "candidate") for horizon in HORIZONS]
    if pairs != expected or len(matrix) != MAX_UNITS:
        errors.append("MATRIX_NOT_EXACT_2X2")
    for row in matrix:
        if not isinstance(row, Mapping):
            continue
        if row.get("scope") != EXPECTED_SCOPE:
            errors.append("SCOPE_EXPANDED")
        if any(
            canonical_json_bytes({"value": row.get(key)})
            != canonical_json_bytes({"value": value})
            for key, value in FIXED_PARAMETERS.items()
        ):
            errors.append("NON_HORIZON_PARAMETER_DRIFT")
        if row.get("unit_id") != content_hash(row, omit={"unit_id"}):
            errors.append("UNIT_ID_MISMATCH")
    boundary = plan.get("boundary") if isinstance(plan.get("boundary"), Mapping) else {}
    if boundary != {
        "development_only": True,
        "sealed_data_read_allowed": False,
        "canonical_queue_write_allowed": False,
        "scheduler_write_allowed": False,
        "production_write_allowed": False,
    }:
        errors.append("BOUNDARY_MISMATCH")
    return sorted(set(errors))


def _runner_topic(plan: Mapping[str, Any], baseline_dir: Path, candidate_dir: Path) -> formal_runner.ResearchTopic:
    return formal_runner.ResearchTopic(
        topic_id="native_evidence_replay:isolated_shadow_h10_h20:development_screen",
        title="horizon 10 與 20 隔離 development replay",
        hypothesis="在固定研究條件下比較 horizon 10 與 20。",
        validation_plan="正式 strategy matrix runner 的 paired exact-regime development-only replay。",
        runner="strategy_matrix_comparison",
        candidate_dir=str(candidate_dir.resolve()),
        baseline_dir=str(baseline_dir.resolve()),
        score=0.0,
        reasons=["APPROVED_SHADOW_PLAN_REPLAY"],
        evidence_sources=[EXPECTED_PROPOSAL_SET_ID],
        ranking_file_count=8,
        validation_profile="isolated_shadow_horizon_pair",
        horizons="10,20",
        stop_loss_pcts="0.08",
        take_profit_pcts="0.15",
        max_group_exposures="0.35",
        regime_identity={"base_regime": "NARROW_LEADER", "family_tags": ["BIG_BULL"]},
        eligible=True,
        reason_code="APPROVED_ISOLATED_REPLAY",
        selection_rationale={"research_stage": "DEVELOPMENT_SCREEN", "plan_id": plan["plan_id"]},
    )


def _query_units(ledger_path: Path) -> list[dict[str, Any]]:
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT u.execution_unit_id,r.terminal_status,r.observation_status,
                   r.identity_match_status,u.lineage_resolution_status,u.sealed_usage_status,
                   u.lineage_id,p.integer_value AS horizon,o.score,o.total_return,
                   o.max_drawdown,o.trade_count,o.observation_id
            FROM execution_units u
            JOIN run_receipts r ON r.receipt_id=u.receipt_id
            JOIN execution_unit_parameters p
              ON p.execution_unit_id=u.execution_unit_id AND p.parameter_id='horizon'
            LEFT JOIN observations o ON o.execution_unit_id=u.execution_unit_id
            ORDER BY u.lineage_id,p.integer_value
            """
        ).fetchall()
        names = [column[0] for column in connection.description]
        return [dict(zip(names, row, strict=True)) for row in rows]
    finally:
        connection.close()


def _classify(units: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    by_lineage: dict[str, dict[int, Mapping[str, Any]]] = {}
    for row in units:
        by_lineage.setdefault(str(row["lineage_id"]), {})[int(row["horizon"])] = row
    contrasts: list[dict[str, Any]] = []
    for lineage_id in sorted(by_lineage):
        pair = by_lineage[lineage_id]
        if set(pair) != set(HORIZONS):
            continue
        low, high = pair[10], pair[20]
        delta_score = float(high["score"]) - float(low["score"])
        delta_return = float(high["total_return"]) - float(low["total_return"])
        delta_drawdown = float(high["max_drawdown"]) - float(low["max_drawdown"])
        classification = (
            "HORIZON_20_BETTER"
            if delta_score > 0 and delta_return >= 0 and delta_drawdown >= 0
            else "HORIZON_10_BETTER"
            if delta_score < 0 and delta_return <= 0
            else "MIXED"
        )
        contrasts.append(
            {
                "lineage_id": lineage_id,
                "horizon_10_observation_id": low["observation_id"],
                "horizon_20_observation_id": high["observation_id"],
                "delta_score": round(delta_score, 12),
                "delta_total_return": round(delta_return, 12),
                "delta_max_drawdown": round(delta_drawdown, 12),
                "classification": classification,
            }
        )
    labels = {row["classification"] for row in contrasts}
    overall = (
        "NO_COMPARISON"
        if not labels
        else labels.pop()
        if len(labels) == 1
        else "MIXED_LINEAGES"
    )
    return contrasts, overall


def verify_result(
    *, plan: Mapping[str, Any], units: Sequence[Mapping[str, Any]], capacity: Mapping[str, Any],
    parity_before: Mapping[str, Any], parity_after: Mapping[str, Any],
) -> dict[str, Any]:
    errors = validate_execution_plan(plan)
    required = {
        "terminal_status": "SUCCEEDED",
        "observation_status": "OBSERVED",
        "identity_match_status": "EXACT",
        "lineage_resolution_status": "VALID",
        "sealed_usage_status": "PROVEN_NON_SEALED",
    }
    if len(units) != MAX_UNITS:
        errors.append("EXECUTION_UNIT_COUNT_NOT_4")
    for index, row in enumerate(units):
        for field, expected in required.items():
            if row.get(field) != expected:
                errors.append(f"UNIT_{index}:{field.upper()}_MISMATCH")
        if row.get("observation_id") is None:
            errors.append(f"UNIT_{index}:OBSERVATION_MISSING")
    if sorted(int(row["horizon"]) for row in units) != [10, 10, 20, 20]:
        errors.append("EXECUTED_HORIZONS_MISMATCH")
    if len({str(row["lineage_id"]) for row in units}) != 2:
        errors.append("EXECUTED_LINEAGES_NOT_2")
    usage = capacity.get("observed") if isinstance(capacity.get("observed"), Mapping) else {}
    if int(usage.get("bytes") or 0) > MAX_BYTES or int(usage.get("file_count") or 0) > MAX_FILES:
        errors.append("CAPACITY_BUDGET_EXCEEDED")
    if parity_before != parity_after:
        errors.append("PROTECTED_SURFACE_DRIFT")
    contrasts, classification = _classify(units)
    if len(contrasts) != 2:
        errors.append("MATCHED_CONTRAST_COUNT_NOT_2")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "DELIVERED_CANDIDATE" if not errors else "NO-GO_EVIDENCE_UNAVAILABLE",
        "reason_codes": sorted(set(errors)),
        "plan_id": plan.get("plan_id"),
        "unit_count": len(units),
        "lineage_count": len({str(row.get("lineage_id")) for row in units}),
        "units": list(units),
        "matched_contrasts": contrasts,
        "classification": classification,
        "capacity": dict(capacity),
        "protected_surface_parity": {
            "unchanged": parity_before == parity_after,
            "before": parity_before,
            "after": parity_after,
        },
    }


def build_execution_receipt(
    *, plan_id: str, batch_id: str, batch_intent_id: str | None,
    run_receipt: Mapping[str, Any], steps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    commands = [
        {
            "name": step.get("name"),
            "status": step.get("status"),
            "argv": list(step.get("command") or []),
            "return_code": step.get("returncode"),
            "started_at": step.get("started_at"),
            "ended_at": step.get("ended_at"),
        }
        for step in steps
    ]
    payload: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "execution_receipt_id": "",
        "plan_id": plan_id,
        "batch_id": batch_id,
        "batch_intent_id": batch_intent_id,
        "run_id": run_receipt.get("run_id"),
        "intent_id": run_receipt.get("intent_id"),
        "attempt_event_id": run_receipt.get("attempt_event_id"),
        "research_receipt_id": run_receipt.get("receipt_id"),
        "terminal_status": run_receipt.get("terminal_status"),
        "commands": commands,
    }
    payload["execution_receipt_id"] = content_hash(
        payload, omit={"execution_receipt_id"}
    )
    return payload


def validate_execution_receipt(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    fields = {
        "schema_version", "execution_receipt_id", "plan_id", "batch_id",
        "batch_intent_id", "run_id", "intent_id", "attempt_event_id",
        "research_receipt_id", "terminal_status", "commands",
    }
    if set(payload) != fields:
        errors.append("EXECUTION_RECEIPT_FIELDS_MISMATCH")
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        errors.append("EXECUTION_RECEIPT_SCHEMA_INVALID")
    if payload.get("execution_receipt_id") != content_hash(
        payload, omit={"execution_receipt_id"}
    ):
        errors.append("EXECUTION_RECEIPT_ID_MISMATCH")
    for field in (
        "plan_id", "batch_id", "batch_intent_id", "run_id", "intent_id",
        "attempt_event_id", "research_receipt_id", "terminal_status",
    ):
        if not isinstance(payload.get(field), str) or not payload.get(field):
            errors.append(f"EXECUTION_RECEIPT_{field.upper()}_MISSING")
    commands = payload.get("commands") if isinstance(payload.get("commands"), list) else []
    if len(commands) != 3:
        errors.append("EXECUTION_RECEIPT_COMMAND_COUNT_NOT_3")
    for index, command in enumerate(commands):
        if not isinstance(command, Mapping):
            errors.append(f"EXECUTION_RECEIPT_COMMAND_{index}_INVALID")
            continue
        if not isinstance(command.get("argv"), list) or not command.get("argv"):
            errors.append(f"EXECUTION_RECEIPT_COMMAND_{index}_ARGV_MISSING")
        status = command.get("status")
        return_code = command.get("return_code")
        if status in {"OK", "FAILED"} and not isinstance(return_code, int):
            errors.append(f"EXECUTION_RECEIPT_COMMAND_{index}_RETURN_CODE_MISSING")
        if status == "SKIPPED" and return_code is not None:
            errors.append(f"EXECUTION_RECEIPT_COMMAND_{index}_SKIP_RETURN_CODE_INVALID")
    return sorted(set(errors))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(payload) + b"\n"
    if path.exists() and path.read_bytes() != encoded:
        raise IsolatedReplayError(f"EVIDENCE_COLLISION:{path.name}")
    path.write_bytes(encoded)


def run(args: argparse.Namespace, runtime_argv: Sequence[str]) -> dict[str, Any]:
    _require_exact_proposal(args.proposal)
    evidence_root = _authorize_evidence_root(args.evidence_root)
    isolated_root = _authorize_isolated_root(args.isolated_root)
    capacity = capacity_preflight(isolated_root)
    if capacity["status"] != "GO":
        raise IsolatedReplayError("NO-GO_CAPACITY")
    plan = build_execution_plan(
        baseline_dir=args.baseline_dir,
        candidate_dir=args.candidate_dir,
        features=args.features,
        regime_history=args.regime_history,
        execution_date=args.execution_date,
    )
    plan_errors = validate_execution_plan(plan)
    if plan_errors:
        raise IsolatedReplayError(plan_errors[0])
    isolated_root.mkdir(parents=True, exist_ok=True)
    output_root = isolated_root / "manager"
    corpus_root = isolated_root / "corpus"
    ledger_path = isolated_root / "ledger" / "research_ledger.duckdb"
    output_path = output_root / "isolated_shadow_replay.json"
    run_dir = output_root / "run"
    batch_id = f"research-{args.execution_date}-{datetime.now(UTC).strftime('%H%M%S')}-{os.getpid()}"
    intent = build_batch_intent(
        project_root=PROJECT_ROOT,
        corpus_root=corpus_root,
        batch_id=batch_id,
        scheduler_entrypoint=SCHEDULER_PATH,
        runner_argv=list(runtime_argv),
        output_path=output_path,
        ledger_path=ledger_path,
        requested_research_stage="DEVELOPMENT_SCREEN",
        allowed_research_stages=["DEVELOPMENT_SCREEN"],
        policy_path=POLICY_PATH,
        catalog_path=CATALOG_PATH,
        execution_epoch=args.execution_date,
    )
    intent_result = publish_batch_intent(corpus_root=corpus_root, payload=intent)
    authority = verify_batch_owner_authority(
        project_root=PROJECT_ROOT,
        corpus_root=corpus_root,
        batch_id=batch_id,
        batch_intent_reference=str(intent_result.path),
        runtime_argv=list(runtime_argv),
        output_path=output_path,
        ledger_path=ledger_path,
        manager_root=output_root,
        requested_research_stage="DEVELOPMENT_SCREEN",
        execution_epoch=args.execution_date,
    )
    parity_before = snapshot_protected_surfaces(project_root=PROJECT_ROOT)
    runner_args = SimpleNamespace(
        date=args.execution_date,
        features=str(args.features.resolve()),
        max_ranking_files=8,
        horizons="10,20",
        stop_loss_pcts="0.08",
        take_profit_pcts="0.15",
        max_group_exposures="0.35",
        closed_regime_research=True,
        market_regime_history=str(args.regime_history.resolve()),
        research_contract=str((PROJECT_ROOT / "config/regime_research_contract.json").resolve()),
    )
    topic = _runner_topic(plan, args.baseline_dir, args.candidate_dir)
    scenarios = formal_runner.validation_profile_combinations(
        topic.horizons,
        topic.stop_loss_pcts,
        topic.take_profit_pcts,
        topic.max_group_exposures,
    )
    attempt = formal_runner.begin_topic_attempt(
        corpus_root=corpus_root,
        project_root=PROJECT_ROOT,
        topic=topic,
        scenarios=scenarios,
        research_stage="DEVELOPMENT_SCREEN",
        regime_scope={"regime_id": EXPECTED_SCOPE},
        features_path=str(args.features.resolve()),
        execution_settings={
            "max_ranking_files": 8,
            "top_n": 10,
            "max_gross_exposure": 0.65,
            "max_position_weight": 0.2,
            "fee_rate": 0.001425,
            "tax_rate": 0.003,
            "slippage_rate": 0.001,
            "same_day_hit_priority": "stop_loss",
            "runner_policy_version": "strategy-matrix-replay.v1",
        },
        selection_reason_codes=["APPROVED_SHADOW_PLAN_REPLAY"],
        research_batch_id=batch_id,
    )
    execution_started = False

    def mark_execution_started() -> None:
        nonlocal execution_started
        execution_started = True

    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        steps, outcome, outputs = formal_runner.execute_topic(
            runner_args,
            topic,
            run_dir,
            on_execution_started=mark_execution_started,
            receipt_attempt=attempt,
        )
        all_steps_ok = all(step["status"] == "OK" for step in steps)
        slug = formal_runner.slugify(topic.topic_id)
        receipt = formal_runner.finish_topic_attempt(
            attempt,
            terminal_status="SUCCEEDED" if all_steps_ok else "FAILED",
            matrix_paths=[
                run_dir / f"{slug}_baseline_strategy_matrix.json",
                run_dir / f"{slug}_candidate_strategy_matrix.json",
            ],
            lineage_authority_paths=[
                run_dir / f"{slug}_development_screen_contract.json"
            ],
            failure_reason=None if all_steps_ok else "RUNNER_STEP_FAILED",
        )
    except Exception as error:
        formal_runner.finish_topic_attempt(
            attempt,
            terminal_status="FAILED" if execution_started else "REJECTED_BEFORE_EXECUTION",
            matrix_paths=[],
            failure_reason=type(error).__name__.upper(),
        )
        raise
    receipt_errors = validate_run_receipt(receipt)
    if receipt_errors:
        raise IsolatedReplayError("RUN_RECEIPT_INVALID:" + receipt_errors[0])
    ingest = ingest_corpus(corpus_root=corpus_root, ledger_path=ledger_path, rebuild=True)
    units = _query_units(ledger_path)
    parity_after = snapshot_protected_surfaces(project_root=PROJECT_ROOT)
    execution_receipt = build_execution_receipt(
        plan_id=str(plan["plan_id"]),
        batch_id=batch_id,
        batch_intent_id=authority.batch_intent_id,
        run_receipt=receipt,
        steps=steps,
    )
    execution_receipt_id = str(execution_receipt["execution_receipt_id"])
    execution_receipt_path = (
        corpus_root / "execution_receipts" / f"{execution_receipt_id.removeprefix('sha256:')}.json"
    )
    write_immutable_json(
        execution_receipt_path,
        execution_receipt,
        validator=validate_execution_receipt,
        identity_field="execution_receipt_id",
    )
    capacity = {**capacity, "observed": _tree_usage(isolated_root)}
    result = verify_result(
        plan=plan,
        units=units,
        capacity=capacity,
        parity_before=parity_before,
        parity_after=parity_after,
    )
    if any(
        "NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE"
        in str(step.get("stderr_tail") or "")
        for step in steps
    ):
        result["reason_codes"] = sorted(
            {*result["reason_codes"], "NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE"}
        )
    result.update(
        {
            "proposal_path": PROPOSAL_RELATIVE.as_posix(),
            "batch_id": batch_id,
            "batch_intent_id": authority.batch_intent_id,
            "run_id": attempt.run_id,
            "intent_id": attempt.intent_id,
            "receipt_id": receipt["receipt_id"],
            "execution_receipt_id": execution_receipt_id,
            "runner": {
                "owner": "scripts.run_autonomous_research.execute_topic",
                "argv": list(runtime_argv),
                "argv_hash": content_hash({"argv": list(runtime_argv)}),
                "steps": steps,
                "outcome": outcome,
                "outputs": outputs,
            },
            "ingest": asdict(ingest),
            "local_only_isolated_root": str(isolated_root),
        }
    )
    _write_json(isolated_root / "execution_plan.json", plan)
    _write_json(output_path, result)
    _write_json(evidence_root / "execution_plan.json", plan)
    _write_json(evidence_root / "result.json", result)
    _write_json(evidence_root / "run_receipt.json", receipt)
    _write_json(evidence_root / "batch_intent.json", intent)
    _write_json(evidence_root / "execution_receipt.json", execution_receipt)
    return result


def verify_evidence(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("INVALID_SCHEMA")
    status = payload.get("status")
    unavailable = False
    if status == "DELIVERED_CANDIDATE":
        if payload.get("unit_count") != MAX_UNITS or payload.get("lineage_count") != 2:
            errors.append("RESULT_MATRIX_INCOMPLETE")
        if len(payload.get("matched_contrasts") or []) != 2:
            errors.append("RESULT_CONTRASTS_INCOMPLETE")
    elif status == "NO-GO_EVIDENCE_UNAVAILABLE":
        steps = (payload.get("runner") or {}).get("steps") or []
        unavailable = any(
            isinstance(step, Mapping)
            and step.get("status") == "FAILED"
            and "NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE"
            in str(step.get("stderr_tail") or "")
            for step in steps
        )
        if not unavailable:
            errors.append("NO_GO_RUNNER_EVIDENCE_MISSING")
        if (
            payload.get("unit_count") != 0
            or payload.get("lineage_count") != 0
            or payload.get("units")
            or payload.get("matched_contrasts")
        ):
            errors.append("NO_GO_MUST_NOT_CLAIM_COMPARISON")
    else:
        errors.append("RESULT_STATUS_INVALID")
    parity = payload.get("protected_surface_parity") or {}
    if parity.get("unchanged") is not True or parity.get("before") != parity.get("after"):
        errors.append("RESULT_PARITY_FAILED")
    capacity = payload.get("capacity") or {}
    observed = capacity.get("observed") or {}
    if int(observed.get("bytes") or 0) > MAX_BYTES or int(observed.get("file_count") or 0) > MAX_FILES:
        errors.append("RESULT_CAPACITY_EXCEEDED")
    plan_path = path.parent / "execution_plan.json"
    run_receipt_path = path.parent / "run_receipt.json"
    batch_intent_path = path.parent / "batch_intent.json"
    plan = load_json(plan_path) if plan_path.is_file() else {}
    run_receipt = load_json(run_receipt_path) if run_receipt_path.is_file() else {}
    batch_intent = load_json(batch_intent_path) if batch_intent_path.is_file() else {}
    if not plan:
        errors.append("RESULT_EXECUTION_PLAN_MISSING")
    else:
        errors.extend(f"EXECUTION_PLAN_INVALID:{error}" for error in validate_execution_plan(plan))
        if plan.get("plan_id") != payload.get("plan_id"):
            errors.append("RESULT_EXECUTION_PLAN_MISMATCH")
        if status == "NO-GO_EVIDENCE_UNAVAILABLE":
            recomputed = verify_result(
                plan=plan,
                units=payload.get("units") or [],
                capacity=capacity,
                parity_before=parity.get("before") or {},
                parity_after=parity.get("after") or {},
            )
            expected_reasons = set(recomputed["reason_codes"])
            if unavailable:
                expected_reasons.add("NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE")
            if payload.get("classification") != recomputed["classification"]:
                errors.append("RESULT_CLASSIFICATION_MISMATCH")
            if set(payload.get("reason_codes") or []) != expected_reasons:
                errors.append("RESULT_REASON_CODES_MISMATCH")
    if not run_receipt:
        errors.append("RESULT_RUN_RECEIPT_MISSING")
    else:
        errors.extend(f"RUN_RECEIPT_INVALID:{error}" for error in validate_run_receipt(run_receipt))
        for field in ("run_id", "intent_id"):
            if run_receipt.get(field) != payload.get(field):
                errors.append(f"RESULT_RUN_RECEIPT_{field.upper()}_MISMATCH")
        if run_receipt.get("receipt_id") != payload.get("receipt_id"):
            errors.append("RESULT_RUN_RECEIPT_ID_MISMATCH")
    if not batch_intent:
        errors.append("RESULT_BATCH_INTENT_MISSING")
    else:
        errors.extend(f"BATCH_INTENT_INVALID:{error}" for error in validate_batch_intent(batch_intent))
        for field in ("batch_id", "batch_intent_id"):
            if batch_intent.get(field) != payload.get(field):
                errors.append(f"RESULT_BATCH_INTENT_{field.upper()}_MISMATCH")
        runner = payload.get("runner") if isinstance(payload.get("runner"), Mapping) else {}
        batch_runner = (
            batch_intent.get("runner")
            if isinstance(batch_intent.get("runner"), Mapping)
            else {}
        )
        if batch_runner.get("argv") != runner.get("argv"):
            errors.append("RESULT_BATCH_INTENT_RUNNER_MISMATCH")
    if plan and run_receipt:
        requested = (
            run_receipt.get("requested")
            if isinstance(run_receipt.get("requested"), Mapping)
            else {}
        )
        if requested.get("research_stage") != plan.get("research_stage"):
            errors.append("PLAN_RUN_RECEIPT_STAGE_MISMATCH")
        if (requested.get("regime_scope") or {}).get("regime_id") != plan.get("scope"):
            errors.append("PLAN_RUN_RECEIPT_SCOPE_MISMATCH")
        dataset_hashes = {
            row.get("dataset_hash")
            for row in plan.get("matrix", [])
            if isinstance(row, Mapping)
        }
        if dataset_hashes != {(requested.get("dataset_authority") or {}).get("dataset_hash")}:
            errors.append("PLAN_RUN_RECEIPT_DATASET_MISMATCH")
        requested_parameters = requested.get("parameters_by_trial") or {}
        execution_profiles = requested.get("execution_profile_by_trial") or {}
        run_matrix = sorted(
            (
                (execution_profiles.get(trial_id) or {}).get("variant_role"),
                parameters.get("horizon"),
                str(parameters.get("stop_loss_pct")),
                str(parameters.get("take_profit_pct")),
                str(parameters.get("max_group_exposure")),
            )
            for trial_id, parameters in requested_parameters.items()
            if isinstance(parameters, Mapping)
        )
        plan_matrix = sorted(
            (
                row.get("role"),
                row.get("horizon"),
                str(row.get("stop_loss_pct")),
                str(row.get("take_profit_pct")),
                str(row.get("max_group_exposure")),
            )
            for row in plan.get("matrix", [])
            if isinstance(row, Mapping)
        )
        if run_matrix != plan_matrix:
            errors.append("PLAN_RUN_RECEIPT_MATRIX_MISMATCH")
    if plan and batch_intent:
        research = batch_intent.get("research") or {}
        if batch_intent.get("execution_epoch") != plan.get("execution_date"):
            errors.append("PLAN_BATCH_INTENT_DATE_MISMATCH")
        if research.get("requested_stage") != plan.get("research_stage"):
            errors.append("PLAN_BATCH_INTENT_STAGE_MISMATCH")
    execution_receipt_path = path.parent / "execution_receipt.json"
    if execution_receipt_path.is_file():
        execution_receipt = load_json(execution_receipt_path)
        errors.extend(validate_execution_receipt(execution_receipt))
        if execution_receipt.get("plan_id") != payload.get("plan_id"):
            errors.append("RESULT_EXECUTION_RECEIPT_PLAN_MISMATCH")
        if execution_receipt.get("run_id") != payload.get("run_id"):
            errors.append("RESULT_EXECUTION_RECEIPT_RUN_MISMATCH")
        if execution_receipt.get("batch_id") != payload.get("batch_id"):
            errors.append("RESULT_EXECUTION_RECEIPT_BATCH_MISMATCH")
        if execution_receipt.get("batch_intent_id") != payload.get("batch_intent_id"):
            errors.append("RESULT_EXECUTION_RECEIPT_BATCH_INTENT_MISMATCH")
        if execution_receipt.get("research_receipt_id") != payload.get("receipt_id"):
            errors.append("RESULT_EXECUTION_RECEIPT_RESEARCH_RECEIPT_MISMATCH")
        if execution_receipt.get("execution_receipt_id") != payload.get("execution_receipt_id"):
            errors.append("RESULT_EXECUTION_RECEIPT_ID_MISMATCH")
        if run_receipt:
            receipt_bindings = {
                "run_id": "RUN",
                "intent_id": "INTENT",
                "attempt_event_id": "ATTEMPT",
                "terminal_status": "TERMINAL_STATUS",
            }
            for field, label in receipt_bindings.items():
                if execution_receipt.get(field) != run_receipt.get(field):
                    errors.append(f"RUN_EXECUTION_RECEIPT_{label}_MISMATCH")
            if execution_receipt.get("research_receipt_id") != run_receipt.get("receipt_id"):
                errors.append("RUN_EXECUTION_RECEIPT_ID_MISMATCH")
        commands = execution_receipt.get("commands") or []
        result_steps = (payload.get("runner") or {}).get("steps") or []
        if len(commands) != len(result_steps):
            errors.append("RESULT_EXECUTION_RECEIPT_COMMAND_COUNT_MISMATCH")
        command_trial_ids: set[str] = set()
        for index, (command, step) in enumerate(zip(commands, result_steps, strict=False)):
            if (
                command.get("argv") != step.get("command")
                or command.get("name") != step.get("name")
                or command.get("status") != step.get("status")
                or command.get("return_code") != step.get("returncode")
                or command.get("started_at") != step.get("started_at")
                or command.get("ended_at") != step.get("ended_at")
            ):
                errors.append(f"RESULT_EXECUTION_RECEIPT_COMMAND_{index}_MISMATCH")
            argv = command.get("argv") if isinstance(command.get("argv"), list) else []
            is_strategy_command = any(
                str(argument).endswith("run_backtest_strategy_matrix.py")
                for argument in argv
            )
            for option, field, label in (
                ("--research-run-id", "run_id", "RUN"),
                ("--research-intent-id", "intent_id", "INTENT"),
            ):
                if option not in argv:
                    if is_strategy_command:
                        errors.append(f"RESULT_COMMAND_{index}_{label}_MISSING")
                    continue
                option_index = argv.index(option)
                value = argv[option_index + 1] if option_index + 1 < len(argv) else None
                if value != run_receipt.get(field):
                    errors.append(f"RESULT_RUN_RECEIPT_COMMAND_{label}_MISMATCH")
            trial_option = "--requested-trial-spec-ids"
            if is_strategy_command and trial_option not in argv:
                errors.append(f"RESULT_COMMAND_{index}_TRIAL_IDS_MISSING")
            elif trial_option in argv:
                option_index = argv.index(trial_option)
                value = argv[option_index + 1] if option_index + 1 < len(argv) else ""
                try:
                    trial_ids = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    trial_ids = None
                if not isinstance(trial_ids, list) or not all(
                    isinstance(trial_id, str) for trial_id in trial_ids
                ):
                    errors.append(f"RESULT_COMMAND_{index}_TRIAL_IDS_INVALID")
                else:
                    command_trial_ids.update(trial_ids)
        requested = run_receipt.get("requested") if isinstance(run_receipt, Mapping) else {}
        if command_trial_ids != set((requested or {}).get("trial_spec_ids") or []):
            errors.append("RESULT_RUN_RECEIPT_COMMAND_TRIAL_IDS_MISMATCH")
    else:
        errors.append("RESULT_EXECUTION_RECEIPT_MISSING")
    sibling_name = "result.json" if path.name == "final_result.json" else "final_result.json"
    sibling_path = path.parent / sibling_name
    if sibling_path.is_file() and load_json(sibling_path) != payload:
        errors.append("RESULT_FINAL_RESULT_MISMATCH")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, default=PROPOSAL_RELATIVE)
    parser.add_argument("--isolated-root", type=Path)
    parser.add_argument("--baseline-dir", type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--features", type=Path)
    parser.add_argument("--regime-history", type=Path)
    parser.add_argument("--execution-date", default="2026-05-12")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=EVIDENCE_RELATIVE,
    )
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    if args.verify is None and any(
        value is None
        for value in (args.isolated_root, args.baseline_dir, args.candidate_dir, args.features, args.regime_history)
    ):
        parser.error("execution requires isolated root and all real data inputs")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    supplied = list(argv) if argv is not None else sys.argv[1:]
    args = parse_args(supplied)
    try:
        if args.verify is not None:
            result = verify_evidence(args.verify)
        else:
            result = run(
                args,
                [sys.executable, "-m", "app.research.isolated_shadow_plan_replay", *supplied],
            )
    except (IsolatedReplayError, FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "NO-GO_EVIDENCE_UNAVAILABLE",
            "reason_codes": [str(error).split(":", 1)[0]],
            "detail": str(error),
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "DELIVERED_CANDIDATE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
