"""盤點 horizon-safe replay inputs；只讀既有 authority，不執行 replay。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import pandas as pd

from app.research.contracts import canonical_json_bytes, content_hash
from app.research.shadow_plan_proposal import snapshot_protected_surfaces
from scripts import run_backtest_replay
from scripts import run_backtest_strategy_matrix as strategy_matrix


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "shadow-replay-availability.v1"
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/"
    "availability_audit.json"
)
CARD_D_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/final_result.json"
)
RANKING_ROOTS = {
    "baseline": Path("artifacts/backtest/historical_rankings_current_model"),
    "candidate": Path("artifacts/backtest/shadow_rankings_regime_guard_recent"),
}
FEATURES_RELATIVE = Path("data/clean/features.parquet")
REGIME_RELATIVE = Path("artifacts/market_regime_history.json")
HORIZONS = (10, 20)
MAX_INVENTORY_FILES = 1000


class AvailabilityAuditError(RuntimeError):
    """表示 authority 邊界或內容衝突，必須 fail closed。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_source(project_root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise AvailabilityAuditError("SOURCE_PATH_OUTSIDE_PROJECT")
    root = project_root.resolve()
    path = project_root / relative
    cursor = path
    while cursor != project_root and cursor != cursor.parent:
        if cursor.is_symlink():
            raise AvailabilityAuditError(f"SOURCE_SYMLINK:{relative.as_posix()}")
        cursor = cursor.parent
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise AvailabilityAuditError(
            f"SOURCE_PATH_OUTSIDE_PROJECT:{relative.as_posix()}"
        ) from exc
    return path


def _directory_inventory(project_root: Path, relative: Path) -> dict[str, Any]:
    path = _safe_source(project_root, relative)
    if not path.exists():
        return {
            "path": relative.as_posix(),
            "status": "MISSING",
            "sha256": "ABSENT",
            "files": [],
            "conflicts": [],
        }
    if not path.is_dir():
        return {
            "path": relative.as_posix(),
            "status": "CONFLICT",
            "sha256": "ABSENT",
            "files": [],
            "conflicts": ["EXPECTED_DIRECTORY"],
        }
    files = sorted(item for item in path.rglob("*") if item.is_file() or item.is_symlink())
    if len(files) > MAX_INVENTORY_FILES:
        return {
            "path": relative.as_posix(),
            "status": "CONFLICT",
            "sha256": "ABSENT",
            "files": [],
            "conflicts": ["INVENTORY_FILE_LIMIT_EXCEEDED"],
        }
    manifest: list[dict[str, str]] = []
    conflicts: list[str] = []
    dates: set[str] = set()
    for item in files:
        item_relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            conflicts.append(f"SYMLINK:{item_relative}")
            continue
        manifest.append({"path": item_relative, "sha256": _sha256_file(item)})
        if item.parent == path and item.name.startswith("ranking_") and item.suffix == ".csv":
            try:
                dates.add(run_backtest_replay.ranking_date(item))
            except ValueError:
                conflicts.append(f"UNPARSEABLE_RANKING_DATE:{item_relative}")
    return {
        "path": relative.as_posix(),
        "status": "CONFLICT" if conflicts else "AVAILABLE",
        "sha256": content_hash({"files": manifest}),
        "files": manifest,
        "ranking_dates": sorted(dates),
        "conflicts": sorted(conflicts),
    }


def _file_inventory(project_root: Path, relative: Path) -> dict[str, Any]:
    path = _safe_source(project_root, relative)
    if not path.exists():
        return {"path": relative.as_posix(), "status": "MISSING", "sha256": "ABSENT"}
    if not path.is_file():
        return {"path": relative.as_posix(), "status": "CONFLICT", "sha256": "ABSENT"}
    return {"path": relative.as_posix(), "status": "AVAILABLE", "sha256": _sha256_file(path)}


def _feature_inventory(project_root: Path) -> tuple[dict[str, Any], list[Any]]:
    inventory = _file_inventory(project_root, FEATURES_RELATIVE)
    if inventory["status"] != "AVAILABLE":
        return {**inventory, "date_coverage": None}, []
    path = project_root / FEATURES_RELATIVE
    try:
        try:
            frame = pd.read_parquet(path, columns=["trade_date"])
        except Exception as error:
            if "trade_date" not in str(error):
                raise
            frame = pd.read_parquet(path, columns=["date"]).rename(columns={"date": "trade_date"})
        parsed = pd.to_datetime(frame["trade_date"], errors="raise").dt.date
        dates = sorted(parsed.dropna().unique())
    except Exception as error:
        return {
            **inventory,
            "status": "CONFLICT",
            "date_coverage": None,
            "conflicts": [f"FEATURE_DATE_READ_FAILED:{type(error).__name__}"],
        }, []
    coverage = {
        "count": len(dates),
        "first": dates[0].isoformat() if dates else None,
        "last": dates[-1].isoformat() if dates else None,
    }
    return {**inventory, "date_coverage": coverage}, dates


def _load_card_d(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    inventory = _file_inventory(project_root, CARD_D_RELATIVE)
    if inventory["status"] != "AVAILABLE":
        return inventory, {}
    try:
        payload = json.loads((project_root / CARD_D_RELATIVE).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        return {
            **inventory,
            "status": "CONFLICT",
            "conflicts": [f"CARD_D_READ_FAILED:{type(error).__name__}"],
        }, {}
    return inventory, payload if isinstance(payload, dict) else {}


def _allowed_episode_ids(card_d: Mapping[str, Any]) -> list[str]:
    steps = ((card_d.get("runner") or {}).get("steps") or []) if isinstance(card_d, Mapping) else []
    for step in steps:
        argv = step.get("command") if isinstance(step, Mapping) else None
        if not isinstance(argv, list) or "--allowed-episode-ids" not in argv:
            continue
        index = argv.index("--allowed-episode-ids")
        if index + 1 < len(argv):
            return sorted(item for item in str(argv[index + 1]).split(",") if item)
    return []


def _proven_lineages(card_d: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, set[int]] = {}
    for row in card_d.get("units") or []:
        if not isinstance(row, Mapping):
            continue
        if (
            row.get("terminal_status") == "SUCCEEDED"
            and row.get("observation_status") == "OBSERVED"
            and row.get("identity_match_status") == "EXACT"
            and row.get("lineage_resolution_status") == "VALID"
            and row.get("sealed_usage_status") == "PROVEN_NON_SEALED"
            and int(row.get("horizon") or 0) in HORIZONS
        ):
            grouped.setdefault(str(row.get("lineage_id") or ""), set()).add(
                int(row["horizon"])
            )
    return [
        {"lineage_id": lineage_id, "horizons": sorted(horizons)}
        for lineage_id, horizons in sorted(grouped.items())
        if lineage_id and horizons == set(HORIZONS)
    ]


def _exact_regime_authority(
    project_root: Path,
    regime_inventory: Mapping[str, Any],
    card_d: Mapping[str, Any],
) -> tuple[dict[str, Any], set[str], dict[str, str]]:
    episode_ids = _allowed_episode_ids(card_d)
    if regime_inventory.get("status") != "AVAILABLE" or not episode_ids:
        return {
            "status": "MISSING",
            "identity": "NARROW_LEADER|BIG_BULL",
            "requested_episode_ids": episode_ids,
            "allowed_dates": [],
            "conflicts": [],
        }, set(), {}
    args = SimpleNamespace(
        require_exact_regime=True,
        market_regime_history=str(project_root / REGIME_RELATIVE),
        base_regime="NARROW_LEADER",
        family_tags="BIG_BULL",
        allowed_episode_ids=",".join(episode_ids),
    )
    try:
        identity, allowed_dates, episode_by_date = strategy_matrix.exact_regime_context(args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return {
            "status": "CONFLICT",
            "identity": "NARROW_LEADER|BIG_BULL",
            "requested_episode_ids": episode_ids,
            "allowed_dates": [],
            "conflicts": [str(error)],
        }, set(), {}
    return {
        "status": "AVAILABLE",
        "identity": f"{identity['base_regime']}|{'+'.join(identity['family_tags'])}",
        "requested_episode_ids": episode_ids,
        "allowed_dates": sorted(allowed_dates or set()),
        "conflicts": [],
    }, allowed_dates or set(), episode_by_date or {}


def _horizon_safe_dates(
    allowed_dates: set[str], episode_by_date: dict[str, str], trade_dates: list[Any], horizon: int
) -> tuple[set[str], list[str]]:
    if not allowed_dates or not episode_by_date or not trade_dates:
        return set(), []
    try:
        safe = strategy_matrix.exact_horizon_safe_ranking_dates(
            allowed_dates,
            episode_by_date,
            trade_dates,
            horizon=horizon,
            entry_delay_trade_days=1,
        )
    except ValueError as error:
        if "NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE" in str(error):
            return set(), ["NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE"]
        raise AvailabilityAuditError(f"CANONICAL_HELPER_FAILED:{error}") from error
    return safe or set(), []


def _availability_matrix(
    ranking_inventories: Mapping[str, Mapping[str, Any]],
    allowed_dates: set[str],
    episode_by_date: dict[str, str],
    trade_dates: list[Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    rows: list[dict[str, Any]] = []
    accepted_by_key: dict[str, list[str]] = {}
    for horizon in HORIZONS:
        safe_dates, helper_reasons = _horizon_safe_dates(
            allowed_dates, episode_by_date, trade_dates, horizon
        )
        for role in sorted(ranking_inventories):
            inventory = ranking_inventories[role]
            date_rows: list[dict[str, Any]] = []
            for ranking_date in inventory.get("ranking_dates") or []:
                reasons: list[str] = []
                if ranking_date not in allowed_dates:
                    reasons.append("NOT_EXACT_REGIME_DATE")
                elif ranking_date not in safe_dates:
                    reasons.append("NO_HORIZON_SAFE_EXACT_REGIME_WINDOW")
                date_rows.append(
                    {
                        "ranking_date": ranking_date,
                        "exact_regime_episode_id": episode_by_date.get(ranking_date),
                        "status": "ACCEPTED" if not reasons else "EXCLUDED",
                        "reason_codes": reasons,
                    }
                )
            accepted = [row["ranking_date"] for row in date_rows if row["status"] == "ACCEPTED"]
            key = f"{role}:h{horizon}"
            accepted_by_key[key] = accepted
            summary_reasons = list(helper_reasons)
            if inventory.get("status") == "MISSING":
                summary_reasons.append("RANKING_ROOT_MISSING")
            elif not inventory.get("ranking_dates"):
                summary_reasons.append("RANKING_DATE_MISSING")
            rows.append(
                {
                    "role": role,
                    "ranking_root": inventory["path"],
                    "horizon": horizon,
                    "dates": date_rows,
                    "accepted_dates": accepted,
                    "reason_codes": sorted(set(summary_reasons)),
                }
            )
    return rows, accepted_by_key


def _minimum_gap(
    rankings: Mapping[str, Mapping[str, Any]],
    features: Mapping[str, Any],
    exact_regime: Mapping[str, Any],
    proven_lineages: Sequence[Mapping[str, Any]],
    matched: Mapping[str, Sequence[str]],
) -> dict[str, Any] | None:
    reasons: list[str] = []
    if any(not inventory.get("ranking_dates") for inventory in rankings.values()):
        reasons.append("MISSING_RANKING_DATE")
    if features.get("status") != "AVAILABLE" or not (features.get("date_coverage") or {}).get("count"):
        reasons.append("MISSING_FORWARD_HORIZON")
    if exact_regime.get("status") != "AVAILABLE" or not exact_regime.get("allowed_dates"):
        reasons.append("MISSING_EXACT_REGIME")
    if len(proven_lineages) < 2:
        reasons.extend(["MISSING_LINEAGE_AUTHORITY", "MISSING_NON_SEALED_AUTHORITY"])
    if any(not matched.get(str(horizon)) for horizon in HORIZONS):
        reasons.append("MISSING_CROSS_ROOT_MATCHED_INTERSECTION")
    if not reasons:
        return None
    return {
        "primary_reason_code": reasons[0],
        "reason_codes": reasons,
        "required_addition": {
            "ranking_roots_with_dates": 2,
            "horizons": list(HORIZONS),
            "exact_regime": "NARROW_LEADER|BIG_BULL",
            "proven_non_sealed_lineages": 2,
        },
    }


def _source_snapshot(project_root: Path) -> dict[str, Any]:
    rankings = {
        role: _directory_inventory(project_root, relative)
        for role, relative in sorted(RANKING_ROOTS.items())
    }
    features, _ = _feature_inventory(project_root)
    regime = _file_inventory(project_root, REGIME_RELATIVE)
    card_d, _ = _load_card_d(project_root)
    return {"ranking_roots": rankings, "features": features, "regime": regime, "card_d": card_d}


def build_audit(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    project_root = project_root.resolve()
    before_sources = _source_snapshot(project_root)
    before_protected = snapshot_protected_surfaces(project_root=project_root)
    rankings = before_sources["ranking_roots"]
    features, trade_dates = _feature_inventory(project_root)
    regime = _file_inventory(project_root, REGIME_RELATIVE)
    card_d_inventory, card_d = _load_card_d(project_root)
    exact_regime, allowed_dates, episode_by_date = _exact_regime_authority(
        project_root, regime, card_d
    )
    matrix, accepted = _availability_matrix(
        rankings, allowed_dates, episode_by_date, trade_dates
    )
    matched = {
        str(horizon): sorted(
            set(accepted[f"baseline:h{horizon}"])
            & set(accepted[f"candidate:h{horizon}"])
        )
        for horizon in HORIZONS
    }
    lineages = _proven_lineages(card_d)
    gap = _minimum_gap(rankings, features, exact_regime, lineages, matched)
    after_sources = _source_snapshot(project_root)
    after_protected = snapshot_protected_surfaces(project_root=project_root)
    conflicts = sorted(
        {
            reason
            for inventory in [*rankings.values(), features, regime, card_d_inventory, exact_regime]
            for reason in inventory.get("conflicts", [])
        }
    )
    if before_sources != after_sources:
        conflicts.append("FIXED_SOURCE_DRIFT_DURING_AUDIT")
    if before_protected != after_protected:
        conflicts.append("PROTECTED_SURFACE_DRIFT_DURING_AUDIT")
    verdict = (
        "BLOCKED_AUTHORITY_CONFLICT"
        if conflicts
        else "GO_REPLAY_INPUTS_AVAILABLE"
        if gap is None
        else "NO-GO_EVIDENCE_UNAVAILABLE"
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": "",
        "scope": "NARROW_LEADER|BIG_BULL",
        "horizons": list(HORIZONS),
        "verdict": verdict,
        "reason_codes": conflicts if conflicts else ([] if gap is None else gap["reason_codes"]),
        "sources": {
            "ranking_roots": rankings,
            "features": features,
            "regime": regime,
            "card_d": card_d_inventory,
        },
        "exact_regime_authority": exact_regime,
        "availability_matrix": matrix,
        "matched_intersection_by_horizon": matched,
        "proven_non_sealed_lineages": lineages,
        "minimum_gap": gap,
        "parity": {
            "fixed_sources_unchanged": before_sources == after_sources,
            "protected_surfaces_unchanged": before_protected == after_protected,
            "fixed_sources_before": before_sources,
            "fixed_sources_after": after_sources,
            "protected_surfaces_before": before_protected,
            "protected_surfaces_after": after_protected,
        },
        "canonical_helper": (
            "scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates"
        ),
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})
    return payload


def _authorized_evidence_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute() or ".." in PurePosixPath(path.as_posix()).parts:
        raise AvailabilityAuditError("EVIDENCE_PATH_OUTSIDE_PROJECT")
    if path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise AvailabilityAuditError("EVIDENCE_PATH_NOT_CANONICAL")
    target = project_root / path
    if target.is_symlink() or target.resolve(strict=False) != target.absolute():
        raise AvailabilityAuditError("EVIDENCE_PATH_SYMLINK_ESCAPE")
    return target


def write_audit(path: Path, *, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    target = _authorized_evidence_path(path, project_root)
    payload = build_audit(project_root=project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json_bytes(payload) + b"\n")
    return payload


def verify_audit(path: Path, *, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    try:
        target = _authorized_evidence_path(path, project_root)
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AvailabilityAuditError("EVIDENCE_NOT_OBJECT")
        expected_id = content_hash(payload, omit={"audit_id"})
        rebuilt = build_audit(project_root=project_root)
        errors = []
        if payload.get("schema_version") != SCHEMA_VERSION:
            errors.append("SCHEMA_VERSION_MISMATCH")
        if payload.get("audit_id") != expected_id:
            errors.append("AUDIT_ID_MISMATCH")
        if payload != rebuilt:
            errors.append("AUDIT_RECOMPUTE_MISMATCH")
    except (AvailabilityAuditError, FileNotFoundError, json.JSONDecodeError) as error:
        return {"status": "FAIL", "errors": [str(error)]}
    return {"status": "PASS" if not errors else "FAIL", "errors": errors}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="audit horizon-safe replay input availability")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = (
            verify_audit(args.verify)
            if args.verify is not None
            else write_audit(args.output)
        )
    except AvailabilityAuditError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.verify is not None:
        return 0 if result["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
