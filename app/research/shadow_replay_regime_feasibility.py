"""盤點 immutable exact-regime episode 是否可承載指定 holding horizon。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research import shadow_replay_availability as availability
from app.research import shadow_replay_coverage_plan as coverage
from app.research.contracts import canonical_json_bytes, content_hash
from app.research.shadow_plan_proposal import snapshot_protected_surfaces
from scripts import run_autonomous_research as regime_research
from scripts import run_backtest_strategy_matrix as strategy_matrix


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "shadow-replay-regime-feasibility.v1"
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/"
    "feasibility_audit.json"
)
COVERAGE_PLAN_RELATIVE = coverage.EVIDENCE_RELATIVE
HORIZONS = (10, 20)
FIXED_SCOPE = "NARROW_LEADER|BIG_BULL"
ALLOWED_STATUSES = {
    "READY_FOR_SCOPE_DECISION",
    "NO-GO_NO_ELIGIBLE_REGIME",
    "BLOCKED_AUTHORITY_CONFLICT",
}


class RegimeFeasibilityError(RuntimeError):
    """表示 immutable authority 或 evidence 契約不合法。"""


def _sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise RegimeFeasibilityError(f"SOURCE_MISSING_OR_SYMLINK:{path.as_posix()}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise RegimeFeasibilityError("PATH_ESCAPE")

    lexical_root = root.absolute()
    if lexical_root.is_symlink():
        raise RegimeFeasibilityError("SOURCE_SYMLINK")
    try:
        resolved_root = lexical_root.resolve(strict=True)
    except OSError as error:
        raise RegimeFeasibilityError("PATH_ESCAPE") from error
    if resolved_root != lexical_root:
        raise RegimeFeasibilityError("SOURCE_SYMLINK")

    path = lexical_root / relative
    cursor = lexical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise RegimeFeasibilityError("SOURCE_SYMLINK")
    try:
        path.resolve(strict=False).relative_to(resolved_root)
    except ValueError as error:
        raise RegimeFeasibilityError("PATH_ESCAPE") from error
    return path


def _committed_record(root: Path, relative: Path) -> dict[str, str]:
    path = _safe_path(root, relative)
    working_bytes = path.read_bytes()
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or result.stdout != working_bytes:
        raise RegimeFeasibilityError(f"COMMITTED_SOURCE_DRIFT:{relative.as_posix()}")
    return {"path": relative.as_posix(), "sha256": "sha256:" + hashlib.sha256(working_bytes).hexdigest()}


def _authority_record(root: Path, relative: Path) -> tuple[dict[str, str], list[str]]:
    try:
        return {**_committed_record(root, relative), "commit_status": "MATCHED"}, []
    except RegimeFeasibilityError as error:
        path = _safe_path(root, relative)
        return (
            {"path": relative.as_posix(), "sha256": _sha256_file(path), "commit_status": "DRIFT"},
            [str(error)],
        )


def discover_authority_root(project_root: Path = PROJECT_ROOT) -> Path:
    return coverage.discover_authority_root(project_root)


def _episode_safe_dates(
    episode: Mapping[str, Any], trade_dates: list[Any]
) -> dict[str, list[str]]:
    dates = {str(item) for item in episode["trade_dates"]}
    episode_id = str(episode["episode_id"])
    episode_by_date = {item: episode_id for item in dates}
    result: dict[str, list[str]] = {}
    for horizon in HORIZONS:
        try:
            safe = strategy_matrix.exact_horizon_safe_ranking_dates(
                dates,
                episode_by_date,
                trade_dates,
                horizon=horizon,
                entry_delay_trade_days=1,
            )
        except ValueError as error:
            if "NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE" not in str(error):
                raise RegimeFeasibilityError(f"CANONICAL_HELPER_FAILED:{error}") from error
            safe = set()
        result[str(horizon)] = sorted(safe or set())
    return result


def episode_matrix(rows: list[dict[str, Any]], trade_dates: list[Any]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for episode in regime_research.build_regime_episodes(rows):
        safe_by_horizon = _episode_safe_dates(episode, trade_dates)
        matrix.append(
            {
                "identity": str(episode["regime_id"]),
                "episode_id": str(episode["episode_id"]),
                "start_date": str(episode["start_date"]),
                "end_date": str(episode["end_date"]),
                "trade_date_count": len(episode["trade_dates"]),
                "trade_dates": list(episode["trade_dates"]),
                "horizon_safe_dates": safe_by_horizon,
                "shared_dates": sorted(
                    set(safe_by_horizon["10"]) & set(safe_by_horizon["20"])
                ),
            }
        )
    return sorted(matrix, key=lambda item: (item["identity"], item["start_date"], item["episode_id"]))


def _snapshot_hashes(authority_root: Path) -> tuple[str, str]:
    return (
        content_hash(availability._source_snapshot(authority_root)),
        content_hash(snapshot_protected_surfaces(project_root=authority_root)),
    )


def _coverage_plan(project_root: Path) -> dict[str, str]:
    record = _committed_record(project_root, COVERAGE_PLAN_RELATIVE)
    try:
        payload = json.loads((project_root / COVERAGE_PLAN_RELATIVE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RegimeFeasibilityError("COVERAGE_PLAN_UNREADABLE") from error
    if not isinstance(payload, dict) or payload.get("status") != "NO-GO_PLAN_UNAVAILABLE":
        raise RegimeFeasibilityError("COVERAGE_PLAN_AUTHORITY_CONFLICT")
    return record


def _with_audit_id(payload: dict[str, Any]) -> dict[str, Any]:
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})
    return payload


def build_audit(
    *, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None
) -> dict[str, Any]:
    project_root = project_root.resolve()
    try:
        authority_root = coverage.authorize_explicit_authority_root(
            project_root, authority_root or discover_authority_root(project_root)
        )
    except coverage.CoveragePlanError as error:
        raise RegimeFeasibilityError("AUTHORITY_ROOT_INVALID") from error
    before_sources, before_protected = _snapshot_hashes(authority_root)
    market_regime, market_conflicts = _authority_record(authority_root, availability.REGIME_RELATIVE)
    features, feature_conflicts = _authority_record(authority_root, availability.FEATURES_RELATIVE)
    sources = {
        "coverage_plan": _coverage_plan(authority_root),
        "market_regime": market_regime,
        "features": features,
        "canonical_helper": _committed_record(authority_root, Path("scripts/run_backtest_strategy_matrix.py")),
        "episode_builder": _committed_record(authority_root, Path("scripts/run_autonomous_research.py")),
    }
    conflicts = [*market_conflicts, *feature_conflicts]
    episodes: list[dict[str, Any]] = []
    if not conflicts:
        try:
            history = json.loads((authority_root / availability.REGIME_RELATIVE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RegimeFeasibilityError("REGIME_HISTORY_UNREADABLE") from error
        rows = history.get("rows") if isinstance(history, dict) and isinstance(history.get("rows"), list) else []
        as_of = regime_research.validate_as_of_regime_rows(rows)
        if not as_of["ok"]:
            conflicts.append("REGIME_AS_OF_CONFLICT")
        _, trade_dates = availability._feature_inventory(authority_root)
        if not trade_dates:
            conflicts.append("FEATURE_TRADE_DATE_AUTHORITY_MISSING")
        if not conflicts:
            episodes = episode_matrix(rows, trade_dates)
    fixed_episodes = [item for item in episodes if item["identity"] == FIXED_SCOPE]
    feasible = sorted({item["identity"] for item in episodes if item["shared_dates"]})
    after_sources, after_protected = _snapshot_hashes(authority_root)
    parity = {
        "fixed_sources_before_hash": before_sources,
        "fixed_sources_after_hash": after_sources,
        "fixed_sources_unchanged": before_sources == after_sources,
        "protected_surfaces_before_hash": before_protected,
        "protected_surfaces_after_hash": after_protected,
        "protected_surfaces_unchanged": before_protected == after_protected,
    }
    if not parity["fixed_sources_unchanged"] or not parity["protected_surfaces_unchanged"]:
        raise RegimeFeasibilityError("AUTHORITY_DRIFT_DURING_AUDIT")
    status = (
        "BLOCKED_AUTHORITY_CONFLICT"
        if conflicts
        else "READY_FOR_SCOPE_DECISION"
        if feasible
        else "NO-GO_NO_ELIGIBLE_REGIME"
    )
    return _with_audit_id(
        {
            "schema_version": SCHEMA_VERSION,
            "audit_id": "",
            "status": status,
            "reason_codes": sorted(conflicts) if conflicts else ([] if feasible else ["NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE"]),
            "horizons": list(HORIZONS),
            "entry_delay_trade_days": 1,
            "canonical_helper": "scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates",
            "lineage_authority_status": "UNPROVEN",
            "sources": sources,
            "episodes": episodes,
            "feasible_identities": feasible,
            "fixed_scope": {
                "identity": FIXED_SCOPE,
                "maximum_episode_trade_date_count": max((item["trade_date_count"] for item in fixed_episodes), default=0),
                "horizon_safe_dates": {
                    str(horizon): sorted({date for item in fixed_episodes for date in item["horizon_safe_dates"][str(horizon)]})
                    for horizon in HORIZONS
                },
                "shared_dates": sorted({date for item in fixed_episodes for date in item["shared_dates"]}),
            },
            "parity": parity,
        }
    )


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
    if payload.get("lineage_authority_status") != "UNPROVEN":
        errors.append("LINEAGE_AUTHORITY_MUST_REMAIN_UNPROVEN")
    if not isinstance(payload.get("episodes"), list):
        errors.append("EPISODE_MATRIX_MISSING")
    if payload.get("status") == "READY_FOR_SCOPE_DECISION" and not payload.get("feasible_identities"):
        errors.append("READY_WITHOUT_FEASIBLE_IDENTITY")
    for value in _strings(payload):
        if value.startswith("/"):
            errors.append(f"ABSOLUTE_PATH_FORBIDDEN:{value}")
    if any(item in {"generated_at", "timestamp", "mtime"} for item in _strings(payload)):
        errors.append("NONDETERMINISTIC_FIELD_FORBIDDEN")
    return sorted(set(errors))


def encode_audit(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _authorized_evidence(path: Path, project_root: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise RegimeFeasibilityError("EVIDENCE_PATH_NOT_CANONICAL")
    return _safe_path(project_root, path)


def write_audit(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    target = _authorized_evidence(path, PROJECT_ROOT)
    payload = build_audit(authority_root=authority_root)
    errors = validate_audit(payload)
    if errors:
        raise RegimeFeasibilityError("AUDIT_VALIDATION_FAILED:" + ",".join(errors))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_audit(payload))
    return payload


def verify_audit(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    try:
        target = _authorized_evidence(path, PROJECT_ROOT)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RegimeFeasibilityError("EVIDENCE_NOT_OBJECT")
        errors = validate_audit(payload)
        if raw != encode_audit(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_audit(authority_root=authority_root):
            errors.append("AUDIT_RECOMPUTE_MISMATCH")
    except (RegimeFeasibilityError, OSError, json.JSONDecodeError) as error:
        return {"status": "FAIL", "errors": [str(error)]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="audit exact-regime horizon feasibility")
    parser.add_argument("--authority-root", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_audit(args.verify, authority_root=args.authority_root) if args.verify else write_audit(args.output, authority_root=args.authority_root)
    except RegimeFeasibilityError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result if args.verify else {"status": result["status"], "audit_id": result["audit_id"]}, ensure_ascii=False, sort_keys=True))
    return 0 if not args.verify or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
