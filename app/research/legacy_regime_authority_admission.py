"""稽核 legacy regime history 是否可升級為 exact-regime authority。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research.contracts import canonical_json_bytes, content_hash
from app.research import shadow_replay_regime_feasibility as feasibility
from scripts import build_market_regime_history as regime_builder
from scripts import run_autonomous_research as regime_research


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "legacy-regime-authority-admission.v1"
LEGACY_RELATIVE = Path(
    "artifacts/model_experiments/market_regime_history_2023-11-21_2026-05-15.json"
)
CURRENT_RELATIVE = Path("artifacts/market_regime_history.json")
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-LEGACY-REGIME-AUTHORITY-ADMISSION-AUDIT-V1/admission.json"
)
MAX_EVIDENCE_BYTES = 256 * 1024
ALLOWED_STATUSES = {
    "READY_FOR_STAGED_MIGRATION",
    "NO-GO_NO_ELIGIBLE_EPISODE",
    "BLOCKED_AUTHORITY_NOT_ADMISSIBLE",
}


class LegacyAdmissionError(RuntimeError):
    """legacy authority 稽核輸入或 evidence 不合法。"""


def _safe_relative(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise LegacyAdmissionError("PATH_ESCAPE")
    lexical_root = root.absolute()
    if lexical_root.is_symlink() or lexical_root.resolve(strict=True) != lexical_root:
        raise LegacyAdmissionError("ROOT_SYMLINK")
    cursor = lexical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise LegacyAdmissionError("PATH_SYMLINK")
    try:
        cursor.resolve(strict=False).relative_to(lexical_root)
    except ValueError as error:
        raise LegacyAdmissionError("PATH_ESCAPE") from error
    return cursor


def _sha256(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise LegacyAdmissionError("SOURCE_MISSING_OR_SYMLINK")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LegacyAdmissionError("SOURCE_UNREADABLE") from error
    if not isinstance(payload, dict):
        raise LegacyAdmissionError("SOURCE_NOT_OBJECT")
    return payload


def _validate_rows(payload: Mapping[str, Any], expected_schema: str) -> list[dict[str, Any]]:
    if payload.get("schema_version") != expected_schema:
        raise LegacyAdmissionError("SOURCE_SCHEMA_INVALID")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise LegacyAdmissionError("ROWS_INVALID")
    dates = [str(row.get("trade_date") or "") for row in rows]
    if any(not value for value in dates) or dates != sorted(dates) or len(dates) != len(set(dates)):
        raise LegacyAdmissionError("TRADE_DATES_INVALID")
    summary = payload.get("summary") or {}
    if (
        summary.get("trade_days") != len(rows)
        or summary.get("start_date") != dates[0]
        or summary.get("end_date") != dates[-1]
    ):
        raise LegacyAdmissionError("SUMMARY_MISMATCH")
    return rows


def _migrate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = tuple(regime_builder.RegimeRow.__dataclass_fields__)
    try:
        source_rows = [regime_builder.RegimeRow(**{field: row.get(field) for field in fields}) for row in rows]
        migrated = regime_builder.enrich_regime_contract_rows(source_rows)
    except (TypeError, ValueError, KeyError) as error:
        raise LegacyAdmissionError("V2_MIGRATION_FAILED") from error
    if len(migrated) != len(rows):
        raise LegacyAdmissionError("V2_MIGRATION_ROW_COUNT_DRIFT")
    for before, after in zip(rows, migrated, strict=True):
        if before.get("trade_date") != after.get("trade_date") or before.get("regime_label") != after.get("base_regime"):
            raise LegacyAdmissionError("V2_MIGRATION_BASE_IDENTITY_DRIFT")
    if not regime_research.validate_as_of_regime_rows(migrated)["ok"]:
        raise LegacyAdmissionError("V2_MIGRATION_AS_OF_INVALID")
    return migrated


def _identity(row: Mapping[str, Any]) -> str:
    return regime_research.regime_identity_id(regime_research.regime_row_identity(dict(row)))


def _producer_lineage(payload: Mapping[str, Any], project_root: Path) -> tuple[dict[str, Any], list[str]]:
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), Mapping) else {}
    raw_path = str(inputs.get("features") or "")
    expected = str(inputs.get("features_sha256") or "")
    path = Path(raw_path).expanduser() if raw_path else Path()
    if raw_path and not path.is_absolute():
        path = project_root / path
    available = bool(raw_path) and path.is_file() and not path.is_symlink()
    observed = _sha256(path) if available else None
    reasons: list[str] = []
    if not available:
        reasons.append("LEGACY_PRODUCER_INPUT_MISSING")
    if not expected.startswith("sha256:"):
        reasons.append("LEGACY_INPUT_HASH_NOT_RECORDED")
    elif observed != expected:
        reasons.append("LEGACY_INPUT_HASH_MISMATCH")
    return {
        "producer_input_available": available,
        "producer_input_hash_recorded": expected.startswith("sha256:"),
        "producer_input_hash_matches": bool(observed and observed == expected),
        "producer_input_reference_kind": "ABSOLUTE" if Path(raw_path).is_absolute() else "REPOSITORY_RELATIVE",
    }, reasons


def _episode_summary(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    dates = [date.fromisoformat(row["trade_date"]) for row in rows]
    matrix = feasibility.episode_matrix(rows, dates)
    summaries: list[dict[str, Any]] = []
    feasible_identities: set[str] = set()
    for item in matrix:
        safe = item["horizon_safe_dates"]["20"]
        if safe:
            feasible_identities.add(item["identity"])
        summaries.append(
            {
                "identity": item["identity"],
                "episode_id": item["episode_id"],
                "start_date": item["start_date"],
                "end_date": item["end_date"],
                "trade_date_count": item["trade_date_count"],
                "h20_safe_ranking_date_count": len(safe),
                "h20_first_safe_date": safe[0] if safe else None,
                "h20_last_safe_date": safe[-1] if safe else None,
            }
        )
    return summaries, sorted(feasible_identities)


def build_audit(
    *, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None
) -> dict[str, Any]:
    project_root = project_root.resolve()
    authority_root = (authority_root or project_root).resolve()
    legacy_path = _safe_relative(authority_root, LEGACY_RELATIVE)
    current_path = _safe_relative(authority_root, CURRENT_RELATIVE)
    legacy = _load(legacy_path)
    current = _load(current_path)
    legacy_rows = _validate_rows(legacy, "market-regime-history.v1")
    current_rows = _validate_rows(current, "market-regime-history.v2")
    migrated = _migrate(legacy_rows)
    lineage, reasons = _producer_lineage(legacy, authority_root)

    current_by_date = {row["trade_date"]: row for row in current_rows}
    overlap = [row for row in migrated if row["trade_date"] in current_by_date]
    drift = []
    for row in overlap:
        legacy_id = _identity(row)
        current_id = _identity(current_by_date[row["trade_date"]])
        if legacy_id != current_id:
            drift.append(
                {"trade_date": row["trade_date"], "legacy_identity": legacy_id, "current_identity": current_id}
            )
    if drift:
        reasons.append("OVERLAP_EXACT_IDENTITY_DRIFT")

    episodes, feasible_identities = _episode_summary(migrated)
    status = (
        "BLOCKED_AUTHORITY_NOT_ADMISSIBLE"
        if reasons
        else "READY_FOR_STAGED_MIGRATION"
        if feasible_identities
        else "NO-GO_NO_ELIGIBLE_EPISODE"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": "",
        "status": status,
        "reason_codes": sorted(set(reasons)) if reasons else ([] if feasible_identities else ["NO_H20_SAFE_EXACT_REGIME_EPISODE"]),
        "contract": {
            "research_only": True,
            "raw_data_writes": 0,
            "network_requests": 0,
            "base_regime_definition_changed": False,
            "horizon": 20,
            "entry_delay_trade_days": 1,
        },
        "sources": {
            "legacy": {"path": LEGACY_RELATIVE.as_posix(), "sha256": _sha256(legacy_path)},
            "current": {"path": CURRENT_RELATIVE.as_posix(), "sha256": _sha256(current_path)},
            "canonical_builder": "scripts/build_market_regime_history.py::enrich_regime_contract_rows",
            "canonical_episode_helper": "app/research/shadow_replay_regime_feasibility.py::episode_matrix",
        },
        "legacy": {
            "row_count": len(legacy_rows),
            "start_date": legacy_rows[0]["trade_date"],
            "end_date": legacy_rows[-1]["trade_date"],
            "migration_row_count": len(migrated),
            **lineage,
        },
        "overlap_reconciliation": {
            "overlap_date_count": len(overlap),
            "exact_identity_match_count": len(overlap) - len(drift),
            "exact_identity_drift_count": len(drift),
            "drift_sample": drift[:20],
        },
        "episode_count": len(episodes),
        "episodes": episodes,
        "feasible_identities": feasible_identities,
        "lineage_authority_status": "PROVEN" if not reasons else "UNPROVEN",
    }
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


def validate_audit(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("status") not in ALLOWED_STATUSES:
        errors.append("STATUS_INVALID")
    if payload.get("audit_id") != content_hash(payload, omit={"audit_id"}):
        errors.append("AUDIT_ID_MISMATCH")
    reasons = payload.get("reason_codes")
    if payload.get("status") == "BLOCKED_AUTHORITY_NOT_ADMISSIBLE" and not reasons:
        errors.append("BLOCKED_WITHOUT_REASON")
    if payload.get("status") == "READY_FOR_STAGED_MIGRATION" and (reasons or not payload.get("feasible_identities")):
        errors.append("FALSE_READY_STATUS")
    if any(value.startswith("/") for value in _strings(payload)):
        errors.append("ABSOLUTE_PATH_FORBIDDEN")
    if len(canonical_json_bytes(payload)) + 1 > MAX_EVIDENCE_BYTES:
        errors.append("EVIDENCE_SIZE_LIMIT_EXCEEDED")
    return sorted(set(errors))


def encode_audit(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _evidence_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise LegacyAdmissionError("EVIDENCE_PATH_NOT_CANONICAL")
    return _safe_relative(project_root, path)


def write_audit(
    path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    authority_root: Path | None = None,
) -> dict[str, Any]:
    payload = build_audit(project_root=project_root, authority_root=authority_root)
    errors = validate_audit(payload)
    if errors:
        raise LegacyAdmissionError("AUDIT_VALIDATION_FAILED:" + ",".join(errors))
    target = _evidence_path(path, project_root.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_audit(payload))
    return payload


def verify_audit(
    path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    authority_root: Path | None = None,
) -> dict[str, Any]:
    try:
        target = _evidence_path(path, project_root.resolve())
        raw = target.read_bytes()
        payload = json.loads(raw)
        errors = validate_audit(payload)
        if raw != encode_audit(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_audit(project_root=project_root, authority_root=authority_root):
            errors.append("AUDIT_RECOMPUTE_MISMATCH")
    except (OSError, json.JSONDecodeError, LegacyAdmissionError) as error:
        return {"status": "FAIL", "errors": [str(error)]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="audit legacy regime authority admission")
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
    except LegacyAdmissionError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result if args.verify else {"status": result["status"], "audit_id": result["audit_id"]}, sort_keys=True))
    return 0 if not args.verify or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
