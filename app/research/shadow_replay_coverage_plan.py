"""規劃 horizon-safe ranking 補齊；只產生計畫，不執行 materializer。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import pandas as pd

from app.research import shadow_replay_availability as availability
from app.research.contracts import canonical_json_bytes, content_hash
from app.research.shadow_plan_proposal import snapshot_protected_surfaces
from scripts import run_backtest_strategy_matrix as strategy_matrix


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "horizon-safe-evidence-coverage-plan.v1"
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/coverage_plan.json"
)
AUDIT_RELATIVE = availability.EVIDENCE_RELATIVE
HORIZONS = (10, 20)
PENDING = "PENDING_MATERIALIZATION_AND_REPLAY"
ALLOWED_STATUSES = {
    "READY_FOR_MATERIALIZATION",
    "NO-GO_PLAN_UNAVAILABLE",
    "BLOCKED_AUTHORITY_CONFLICT",
}
BASELINE_ROOT = Path("artifacts/backtest/historical_rankings_current_model")
CANDIDATE_ROOT = Path("artifacts/backtest/shadow_rankings_regime_guard_recent")
BASELINE_SOURCE = Path("scripts/build_historical_ranking_replay_set.py")
CANDIDATE_SOURCE = Path("scripts/research_regime_shadow_ranking.py")
HELPER_SOURCE = Path("scripts/run_backtest_strategy_matrix.py")


class CoveragePlanError(RuntimeError):
    """表示 evidence authority 或 materialization 邊界不合法。"""


def _sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise CoveragePlanError(f"SOURCE_MISSING_OR_SYMLINK:{path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _repo_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise CoveragePlanError("PATH_ESCAPE") from error


def _safe_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise CoveragePlanError("PATH_ESCAPE")
    root = root.resolve()
    path = root / relative
    cursor = path
    while cursor != root and cursor != cursor.parent:
        if cursor.is_symlink():
            raise CoveragePlanError(f"SOURCE_SYMLINK:{relative.as_posix()}")
        cursor = cursor.parent
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as error:
        raise CoveragePlanError("PATH_ESCAPE") from error
    return path


def ensure_new_output(path: Path, *, root: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root.resolve())
    except ValueError as error:
        raise CoveragePlanError("OUTPUT_PATH_ESCAPE") from error
    if path.is_symlink():
        raise CoveragePlanError("OUTPUT_SYMLINK")
    if path.exists():
        raise CoveragePlanError(f"OUTPUT_COLLISION:{path.name}")


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise CoveragePlanError(f"GIT_AUTHORITY_FAILED:{args[0]}")
    return result.stdout.strip()


def discover_authority_root(project_root: Path = PROJECT_ROOT) -> Path:
    blocks = _git(project_root, "worktree", "list", "--porcelain").split("\n\n")
    candidates: list[Path] = []
    for block in blocks:
        fields = dict(
            line.split(" ", 1) for line in block.splitlines() if " " in line
        )
        if fields.get("branch") == "refs/heads/main":
            candidates.append(Path(fields["worktree"]).resolve())
    if len(candidates) != 1:
        raise CoveragePlanError("MAIN_AUTHORITY_ROOT_NOT_UNIQUE")
    availability._bind_authority_root(project_root.resolve(), candidates[0])
    return candidates[0]


def authorize_explicit_authority_root(
    project_root: Path,
    authority_root: Path,
) -> Path:
    raw = authority_root.as_posix()
    if not authority_root.is_absolute() or ".." in PurePosixPath(raw).parts:
        raise CoveragePlanError("AUTHORITY_ROOT_PATH_ESCAPE")

    lexical = authority_root.absolute()
    cursor = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise CoveragePlanError("AUTHORITY_ROOT_SYMLINK_ALIAS")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as error:
        raise CoveragePlanError("AUTHORITY_ROOT_SYMLINK_OR_MISSING") from error
    if resolved != lexical or not lexical.is_dir():
        raise CoveragePlanError("AUTHORITY_ROOT_SYMLINK_OR_MISSING")

    try:
        availability._bind_authority_root(project_root, lexical)
    except availability.AvailabilityAuditError as error:
        raise CoveragePlanError(f"AUTHORITY_ROOT_REJECTED:{error}") from error
    if lexical != discover_authority_root(project_root):
        raise CoveragePlanError("AUTHORITY_ROOT_NOT_MAIN")
    return lexical


def _committed_source(relative: Path, *, project_root: Path) -> dict[str, str]:
    path = _safe_path(project_root, relative)
    working_bytes = path.read_bytes()
    result = subprocess.run(
        ["git", "-C", str(project_root), "show", f"HEAD:{relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or result.stdout != working_bytes:
        raise CoveragePlanError(f"COMMITTED_SOURCE_DRIFT:{relative.as_posix()}")
    return {
        "path": relative.as_posix(),
        "sha256": "sha256:" + hashlib.sha256(working_bytes).hexdigest(),
    }


def _audit_record(
    *, project_root: Path, authority_root: Path
) -> tuple[dict[str, str], dict[str, Any]]:
    audit_path = _safe_path(project_root, AUDIT_RELATIVE)
    try:
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CoveragePlanError("CARD_E_AUDIT_UNREADABLE") from error
    if not isinstance(payload, dict):
        raise CoveragePlanError("CARD_E_AUDIT_NOT_OBJECT")
    expected_id = content_hash(payload, omit={"audit_id"})
    if payload.get("audit_id") != expected_id:
        raise CoveragePlanError("CARD_E_AUDIT_ID_MISMATCH")
    rebuilt = availability.build_audit(
        project_root=project_root, authority_root=authority_root
    )
    if payload != rebuilt:
        raise CoveragePlanError("CARD_E_AUDIT_DRIFT")
    if payload.get("verdict") != "NO-GO_EVIDENCE_UNAVAILABLE":
        raise CoveragePlanError("CARD_E_AUDIT_VERDICT_DRIFT")
    return {
        "path": AUDIT_RELATIVE.as_posix(),
        "sha256": _sha256_file(audit_path),
        "audit_id": str(payload["audit_id"]),
    }, payload


def select_shared_dates(
    allowed_dates: set[str],
    episode_by_date: dict[str, str],
    trade_dates: list[Any],
) -> dict[str, Any]:
    safe_by_horizon: dict[str, list[str]] = {}
    for horizon in HORIZONS:
        try:
            safe = strategy_matrix.exact_horizon_safe_ranking_dates(
                allowed_dates,
                episode_by_date,
                trade_dates,
                horizon=horizon,
                entry_delay_trade_days=1,
            )
        except ValueError as error:
            if "NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE" not in str(error):
                raise CoveragePlanError(f"CANONICAL_HELPER_FAILED:{error}") from error
            safe = set()
        safe_by_horizon[str(horizon)] = sorted(safe or set())
    shared = sorted(
        set(safe_by_horizon[str(HORIZONS[0])])
        & set(safe_by_horizon[str(HORIZONS[1])])
    )
    return {
        "horizon_safe_dates": safe_by_horizon,
        "shared_dates": shared,
        "selected_dates": shared[:1],
        "selection_rule": "MIN_CARDINALITY_THEN_DATE_ASC",
    }


def _with_plan_id(payload: dict[str, Any]) -> dict[str, Any]:
    payload["plan_id"] = content_hash(payload, omit={"plan_id"})
    return payload


def no_go_plan(
    *,
    audit_record: Mapping[str, str],
    source_hashes: Mapping[str, str],
    selection: Mapping[str, Any],
    parity: Mapping[str, Any],
) -> dict[str, Any]:
    return _with_plan_id(
        {
            "schema_version": SCHEMA_VERSION,
            "plan_id": "",
            "status": "NO-GO_PLAN_UNAVAILABLE",
            "reason_codes": ["NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE"],
            "scope": "NARROW_LEADER|BIG_BULL",
            "horizons": list(HORIZONS),
            "audit": dict(audit_record),
            "canonical_helper": (
                "scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates"
            ),
            "source_hashes": dict(source_hashes),
            "source_decision": {
                "codegraph_status": "CONTEXT_DEGRADED",
                "reason": "NO_TASK_RELEVANT_SYMBOLS_RETURNED",
                "fallback_scope": [
                    "app/research/shadow_replay_availability.py",
                    "scripts/build_historical_ranking_replay_set.py",
                    "scripts/research_regime_shadow_ranking.py",
                    "scripts/run_backtest_strategy_matrix.py",
                ],
            },
            "selection": dict(selection),
            "materialization": None,
            "minimum_gap": {
                "reason_code": "NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE",
                "required_addition": "an exact-regime episode spanning entry plus 20 holding trade dates",
            },
            "lineage_authority_status": PENDING,
            "non_sealed_authority_status": PENDING,
            "unproven_gates": [
                "ranking_materialization",
                "formal_replay",
                "lineage_authority",
                "non_sealed_authority",
            ],
            "parity": dict(parity),
        }
    )


def _file_record(root: Path, relative: Path) -> dict[str, str]:
    path = _safe_path(root, relative)
    if not path.is_file():
        raise CoveragePlanError(f"SOURCE_MISSING:{relative.as_posix()}")
    return {"path": relative.as_posix(), "sha256": _sha256_file(path)}


def _validate_selected_date_coverage(
    authority_root: Path, selected_date: str
) -> dict[str, dict[str, str]]:
    records = {
        "features": _file_record(authority_root, Path("data/clean/features.parquet")),
        "universe": _file_record(authority_root, Path("data/clean/universe.parquet")),
        "model": _file_record(authority_root, Path("models/latest_lgbm.pkl")),
        "signals_config": _file_record(authority_root, Path("config/signals.yaml")),
        "regime_history": _file_record(authority_root, availability.REGIME_RELATIVE),
        "industry_map": _file_record(authority_root, Path("data/reference/stock_industry_map.csv")),
    }
    features = pd.read_parquet(
        authority_root / "data/clean/features.parquet", columns=["date"]
    )
    feature_dates = set(
        pd.to_datetime(features["date"], errors="raise").dt.strftime("%Y-%m-%d")
    )
    if selected_date not in feature_dates:
        raise CoveragePlanError("FEATURE_DATE_COVERAGE_MISSING")
    universe_path = authority_root / "data/clean/universe.parquet"
    universe = pd.read_parquet(universe_path)
    if "date" in universe.columns:
        universe_dates = set(
            pd.to_datetime(universe["date"], errors="raise").dt.strftime("%Y-%m-%d")
        )
        if selected_date not in universe_dates:
            raise CoveragePlanError("UNIVERSE_DATE_COVERAGE_MISSING")
    regime = json.loads(
        (authority_root / availability.REGIME_RELATIVE).read_text(encoding="utf-8")
    )
    regime_dates = {str(row.get("trade_date")) for row in regime.get("rows", [])}
    if selected_date not in regime_dates:
        raise CoveragePlanError("REGIME_DATE_COVERAGE_MISSING")
    return records


def _materialization(
    *, project_root: Path, authority_root: Path, selected_date: str
) -> dict[str, Any]:
    inputs = _validate_selected_date_coverage(authority_root, selected_date)
    baseline_target = _safe_path(
        authority_root, BASELINE_ROOT / f"ranking_{selected_date}.csv"
    )
    candidate_target = _safe_path(
        authority_root, CANDIDATE_ROOT / f"ranking_{selected_date}.csv"
    )
    ensure_new_output(baseline_target, root=authority_root)
    ensure_new_output(candidate_target, root=authority_root)
    existing_dates = sorted(
        item.name.removeprefix("ranking_").removesuffix(".csv")
        for item in (authority_root / BASELINE_ROOT).glob("ranking_*.csv")
    )
    if existing_dates and selected_date <= existing_dates[-1]:
        raise CoveragePlanError("CANDIDATE_MATERIALIZER_DATE_BOUNDARY_UNAVAILABLE")
    baseline_argv = [
        "uv", "run", "python", BASELINE_SOURCE.as_posix(),
        "--start-date", selected_date, "--end-date", selected_date,
        "--data-dir", "data/clean", "--model-dir", "models",
        "--config", "config/signals.yaml", "--output-dir", BASELINE_ROOT.as_posix(),
        "--max-dates", "1", "--top-n", "10",
    ]
    candidate_argv = [
        "uv", "run", "python", CANDIDATE_SOURCE.as_posix(),
        "--dates-from-dir", BASELINE_ROOT.as_posix(),
        "--output-dir", CANDIDATE_ROOT.as_posix(),
        "--market-regime-history", availability.REGIME_RELATIVE.as_posix(),
        "--industry-map", "data/reference/stock_industry_map.csv",
        "--risk-profile", "shadow_regime_guard", "--top-n", "10", "--limit", "1",
    ]
    return {
        "execution_allowed_in_this_card": False,
        "baseline": {
            "materializer": _committed_source(BASELINE_SOURCE, project_root=project_root),
            "inputs": {key: inputs[key] for key in ("features", "universe", "model", "signals_config")},
            "expected_ranking_paths": [_repo_path(baseline_target, authority_root)],
            "argv": baseline_argv,
        },
        "candidate": {
            "materializer": _committed_source(CANDIDATE_SOURCE, project_root=project_root),
            "inputs": {
                "planned_baseline_ranking": {
                    "path": _repo_path(baseline_target, authority_root),
                    "sha256": "PENDING_MATERIALIZATION",
                },
                "regime_history": inputs["regime_history"],
                "industry_map": inputs["industry_map"],
            },
            "expected_ranking_paths": [_repo_path(candidate_target, authority_root)],
            "argv": candidate_argv,
        },
    }


def _snapshot_hashes(authority_root: Path) -> tuple[str, str]:
    return (
        content_hash(availability._source_snapshot(authority_root)),
        content_hash(snapshot_protected_surfaces(project_root=authority_root)),
    )


def _base_payload(
    *, audit_record: Mapping[str, str], source_hashes: Mapping[str, str], selection: Mapping[str, Any], parity: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": "",
        "status": "READY_FOR_MATERIALIZATION",
        "reason_codes": [],
        "scope": "NARROW_LEADER|BIG_BULL",
        "horizons": list(HORIZONS),
        "audit": dict(audit_record),
        "canonical_helper": "scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates",
        "source_hashes": dict(source_hashes),
        "source_decision": {
            "codegraph_status": "CONTEXT_DEGRADED",
            "reason": "NO_TASK_RELEVANT_SYMBOLS_RETURNED",
            "fallback_scope": [
                "app/research/shadow_replay_availability.py",
                "scripts/build_historical_ranking_replay_set.py",
                "scripts/research_regime_shadow_ranking.py",
                "scripts/run_backtest_strategy_matrix.py",
            ],
        },
        "selection": dict(selection),
        "materialization": None,
        "minimum_gap": None,
        "lineage_authority_status": PENDING,
        "non_sealed_authority_status": PENDING,
        "unproven_gates": ["ranking_materialization", "formal_replay", "lineage_authority", "non_sealed_authority"],
        "parity": dict(parity),
    }


def build_plan(
    *, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None
) -> dict[str, Any]:
    if authority_root is not None:
        authority_root = authorize_explicit_authority_root(
            project_root,
            authority_root,
        )
    project_root = project_root.resolve()
    authority_root = authority_root or discover_authority_root(project_root)
    before_sources, before_protected = _snapshot_hashes(authority_root)
    audit_record, _ = _audit_record(
        project_root=project_root, authority_root=authority_root
    )
    _, trade_dates = availability._feature_inventory(authority_root)
    _, card_d = availability._load_card_d(authority_root)
    regime = availability._file_inventory(authority_root, availability.REGIME_RELATIVE)
    _, allowed_dates, episode_by_date = availability._exact_regime_authority(
        authority_root, regime, card_d
    )
    selection = select_shared_dates(allowed_dates, episode_by_date, trade_dates)
    source_hashes = {
        "canonical_helper": _committed_source(HELPER_SOURCE, project_root=project_root)["sha256"],
        "baseline_materializer": _committed_source(BASELINE_SOURCE, project_root=project_root)["sha256"],
        "candidate_materializer": _committed_source(CANDIDATE_SOURCE, project_root=project_root)["sha256"],
    }
    after_sources, after_protected = _snapshot_hashes(authority_root)
    parity = {
        "fixed_sources_before_hash": before_sources,
        "fixed_sources_after_hash": after_sources,
        "fixed_sources_unchanged": before_sources == after_sources,
        "protected_surfaces_before_hash": before_protected,
        "protected_surfaces_after_hash": after_protected,
        "protected_surfaces_unchanged": before_protected == after_protected,
    }
    if not all(parity.values()):
        raise CoveragePlanError("AUTHORITY_DRIFT_DURING_PLAN")
    if not selection["selected_dates"]:
        return no_go_plan(
            audit_record=audit_record,
            source_hashes=source_hashes,
            selection=selection,
            parity=parity,
        )
    payload = _base_payload(
        audit_record=audit_record,
        source_hashes=source_hashes,
        selection=selection,
        parity=parity,
    )
    try:
        payload["materialization"] = _materialization(
            project_root=project_root,
            authority_root=authority_root,
            selected_date=selection["selected_dates"][0],
        )
    except (CoveragePlanError, OSError, ValueError, json.JSONDecodeError) as error:
        payload["status"] = "BLOCKED_AUTHORITY_CONFLICT"
        payload["reason_codes"] = [str(error)]
    return _with_plan_id(payload)


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


def validate_plan(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("status") not in ALLOWED_STATUSES:
        errors.append("STATUS_INVALID")
    if payload.get("plan_id") != content_hash(payload, omit={"plan_id"}):
        errors.append("PLAN_ID_MISMATCH")
    if payload.get("lineage_authority_status") != PENDING:
        errors.append("LINEAGE_STATUS_MUST_REMAIN_PENDING")
    if payload.get("non_sealed_authority_status") != PENDING:
        errors.append("NON_SEALED_STATUS_MUST_REMAIN_PENDING")
    for value in _strings(payload):
        if value.startswith("/"):
            errors.append(f"ABSOLUTE_PATH_FORBIDDEN:{value}")
    forbidden_keys = {"generated_at", "timestamp", "mtime"}
    if any(value in forbidden_keys for value in _strings(payload)):
        errors.append("NONDETERMINISTIC_FIELD_FORBIDDEN")
    if payload.get("status") == "READY_FOR_MATERIALIZATION":
        if not (payload.get("selection") or {}).get("selected_dates"):
            errors.append("READY_WITHOUT_SELECTED_DATE")
        materialization = payload.get("materialization") or {}
        if not (materialization.get("baseline") or {}).get("argv"):
            errors.append("BASELINE_ARGV_MISSING")
        if not (materialization.get("candidate") or {}).get("argv"):
            errors.append("CANDIDATE_ARGV_MISSING")
    if payload.get("status") == "NO-GO_PLAN_UNAVAILABLE" and payload.get("materialization") is not None:
        errors.append("NO_GO_MUST_NOT_DECLARE_MATERIALIZATION")
    return sorted(set(errors))


def encode_plan(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _authorized_evidence(path: Path, project_root: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise CoveragePlanError("EVIDENCE_PATH_NOT_CANONICAL")
    target = _safe_path(project_root, path)
    if target.is_symlink():
        raise CoveragePlanError("EVIDENCE_PATH_SYMLINK")
    return target


def write_plan(
    path: Path, *, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None
) -> dict[str, Any]:
    target = _authorized_evidence(path, project_root)
    payload = build_plan(project_root=project_root, authority_root=authority_root)
    errors = validate_plan(payload)
    if errors:
        raise CoveragePlanError("PLAN_VALIDATION_FAILED:" + ",".join(errors))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_plan(payload))
    return payload


def verify_plan(
    path: Path, *, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None
) -> dict[str, Any]:
    try:
        target = _authorized_evidence(path, project_root)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise CoveragePlanError("EVIDENCE_NOT_OBJECT")
        errors = validate_plan(payload)
        if raw != encode_plan(payload):
            errors.append("NON_CANONICAL_BYTES")
        rebuilt = build_plan(project_root=project_root, authority_root=authority_root)
        if payload != rebuilt:
            errors.append("PLAN_RECOMPUTE_MISMATCH")
    except (CoveragePlanError, OSError, json.JSONDecodeError) as error:
        return {"status": "FAIL", "errors": [str(error)]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="plan horizon-safe ranking evidence coverage")
    parser.add_argument("--authority-root", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = (
            verify_plan(args.verify, authority_root=args.authority_root)
            if args.verify is not None
            else write_plan(args.output, authority_root=args.authority_root)
        )
    except CoveragePlanError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    if args.verify is not None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    print(json.dumps({"status": result["status"], "plan_id": result["plan_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
