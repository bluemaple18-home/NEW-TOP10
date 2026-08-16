"""產生 entry-regime cohort 的研究架構決策與 fail-closed 證據。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research.contracts import canonical_json_bytes, content_hash
from app.research import exact_regime_evidence_phase_closure as phase_closure


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "entry-regime-cohort-architecture-decision.v1"
SELECTED_STATUS = "SELECT_ENTRY_REGIME_COHORT_FOR_FEASIBILITY"
SUCCESSOR_CARD = "CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1"
ARCHITECTURE_RELATIVE = Path("docs/architecture/entry_regime_cohort_replay_v1.md")
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1/decision.json"
)
COMMITTED_SOURCE_RELATIVES = (
    phase_closure.EVIDENCE_RELATIVE,
    ARCHITECTURE_RELATIVE,
    Path("scripts/run_backtest_strategy_matrix.py"),
    Path("scripts/run_backtest_replay.py"),
    Path("scripts/run_autonomous_research.py"),
    Path("app/modeling/sealed_oos.py"),
    Path("config/regime_research_contract.json"),
)
EXPECTED_INVARIANTS = {
    "horizon_trade_bars": 20,
    "entry_delay_trade_days": 1,
    "entry_identity_as_of_ranking_date": True,
    "future_path_is_descriptive_only": True,
    "global_chronological_split": True,
    "outcome_interval_purge_at_both_boundaries": True,
    "minimum_embargo_trade_days": 20,
    "old_episode_split_reuse_allowed": False,
    "sealed_outcome_access_allowed": False,
}
EXPECTED_STATISTICAL_CONTRACT = {
    "observation_grain": "ranking_date_x_scenario_x_top_n_portfolio",
    "dependence_unit": "overlap_component",
    "family_grain": "scenario_x_entry_cohort_x_primary_endpoint",
    "multiplicity": "BONFERRONI",
    "minimum_independent_components": "max(20,ceil(log2(M/0.05)))",
    "claim_boundary": "associational_h20_outcome_conditional_on_entry_cohort",
}
EXPECTED_SUCCESSOR = {
    "card_id": SUCCESSOR_CARD,
    "authorized_action": "OUTCOME_FREE_CAPACITY_FEASIBILITY_AUDIT_ONLY",
    "only_go_status": "FEASIBLE_FOR_PREREGISTRATION",
    "no_go_status": "NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY",
}
EXPECTED_SAFETY = {
    "research_only": True,
    "replay_ready": False,
    "promotion_ready": False,
    "production_ready": False,
    "runtime_change_allowed": False,
}


class ArchitectureDecisionError(RuntimeError):
    """架構決策的 authority、來源或輸出不合法。"""


def _safe_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise ArchitectureDecisionError("PATH_ESCAPE")
    lexical_root = root.absolute()
    if lexical_root.is_symlink() or lexical_root.resolve(strict=True) != lexical_root:
        raise ArchitectureDecisionError("ROOT_SYMLINK")
    cursor = lexical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ArchitectureDecisionError("PATH_SYMLINK")
    try:
        cursor.resolve(strict=False).relative_to(lexical_root)
    except ValueError as error:
        raise ArchitectureDecisionError("PATH_ESCAPE") from error
    return cursor


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _committed_source(root: Path, relative: Path) -> tuple[bytes, dict[str, str]]:
    path = _safe_path(root, relative)
    try:
        working = path.read_bytes()
    except OSError as error:
        raise ArchitectureDecisionError(f"SOURCE_UNREADABLE:{relative.as_posix()}") from error
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ArchitectureDecisionError(f"SOURCE_NOT_COMMITTED:{relative.as_posix()}")
    if result.stdout != working:
        raise ArchitectureDecisionError(f"SOURCE_WORKTREE_DRIFT:{relative.as_posix()}")
    return working, {
        "path": relative.as_posix(),
        "sha256": _sha256(working),
        "commit_status": "MATCHED",
    }


def _closure_from_bytes(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ArchitectureDecisionError("CLOSURE_INVALID_JSON") from error
    if not isinstance(payload, dict):
        raise ArchitectureDecisionError("CLOSURE_NOT_OBJECT")
    errors = phase_closure.validate_closure(payload)
    if errors:
        raise ArchitectureDecisionError("CLOSURE_INVALID:" + ",".join(errors))
    if payload.get("status") != "NO-GO_CLOSE_EXACT_H20_PHASE":
        raise ArchitectureDecisionError("EXACT_H20_PHASE_NOT_CLOSED")
    if not bool((payload.get("mainline") or {}).get("closed")):
        raise ArchitectureDecisionError("EXACT_H20_CLOSURE_FALSE")
    return payload


def _required_architecture_markers(raw: bytes) -> list[str]:
    text = raw.decode("utf-8")
    markers = (
        SELECTED_STATUS,
        "entry-cohort-calendar-split.v1",
        "outcome-interval purge",
        "Future path只能",
        "research_only=true",
        "replay_ready=false",
        "promotion_ready=false",
        "production_ready=false",
        SUCCESSOR_CARD,
    )
    return [marker for marker in markers if marker not in text]


def build_decision(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    root = project_root.resolve()
    source_records: dict[str, dict[str, str]] = {}
    committed_bytes: dict[Path, bytes] = {}
    for relative in COMMITTED_SOURCE_RELATIVES:
        raw, record = _committed_source(root, relative)
        committed_bytes[relative] = raw
        source_records[relative.as_posix()] = record

    closure = _closure_from_bytes(committed_bytes[phase_closure.EVIDENCE_RELATIVE])
    architecture_raw = committed_bytes[ARCHITECTURE_RELATIVE]
    missing_markers = _required_architecture_markers(architecture_raw)
    if missing_markers:
        raise ArchitectureDecisionError(
            "ARCHITECTURE_MARKERS_MISSING:" + ",".join(missing_markers)
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "decision_id": "",
        "status": SELECTED_STATUS,
        "root_question": "preserve_h20_d1_and_as_of_identity_with_safe_successor",
        "closure_id": closure["closure_id"],
        "candidate_decisions": [
            {"candidate": "ENTIRE_HOLDING_EXACT_REGIME", "decision": "KEEP_CLOSED_NO_GO"},
            {"candidate": "SHORTER_HORIZON", "decision": "REJECT_SCOPE_CHANGE"},
            {"candidate": "DILUTED_OR_POOLED_IDENTITY", "decision": "REJECT_SEMANTIC_DILUTION"},
            {"candidate": "ENTRY_REGIME_COHORT", "decision": "SELECT_FOR_FEASIBILITY"},
        ],
        "invariants": EXPECTED_INVARIANTS,
        "statistical_contract": EXPECTED_STATISTICAL_CONTRACT,
        "successor": EXPECTED_SUCCESSOR,
        "safety": EXPECTED_SAFETY,
        "sources": {
            "committed": [source_records[key] for key in sorted(source_records)],
        },
    }
    payload["decision_id"] = content_hash(payload, omit={"decision_id"})
    return payload


def _strings(value: Any):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)
    elif isinstance(value, str):
        yield value


def validate_decision(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("status") != SELECTED_STATUS:
        errors.append("STATUS_INVALID")
    if payload.get("decision_id") != content_hash(payload, omit={"decision_id"}):
        errors.append("DECISION_ID_MISMATCH")
    if payload.get("successor") != EXPECTED_SUCCESSOR:
        errors.append("SUCCESSOR_INVALID")
    if payload.get("safety") != EXPECTED_SAFETY:
        errors.append("SAFETY_INVALID")
    if payload.get("invariants") != EXPECTED_INVARIANTS:
        errors.append("INVARIANTS_INVALID")
    if payload.get("statistical_contract") != EXPECTED_STATISTICAL_CONTRACT:
        errors.append("STATISTICAL_CONTRACT_INVALID")
    if any(value.startswith("/") for value in _strings(payload)):
        errors.append("ABSOLUTE_PATH_FORBIDDEN")
    if any(value in {"generated_at", "timestamp", "mtime"} for value in _strings(payload)):
        errors.append("NONDETERMINISTIC_FIELD_FORBIDDEN")
    return sorted(set(errors))


def encode_decision(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _evidence_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise ArchitectureDecisionError("EVIDENCE_PATH_NOT_CANONICAL")
    return _safe_path(project_root, path)


def write_decision(path: Path) -> dict[str, Any]:
    payload = build_decision()
    errors = validate_decision(payload)
    if errors:
        raise ArchitectureDecisionError("DECISION_VALIDATION_FAILED:" + ",".join(errors))
    target = _evidence_path(path, PROJECT_ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_decision(payload))
    return payload


def verify_decision(path: Path) -> dict[str, Any]:
    try:
        target = _evidence_path(path, PROJECT_ROOT)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ArchitectureDecisionError("EVIDENCE_NOT_OBJECT")
        errors = validate_decision(payload)
        if raw != encode_decision(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_decision():
            errors.append("DECISION_RECOMPUTE_MISMATCH")
    except (OSError, json.JSONDecodeError, ArchitectureDecisionError) as error:
        return {"status": "FAIL", "errors": [str(error)]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build entry-regime cohort architecture decision")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_decision(args.verify) if args.verify else write_decision(args.output)
    except ArchitectureDecisionError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    output = result if args.verify else {"status": result["status"], "decision_id": result["decision_id"]}
    print(json.dumps(output, sort_keys=True))
    return 0 if not args.verify or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
