"""把 exact-regime h20 evidence 支線收斂成單一 mainline 決策。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research.contracts import canonical_json_bytes, content_hash
from app.research import legacy_regime_authority_admission as legacy_admission
from app.research import shadow_replay_reconciled_feasibility as reconciled


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "exact-regime-evidence-phase-closure.v1"
CURRENT_RELATIVE = reconciled.EVIDENCE_RELATIVE
LEGACY_RELATIVE = legacy_admission.EVIDENCE_RELATIVE
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-EXACT-REGIME-EVIDENCE-PHASE-CLOSURE-V1/closure.json"
)
ALLOWED_STATUSES = {
    "GO_REPLAY",
    "NO-GO_CLOSE_EXACT_H20_PHASE",
    "BLOCKED_EVIDENCE_CONFLICT",
}


class PhaseClosureError(RuntimeError):
    """phase closure 的 committed evidence 不合法。"""


def _safe_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise PhaseClosureError("PATH_ESCAPE")
    lexical_root = root.absolute()
    if lexical_root.is_symlink() or lexical_root.resolve(strict=True) != lexical_root:
        raise PhaseClosureError("ROOT_SYMLINK")
    cursor = lexical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise PhaseClosureError("PATH_SYMLINK")
    try:
        cursor.resolve(strict=False).relative_to(lexical_root)
    except ValueError as error:
        raise PhaseClosureError("PATH_ESCAPE") from error
    return cursor


def _committed_json(root: Path, relative: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = _safe_path(root, relative)
    try:
        working = path.read_bytes()
    except OSError as error:
        raise PhaseClosureError("EVIDENCE_UNREADABLE") from error
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise PhaseClosureError("EVIDENCE_NOT_COMMITTED")
    if result.stdout != working:
        raise PhaseClosureError("EVIDENCE_WORKTREE_DRIFT")
    try:
        payload = json.loads(working)
    except json.JSONDecodeError as error:
        raise PhaseClosureError("EVIDENCE_INVALID_JSON") from error
    if not isinstance(payload, dict):
        raise PhaseClosureError("EVIDENCE_NOT_OBJECT")
    return payload, {
        "path": relative.as_posix(),
        "sha256": "sha256:" + hashlib.sha256(working).hexdigest(),
        "commit_status": "MATCHED",
    }


def decide(current: Mapping[str, Any], legacy: Mapping[str, Any]) -> dict[str, Any]:
    conflicts = [
        *(f"CURRENT:{item}" for item in reconciled.validate_audit(current)),
        *(f"LEGACY:{item}" for item in legacy_admission.validate_audit(legacy)),
    ]
    current_feasible = [str(item) for item in current.get("feasible_identities") or []]
    legacy_feasible = [str(item) for item in legacy.get("feasible_identities") or []]
    current_status = str(current.get("status") or "")
    legacy_status = str(legacy.get("status") or "")

    current_ready = current_status == "READY_FOR_SCOPE_DECISION" and bool(current_feasible)
    legacy_ready = legacy_status == "READY_FOR_STAGED_MIGRATION" and bool(legacy_feasible)
    current_closed = current_status == "NO-GO_NO_ELIGIBLE_REGIME" and not current_feasible
    legacy_closed = legacy_status in {
        "NO-GO_NO_ELIGIBLE_EPISODE",
        "BLOCKED_AUTHORITY_NOT_ADMISSIBLE",
    } and not legacy_feasible

    if current_status == "READY_FOR_SCOPE_DECISION" and not current_feasible:
        conflicts.append("CURRENT_FALSE_READY")
    if legacy_status == "READY_FOR_STAGED_MIGRATION" and not legacy_feasible:
        conflicts.append("LEGACY_FALSE_READY")
    if current_feasible and not current_ready:
        conflicts.append("CURRENT_FEASIBLE_STATUS_CONFLICT")
    if legacy_feasible and not legacy_ready:
        conflicts.append("LEGACY_FEASIBLE_STATUS_CONFLICT")

    if conflicts:
        status = "BLOCKED_EVIDENCE_CONFLICT"
    elif current_ready or legacy_ready:
        status = "GO_REPLAY"
    elif current_closed and legacy_closed:
        status = "NO-GO_CLOSE_EXACT_H20_PHASE"
    else:
        status = "BLOCKED_EVIDENCE_CONFLICT"
        conflicts.append("EVIDENCE_STATUS_COMBINATION_UNHANDLED")

    if conflicts:
        reason_codes = sorted(set(conflicts))
    elif status == "GO_REPLAY":
        reason_codes = ["H20_SAFE_EXACT_IDENTITY_AVAILABLE"]
    else:
        reason_codes = [
            "CURRENT_AUTHORITY_HAS_ZERO_H20_SAFE_EXACT_IDENTITIES",
            "LEGACY_HISTORY_HAS_ZERO_H20_SAFE_EXACT_IDENTITIES",
            (
                "LEGACY_AUTHORITY_NOT_ADMISSIBLE"
                if legacy_status == "BLOCKED_AUTHORITY_NOT_ADMISSIBLE"
                else "LEGACY_AUTHORITY_HAS_NO_H20_SAFE_EPISODE"
            ),
        ]

    return {
        "status": status,
        "reason_codes": reason_codes,
        "current": {
            "status": current_status,
            "episode_count": int(current.get("episode_count") or 0),
            "feasible_identities": sorted(current_feasible),
            "fixed_scope": current.get("fixed_scope"),
        },
        "legacy": {
            "status": legacy_status,
            "episode_count": int(legacy.get("episode_count") or 0),
            "feasible_identities": sorted(legacy_feasible),
            "authority_status": legacy.get("lineage_authority_status"),
            "reason_codes": sorted(str(item) for item in legacy.get("reason_codes") or []),
        },
        "forks": {
            "replay": "AUTHORIZED_BY_EVIDENCE" if status == "GO_REPLAY" else "CLOSED_NO_GO",
            "external_backfill": "NOT_JUSTIFIED_BY_AVAILABLE_EVIDENCE",
            "scope_change": "PENDING_EXPLICIT_ARCHITECTURE_DECISION",
        },
    }


def build_closure(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    project_root = project_root.resolve()
    current, current_record = _committed_json(project_root, CURRENT_RELATIVE)
    legacy, legacy_record = _committed_json(project_root, LEGACY_RELATIVE)
    decision = decide(current, legacy)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "closure_id": "",
        **decision,
        "contract": {
            "root_question": "exact_h20_replay_or_same_scope_backfill",
            "horizon": 20,
            "entry_delay_trade_days": 1,
            "exact_identity_required": True,
            "research_only": True,
            "production_change_allowed": False,
            "network_requests": 0,
            "raw_data_writes": 0,
        },
        "sources": {"current": current_record, "legacy": legacy_record},
        "mainline": {
            "phase": "exact_regime_h20_evidence_activation",
            "closed": decision["status"] == "NO-GO_CLOSE_EXACT_H20_PHASE",
            "next_step": "NEW_ARCHITECTURE_SCOPE_DECISION" if decision["status"] != "GO_REPLAY" else "ISOLATED_REPLAY",
            "waiting_conditions": (
                ["explicit horizon or exact-identity contract decision"]
                if decision["status"] == "NO-GO_CLOSE_EXACT_H20_PHASE"
                else []
            ),
        },
    }
    payload["closure_id"] = content_hash(payload, omit={"closure_id"})
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


def validate_closure(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("status") not in ALLOWED_STATUSES:
        errors.append("STATUS_INVALID")
    if payload.get("closure_id") != content_hash(payload, omit={"closure_id"}):
        errors.append("CLOSURE_ID_MISMATCH")
    current = payload.get("current")
    legacy = payload.get("legacy")
    mainline = payload.get("mainline")
    if not isinstance(current, Mapping) or not isinstance(legacy, Mapping):
        errors.append("DECISION_SECTIONS_INVALID")
        current = {}
        legacy = {}
    if not isinstance(mainline, Mapping):
        errors.append("MAINLINE_SECTION_INVALID")
        mainline = {}
    if payload.get("status") == "GO_REPLAY" and not (
        current.get("feasible_identities") or legacy.get("feasible_identities")
    ):
        errors.append("FALSE_GO")
    if payload.get("status") == "NO-GO_CLOSE_EXACT_H20_PHASE" and not mainline.get("closed"):
        errors.append("FALSE_PHASE_CLOSURE")
    if any(value.startswith("/") for value in _strings(payload)):
        errors.append("ABSOLUTE_PATH_FORBIDDEN")
    if any(value in {"generated_at", "timestamp", "mtime"} for value in _strings(payload)):
        errors.append("NONDETERMINISTIC_FIELD_FORBIDDEN")
    return sorted(set(errors))


def encode_closure(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _evidence_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise PhaseClosureError("EVIDENCE_PATH_NOT_CANONICAL")
    return _safe_path(project_root, path)


def write_closure(path: Path) -> dict[str, Any]:
    payload = build_closure()
    errors = validate_closure(payload)
    if errors:
        raise PhaseClosureError("CLOSURE_VALIDATION_FAILED:" + ",".join(errors))
    target = _evidence_path(path, PROJECT_ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_closure(payload))
    return payload


def verify_closure(path: Path) -> dict[str, Any]:
    try:
        target = _evidence_path(path, PROJECT_ROOT)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise PhaseClosureError("EVIDENCE_NOT_OBJECT")
        errors = validate_closure(payload)
        if raw != encode_closure(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_closure():
            errors.append("CLOSURE_RECOMPUTE_MISMATCH")
    except (OSError, json.JSONDecodeError, PhaseClosureError) as error:
        return {"status": "FAIL", "errors": [str(error)]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="close exact-regime h20 evidence phase")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_closure(args.verify) if args.verify else write_closure(args.output)
    except PhaseClosureError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result if args.verify else {"status": result["status"], "closure_id": result["closure_id"]}, sort_keys=True))
    return 0 if not args.verify or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
