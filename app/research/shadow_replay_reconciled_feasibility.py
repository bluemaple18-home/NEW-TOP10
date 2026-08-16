"""以 reconciled authority snapshot 重跑 exact-regime horizon feasibility。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.research import shadow_replay_authority_reconciliation as reconciliation
from app.research import shadow_replay_availability as availability
from app.research import shadow_replay_coverage_plan as coverage
from app.research import shadow_replay_regime_feasibility as feasibility
from app.research.contracts import canonical_json_bytes, content_hash
from scripts import run_autonomous_research as regime_research


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "shadow-replay-reconciled-feasibility.v2"
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-RECONCILED-REGIME-FEASIBILITY-V2/feasibility.json"
)
ALLOWED_STATUSES = {
    "READY_FOR_SCOPE_DECISION",
    "NO-GO_NO_ELIGIBLE_REGIME",
    "BLOCKED_AUTHORITY_CONFLICT",
}


class ReconciledFeasibilityError(RuntimeError):
    """表示 reconciliation 或 feasibility authority 不合法。"""


def _with_audit_id(payload: dict[str, Any]) -> dict[str, Any]:
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})
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


def build_audit(
    *, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None
) -> dict[str, Any]:
    project_root = project_root.resolve()
    try:
        authority_root = coverage.authorize_explicit_authority_root(
            project_root, authority_root or coverage.discover_authority_root(project_root)
        )
        authority = reconciliation.build_receipt(
            project_root=project_root,
            authority_root=authority_root,
        )
    except (coverage.CoveragePlanError, reconciliation.AuthorityReconciliationError) as error:
        raise ReconciledFeasibilityError("AUTHORITY_RECONCILIATION_FAILED") from error
    if (
        authority.get("status") != "READY_FOR_FEASIBILITY_AUDIT"
        or reconciliation.validate_receipt(authority)
    ):
        raise ReconciledFeasibilityError("AUTHORITY_RECONCILIATION_NOT_READY")
    try:
        committed_authority, authority_record = reconciliation._committed_json(
            project_root, reconciliation.EVIDENCE_RELATIVE
        )
    except reconciliation.AuthorityReconciliationError as error:
        raise ReconciledFeasibilityError("RECONCILIATION_EVIDENCE_CONFLICT") from error
    if committed_authority != authority:
        raise ReconciledFeasibilityError("RECONCILIATION_EVIDENCE_DRIFT")

    runtime_sources = authority["runtime_sources"]
    try:
        regime_path = reconciliation._safe_path(
            authority_root, Path(runtime_sources["regime"]["path"])
        )
        if reconciliation._sha256_file(regime_path) != runtime_sources["regime"]["sha256"]:
            raise ReconciledFeasibilityError("REGIME_SOURCE_HASH_MISMATCH")
        history = json.loads(regime_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, reconciliation.AuthorityReconciliationError) as error:
        raise ReconciledFeasibilityError("REGIME_SOURCE_UNREADABLE") from error
    rows = history.get("rows") if isinstance(history, Mapping) else None
    if not isinstance(rows, list) or not regime_research.validate_as_of_regime_rows(rows)["ok"]:
        raise ReconciledFeasibilityError("REGIME_AS_OF_CONFLICT")

    try:
        features_path = reconciliation._safe_path(
            authority_root, Path(runtime_sources["features"]["path"])
        )
        if reconciliation._sha256_file(features_path) != runtime_sources["features"]["sha256"]:
            raise ReconciledFeasibilityError("FEATURE_SOURCE_HASH_MISMATCH")
        _, trade_dates = availability._feature_inventory(authority_root)
    except (OSError, reconciliation.AuthorityReconciliationError) as error:
        raise ReconciledFeasibilityError("FEATURE_SOURCE_UNREADABLE") from error
    if not trade_dates:
        raise ReconciledFeasibilityError("FEATURE_TRADE_DATE_AUTHORITY_MISSING")

    episodes = feasibility.episode_matrix(rows, trade_dates)
    feasible_identities = sorted(
        {item["identity"] for item in episodes if item["shared_dates"]}
    )
    fixed = [item for item in episodes if item["identity"] == feasibility.FIXED_SCOPE]
    status = (
        "READY_FOR_SCOPE_DECISION"
        if feasible_identities
        else "NO-GO_NO_ELIGIBLE_REGIME"
    )
    return _with_audit_id(
        {
            "schema_version": SCHEMA_VERSION,
            "audit_id": "",
            "status": status,
            "reason_codes": (
                []
                if feasible_identities
                else ["NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE"]
            ),
            "horizons": list(feasibility.HORIZONS),
            "entry_delay_trade_days": 1,
            "lineage_authority_status": "UNPROVEN",
            "reconciliation": {
                **authority_record,
                "receipt_id": authority["receipt_id"],
                "status": authority["status"],
            },
            "episode_count": len(episodes),
            "episodes": episodes,
            "feasible_identities": feasible_identities,
            "fixed_scope": {
                "identity": feasibility.FIXED_SCOPE,
                "maximum_episode_trade_date_count": max(
                    (item["trade_date_count"] for item in fixed), default=0
                ),
                "horizon_safe_dates": {
                    str(horizon): sorted(
                        {
                            date
                            for item in fixed
                            for date in item["horizon_safe_dates"][str(horizon)]
                        }
                    )
                    for horizon in feasibility.HORIZONS
                },
                "shared_dates": sorted(
                    {date for item in fixed for date in item["shared_dates"]}
                ),
            },
        }
    )


def validate_audit(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("status") not in ALLOWED_STATUSES:
        errors.append("STATUS_INVALID")
    if payload.get("audit_id") != content_hash(payload, omit={"audit_id"}):
        errors.append("AUDIT_ID_MISMATCH")
    if payload.get("lineage_authority_status") != "UNPROVEN":
        errors.append("LINEAGE_AUTHORITY_MUST_REMAIN_UNPROVEN")
    episodes = payload.get("episodes")
    if not isinstance(episodes, list) or payload.get("episode_count") != len(episodes):
        errors.append("EPISODE_MATRIX_INVALID")
    feasible = payload.get("feasible_identities")
    if not isinstance(feasible, list):
        errors.append("FEASIBLE_IDENTITIES_INVALID")
    elif payload.get("status") == "READY_FOR_SCOPE_DECISION" and not feasible:
        errors.append("FALSE_READY_STATUS")
    elif payload.get("status") == "NO-GO_NO_ELIGIBLE_REGIME" and feasible:
        errors.append("FALSE_NO_GO_STATUS")
    if (
        payload.get("status") == "NO-GO_NO_ELIGIBLE_REGIME"
        and payload.get("reason_codes")
        != ["NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE"]
    ):
        errors.append("NO_GO_REASON_INVALID")
    reconciliation_record = payload.get("reconciliation")
    if (
        not isinstance(reconciliation_record, Mapping)
        or reconciliation_record.get("path")
        != reconciliation.EVIDENCE_RELATIVE.as_posix()
        or reconciliation_record.get("status") != "READY_FOR_FEASIBILITY_AUDIT"
        or reconciliation_record.get("commit_status") != "MATCHED"
    ):
        errors.append("RECONCILIATION_IDENTITY_INVALID")
    if any(value.startswith("/") for value in _strings(payload)):
        errors.append("ABSOLUTE_PATH_FORBIDDEN")
    return sorted(set(errors))


def encode_audit(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _evidence_path(path: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise ReconciledFeasibilityError("EVIDENCE_PATH_NOT_CANONICAL")
    try:
        return reconciliation._safe_path(PROJECT_ROOT, path)
    except reconciliation.AuthorityReconciliationError as error:
        raise ReconciledFeasibilityError("EVIDENCE_PATH_INVALID") from error


def write_audit(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    target = _evidence_path(path)
    payload = build_audit(authority_root=authority_root)
    errors = validate_audit(payload)
    if errors:
        raise ReconciledFeasibilityError("AUDIT_VALIDATION_FAILED:" + ",".join(errors))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_audit(payload))
    return payload


def verify_audit(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    try:
        target = _evidence_path(path)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ReconciledFeasibilityError("EVIDENCE_NOT_OBJECT")
        errors = validate_audit(payload)
        if raw != encode_audit(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_audit(authority_root=authority_root):
            errors.append("AUDIT_RECOMPUTE_MISMATCH")
    except ReconciledFeasibilityError as error:
        return {"status": "FAIL", "errors": [str(error)]}
    except OSError:
        return {"status": "FAIL", "errors": ["IO_ERROR"]}
    except json.JSONDecodeError:
        return {"status": "FAIL", "errors": ["EVIDENCE_INVALID_JSON"]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="audit reconciled exact-regime feasibility")
    parser.add_argument("--authority-root", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = (
            verify_audit(args.verify, authority_root=args.authority_root)
            if args.verify
            else write_audit(args.output, authority_root=args.authority_root)
        )
    except ReconciledFeasibilityError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    except OSError:
        print(json.dumps({"status": "FAIL", "errors": ["IO_ERROR"]}, sort_keys=True))
        return 2
    print(
        json.dumps(
            result if args.verify else {"status": result["status"], "audit_id": result["audit_id"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not args.verify or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
