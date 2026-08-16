"""建立 entry-regime cohort 的 outcome-free h20 可行性證據。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research import entry_regime_cohort_architecture_decision as architecture
from app.research import shadow_replay_authority_reconciliation as reconciliation
from app.research import shadow_replay_availability as availability
from app.research import shadow_replay_coverage_plan as coverage
from app.research.contracts import canonical_json_bytes, content_hash
from scripts import run_autonomous_research as regime_research
from scripts import run_backtest_replay as replay


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "entry-regime-cohort-h20-feasibility.v1"
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1/"
    "feasibility.json"
)
DECISION_RELATIVE = architecture.EVIDENCE_RELATIVE
AVAILABILITY_RELATIVE = availability.EVIDENCE_RELATIVE
RECONCILIATION_RELATIVE = reconciliation.EVIDENCE_RELATIVE
HORIZON = 20
EMBARGO = 20
ROLES = ("development", "validation", "sealed")
ALLOWED_STATUSES = {
    "FEASIBLE_FOR_PREREGISTRATION",
    "NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY",
    "BLOCKED_EVIDENCE_OR_CONTRACT_CONFLICT",
}
FORBIDDEN_METRIC_TOKENS = ("pnl", "sharpe", "win rate", "alpha", "promotion score")


class EntryCohortFeasibilityError(RuntimeError):
    """表示 entry cohort authority 或證據契約不合法。"""


def _safe_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise EntryCohortFeasibilityError("PATH_ESCAPE")
    lexical_root = root.absolute()
    if lexical_root.is_symlink() or lexical_root.resolve(strict=True) != lexical_root:
        raise EntryCohortFeasibilityError("ROOT_SYMLINK")
    cursor = lexical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise EntryCohortFeasibilityError("PATH_SYMLINK")
    try:
        cursor.resolve(strict=False).relative_to(lexical_root)
    except ValueError as error:
        raise EntryCohortFeasibilityError("PATH_ESCAPE") from error
    return cursor


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _committed_json(root: Path, relative: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = _safe_path(root, relative)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise EntryCohortFeasibilityError(f"SOURCE_UNREADABLE:{relative.as_posix()}") from error
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise EntryCohortFeasibilityError(f"SOURCE_NOT_COMMITTED:{relative.as_posix()}")
    if result.stdout != raw:
        raise EntryCohortFeasibilityError(f"SOURCE_WORKTREE_DRIFT:{relative.as_posix()}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise EntryCohortFeasibilityError(f"SOURCE_INVALID_JSON:{relative.as_posix()}") from error
    if not isinstance(payload, dict):
        raise EntryCohortFeasibilityError(f"SOURCE_NOT_OBJECT:{relative.as_posix()}")
    return payload, {
        "path": relative.as_posix(),
        "sha256": _sha256(raw),
        "commit_status": "MATCHED",
    }


def _manifest(availability_payload: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    sources = availability_payload.get("sources")
    roots = sources.get("ranking_roots") if isinstance(sources, Mapping) else None
    if not isinstance(roots, Mapping) or not roots:
        raise EntryCohortFeasibilityError("RANKING_MANIFEST_MISSING")
    manifests: dict[str, dict[str, Any]] = {}
    for scenario, raw in sorted(roots.items()):
        if not isinstance(raw, Mapping):
            raise EntryCohortFeasibilityError("RANKING_MANIFEST_INVALID")
        dates = raw.get("ranking_dates")
        files = raw.get("files")
        if (
            raw.get("status") != "AVAILABLE"
            or not isinstance(raw.get("sha256"), str)
            or not isinstance(dates, list)
            or not isinstance(files, list)
            or dates != sorted(set(str(item) for item in dates))
            or not dates
        ):
            raise EntryCohortFeasibilityError("RANKING_MANIFEST_INVALID")
        by_date: dict[str, str] = {}
        for item in files:
            if not isinstance(item, Mapping):
                continue
            path = str(item.get("path") or "")
            digest = str(item.get("sha256") or "")
            if not path.startswith("ranking_") or not path.endswith(".csv"):
                continue
            value = path.removeprefix("ranking_").removesuffix(".csv")
            if value in by_date or not digest.startswith("sha256:"):
                raise EntryCohortFeasibilityError("RANKING_MANIFEST_ALIAS_CONFLICT")
            by_date[value] = digest
        if set(by_date) != set(dates):
            raise EntryCohortFeasibilityError("RANKING_MANIFEST_DATE_FILE_CONFLICT")
        manifests[str(scenario)] = {
            "path": str(raw.get("path") or ""),
            "sha256": str(raw["sha256"]),
            "ranking_dates": list(dates),
            "date_fingerprints": by_date,
        }
    shared = sorted(set.intersection(*(set(row["ranking_dates"]) for row in manifests.values())))
    if not shared:
        raise EntryCohortFeasibilityError("RANKING_MANIFEST_NO_SHARED_DATES")
    return manifests, shared


def _entry_rows(
    *, ranking_dates: Sequence[str], regime_rows: Sequence[Mapping[str, Any]], trade_dates: Sequence[date], scenarios: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    row_by_date: dict[str, Mapping[str, Any]] = {}
    duplicate_dates: set[str] = set()
    for row in regime_rows:
        trade_date = str(row.get("trade_date") or "")
        if trade_date in row_by_date:
            duplicate_dates.add(trade_date)
        else:
            row_by_date[trade_date] = row
    observations: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    for ranking_date in sorted(ranking_dates):
        row = row_by_date.get(ranking_date)
        if ranking_date in duplicate_dates:
            exclusions.append({"ranking_date": ranking_date, "reason_code": "D_REGIME_DUPLICATE"})
            continue
        if row is None:
            exclusions.append({"ranking_date": ranking_date, "reason_code": "D_REGIME_MISSING"})
            continue
        if str(row.get("as_of_date") or "") != ranking_date:
            exclusions.append({"ranking_date": ranking_date, "reason_code": "D_AS_OF_CONFLICT"})
            continue
        if bool(row.get("is_transition")):
            exclusions.append({"ranking_date": ranking_date, "reason_code": "D_TRANSITION"})
            continue
        try:
            identity = regime_research.regime_identity_id(dict(row))
        except ValueError:
            exclusions.append({"ranking_date": ranking_date, "reason_code": "D_TAXONOMY_INVALID"})
            continue
        if identity.startswith("UNKNOWN|"):
            exclusions.append({"ranking_date": ranking_date, "reason_code": "D_UNKNOWN"})
            continue
        entry = replay.next_market_trade_date(list(trade_dates), ranking_date, delay_trade_days=1)
        if entry is None:
            exclusions.append({"ranking_date": ranking_date, "reason_code": "ENTRY_D1_MISSING"})
            continue
        holding = replay.market_holding_dates(list(trade_dates), entry, HORIZON)
        if holding is None or len(holding) != HORIZON:
            exclusions.append({"ranking_date": ranking_date, "reason_code": "H20_CALENDAR_INCOMPLETE"})
            continue
        for scenario, manifest in sorted(scenarios.items()):
            fingerprint = manifest["date_fingerprints"].get(ranking_date)
            if not isinstance(fingerprint, str):
                exclusions.append({"ranking_date": ranking_date, "reason_code": "SCENARIO_FINGERPRINT_MISSING"})
                continue
            observations.append(
                {
                    "ranking_date": ranking_date,
                    "scenario": scenario,
                    "entry_cohort_id": identity,
                    "entry_date": entry.isoformat(),
                    "exit_date": holding[-1].isoformat(),
                    "portfolio_fingerprint": content_hash(
                        {"scenario": scenario, "ranking_date": ranking_date, "ranking_file": fingerprint}
                    ),
                }
            )
    return observations, exclusions


def overlap_components(observations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """以 closed interval 的可傳遞相交關係建立 component。"""

    ordered = sorted(
        observations,
        key=lambda item: (str(item["entry_date"]), str(item["exit_date"]), str(item["scenario"])),
    )
    components: list[dict[str, Any]] = []
    current: list[Mapping[str, Any]] = []
    latest_exit = ""
    for item in ordered:
        if current and str(item["entry_date"]) > latest_exit:
            components.append(_component(current))
            current = []
            latest_exit = ""
        current.append(item)
        latest_exit = max(latest_exit, str(item["exit_date"]))
    if current:
        components.append(_component(current))
    return components


def _component(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    identities = {
        (str(item["ranking_date"]), str(item["scenario"])): str(item["portfolio_fingerprint"])
        for item in items
    }
    if len(identities) != len(items):
        raise EntryCohortFeasibilityError("PORTFOLIO_ALIAS_CONFLICT")
    return {
        "component_id": content_hash(
            {"observations": [dict(item) for item in sorted(items, key=lambda value: (str(value["ranking_date"]), str(value["scenario"])))]}
        ),
        "start_date": min(str(item["entry_date"]) for item in items),
        "end_date": max(str(item["exit_date"]) for item in items),
        "observation_count": len(items),
        "cohorts": sorted({str(item["entry_cohort_id"]) for item in items}),
    }


def build_global_split(observations: Sequence[Mapping[str, Any]], trade_dates: Sequence[date]) -> dict[str, Any]:
    """先全域切點，再以 h20 closed interval 與 embargo purge。"""

    by_ranking: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in observations:
        by_ranking[str(item["ranking_date"])].append(item)
    dates = sorted(by_ranking)
    third = len(dates) // 3
    if third == 0:
        return {
            "schema_version": "entry-cohort-calendar-split.v1",
            "status": "INSUFFICIENT_GLOBAL_DATES",
            "roles": {role: [] for role in ROLES},
            "boundaries": [],
            "purged_observation_count": 0,
        }
    validation_cut = dates[third]
    sealed_cut = dates[third * 2]
    index = {value.isoformat(): position for position, value in enumerate(trade_dates)}
    if validation_cut not in index or sealed_cut not in index:
        raise EntryCohortFeasibilityError("SPLIT_CUTOFF_NOT_IN_CALENDAR")
    role_rows = {role: [] for role in ROLES}
    purged = 0
    for item in observations:
        ranking_date = str(item["ranking_date"])
        entry_index = index.get(str(item["entry_date"]))
        exit_index = index.get(str(item["exit_date"]))
        if entry_index is None or exit_index is None:
            raise EntryCohortFeasibilityError("OBSERVATION_CALENDAR_CONFLICT")
        if ranking_date < validation_cut:
            if exit_index < index[validation_cut] - EMBARGO:
                role_rows["development"].append(dict(item))
            else:
                purged += 1
        elif ranking_date < sealed_cut:
            if entry_index >= index[validation_cut] + EMBARGO and exit_index < index[sealed_cut] - EMBARGO:
                role_rows["validation"].append(dict(item))
            else:
                purged += 1
        elif entry_index >= index[sealed_cut] + EMBARGO:
            role_rows["sealed"].append(dict(item))
        else:
            purged += 1
    return {
        "schema_version": "entry-cohort-calendar-split.v1",
        "status": "ALLOCATED",
        "roles": {role: sorted(rows, key=lambda item: (item["ranking_date"], item["scenario"])) for role, rows in role_rows.items()},
        "boundaries": [
            {"from": "development", "to": "validation", "cutoff": validation_cut, "embargo_trade_days": EMBARGO},
            {"from": "validation", "to": "sealed", "cutoff": sealed_cut, "embargo_trade_days": EMBARGO},
        ],
        "purged_observation_count": purged,
    }


def _capacity(split: Mapping[str, Any], all_cohorts: Sequence[str], scenarios: Sequence[str]) -> tuple[dict[str, Any], int, int]:
    family_size = max(1, len(all_cohorts) * len(scenarios))
    minimum = max(20, math.ceil(math.log2(family_size / 0.05)))
    capacities: dict[str, Any] = {}
    for cohort in sorted(all_cohorts):
        capacities[cohort] = {}
        for role in ROLES:
            rows = [item for item in split["roles"][role] if item["entry_cohort_id"] == cohort]
            components = overlap_components(rows)
            capacities[cohort][role] = {
                "selection_count": len(rows),
                "calendar_complete_count": len(rows),
                "independent_component_count": len(components),
            }
    return capacities, family_size, minimum


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


def build_audit(*, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None) -> dict[str, Any]:
    root = project_root.resolve()
    decision_payload, decision_record = _committed_json(root, DECISION_RELATIVE)
    if architecture.validate_decision(decision_payload) or decision_payload != architecture.build_decision(project_root=root):
        raise EntryCohortFeasibilityError("ARCHITECTURE_DECISION_CONFLICT")
    availability_payload, availability_record = _committed_json(root, AVAILABILITY_RELATIVE)
    if availability_payload.get("audit_id") != content_hash(availability_payload, omit={"audit_id"}):
        raise EntryCohortFeasibilityError("AVAILABILITY_EVIDENCE_CONFLICT")
    authority_root = coverage.authorize_explicit_authority_root(
        root, authority_root or coverage.discover_authority_root(root)
    )
    receipt = reconciliation.build_receipt(project_root=root, authority_root=authority_root)
    committed_receipt, receipt_record = _committed_json(root, RECONCILIATION_RELATIVE)
    if receipt != committed_receipt or reconciliation.validate_receipt(receipt):
        raise EntryCohortFeasibilityError("CURRENT_RECONCILED_AUTHORITY_DRIFT")
    manifests, ranking_dates = _manifest(availability_payload)
    runtime = receipt["runtime_sources"]
    regime_path = reconciliation._safe_path(authority_root, Path(str(runtime["regime"]["path"])))
    if reconciliation._sha256_file(regime_path) != runtime["regime"]["sha256"]:
        raise EntryCohortFeasibilityError("REGIME_HASH_DRIFT")
    history = json.loads(regime_path.read_text(encoding="utf-8"))
    rows = history.get("rows") if isinstance(history, Mapping) else None
    if not isinstance(rows, list) or not regime_research.validate_as_of_regime_rows(rows)["ok"]:
        raise EntryCohortFeasibilityError("REGIME_AS_OF_CONFLICT")
    feature_inventory, trade_dates = availability._feature_inventory(authority_root)
    if (
        feature_inventory.get("status") != "AVAILABLE"
        or feature_inventory.get("sha256") != runtime["features"]["sha256"]
        or not trade_dates
    ):
        raise EntryCohortFeasibilityError("CALENDAR_HASH_OR_COVERAGE_CONFLICT")
    observations, exclusions = _entry_rows(
        ranking_dates=ranking_dates,
        regime_rows=rows,
        trade_dates=trade_dates,
        scenarios=manifests,
    )
    cohorts = sorted({str(item["entry_cohort_id"]) for item in observations})
    split = build_global_split(observations, trade_dates)
    capacities, family_size, minimum = _capacity(split, cohorts, sorted(manifests))
    provenance_reasons = [
        "RANKING_MODEL_CONFIG_UNBOUND_IN_COMMITTED_MANIFEST",
        "RANKING_UNIVERSE_UNBOUND_IN_COMMITTED_MANIFEST",
        "RANKING_TOP_N_UNBOUND_IN_COMMITTED_MANIFEST",
    ]
    sufficient = any(
        all(capacities[cohort][role]["independent_component_count"] >= minimum for role in ROLES)
        for cohort in cohorts
    )
    status = "BLOCKED_EVIDENCE_OR_CONTRACT_CONFLICT"
    reasons = provenance_reasons
    if not provenance_reasons:
        status = "FEASIBLE_FOR_PREREGISTRATION" if sufficient else "NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY"
        reasons = [] if sufficient else ["NO_PREDECLARED_COHORT_HAS_ALL_ROLE_COMPONENT_CAPACITY"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": "",
        "status": status,
        "reason_codes": reasons,
        "contract": {
            "research_only": True,
            "horizon_trade_bars": HORIZON,
            "entry_delay_trade_days": 1,
            "future_path_controls_selection": False,
            "old_episode_split_reuse_allowed": False,
            "sealed_outcome_access_allowed": False,
        },
        "sources": {
            "architecture_decision": decision_record,
            "availability_manifest": availability_record,
            "reconciliation": receipt_record,
            "runtime": {
                "regime": {"path": runtime["regime"]["path"], "sha256": runtime["regime"]["sha256"]},
                "calendar": {"path": runtime["features"]["path"], "sha256": runtime["features"]["sha256"]},
            },
            "ranking_manifest": {
                "scenarios": {
                    key: {"path": value["path"], "sha256": value["sha256"], "ranking_date_count": len(value["ranking_dates"])}
                    for key, value in manifests.items()
                },
                "provenance_complete": False,
            },
        },
        "inventory": {
            "observation_grain": "ranking_date_x_scenario_x_top_n_portfolio",
            "ranking_date_count": len(ranking_dates),
            "scenario_count": len(manifests),
            "selected_observation_count": len(observations),
            "cohorts": cohorts,
            "exclusions": exclusions,
            "overlap_component_count": len(overlap_components(observations)),
        },
        "split": split,
        "family": {
            "predeclared_scenarios": sorted(manifests),
            "predeclared_cohorts": cohorts,
            "family_size": family_size,
            "minimum_independent_components": minimum,
        },
        "capacity": capacities,
        "sealed_freshness": {
            "namespace": "entry-cohort-calendar-split.v1",
            "outcome_accessed": False,
            "freshness_hash": content_hash({"decision": decision_payload["decision_id"], "split": split}),
        },
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})
    return payload


def validate_audit(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("status") not in ALLOWED_STATUSES:
        errors.append("STATUS_INVALID")
    if payload.get("audit_id") != content_hash(payload, omit={"audit_id"}):
        errors.append("AUDIT_ID_MISMATCH")
    contract = payload.get("contract")
    if not isinstance(contract, Mapping) or contract != {
        "research_only": True, "horizon_trade_bars": HORIZON, "entry_delay_trade_days": 1,
        "future_path_controls_selection": False, "old_episode_split_reuse_allowed": False,
        "sealed_outcome_access_allowed": False,
    }:
        errors.append("CONTRACT_INVALID")
    split = payload.get("split")
    if not isinstance(split, Mapping) or split.get("schema_version") != "entry-cohort-calendar-split.v1":
        errors.append("SPLIT_SCHEMA_INVALID")
    elif split.get("status") == "ALLOCATED":
        boundaries = split.get("boundaries")
        if not isinstance(boundaries, list) or len(boundaries) != 2 or any(item.get("embargo_trade_days") != EMBARGO for item in boundaries if isinstance(item, Mapping)):
            errors.append("SPLIT_EMBARGO_INVALID")
    sources = payload.get("sources")
    provenance = ((sources or {}).get("ranking_manifest") or {}) if isinstance(sources, Mapping) else {}
    if payload.get("status") == "FEASIBLE_FOR_PREREGISTRATION" and provenance.get("provenance_complete") is not True:
        errors.append("FALSE_GO_PROVENANCE_INCOMPLETE")
    if payload.get("status") == "BLOCKED_EVIDENCE_OR_CONTRACT_CONFLICT" and not payload.get("reason_codes"):
        errors.append("BLOCKED_REASON_MISSING")
    if any(value.startswith("/") for value in _strings(payload)):
        errors.append("ABSOLUTE_PATH_FORBIDDEN")
    if any(token in value.lower() for value in _strings(payload) for token in FORBIDDEN_METRIC_TOKENS):
        errors.append("OUTCOME_METRIC_FORBIDDEN")
    return sorted(set(errors))


def encode_audit(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _evidence_path(path: Path, root: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise EntryCohortFeasibilityError("EVIDENCE_PATH_NOT_CANONICAL")
    return _safe_path(root, path)


def write_audit(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    payload = build_audit(authority_root=authority_root)
    errors = validate_audit(payload)
    if errors:
        raise EntryCohortFeasibilityError("AUDIT_VALIDATION_FAILED:" + ",".join(errors))
    target = _evidence_path(path, PROJECT_ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_audit(payload))
    return payload


def verify_audit(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    try:
        target = _evidence_path(path, PROJECT_ROOT)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise EntryCohortFeasibilityError("EVIDENCE_NOT_OBJECT")
        errors = validate_audit(payload)
        if raw != encode_audit(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_audit(authority_root=authority_root):
            errors.append("AUDIT_RECOMPUTE_MISMATCH")
    except EntryCohortFeasibilityError as error:
        return {"status": "FAIL", "errors": [str(error)]}
    except (OSError, json.JSONDecodeError):
        return {"status": "FAIL", "errors": ["EVIDENCE_READ_FAILED"]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build outcome-free entry cohort feasibility evidence")
    parser.add_argument("--authority-root", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_audit(args.verify, authority_root=args.authority_root) if args.verify else write_audit(args.output, authority_root=args.authority_root)
    except EntryCohortFeasibilityError as error:
        result = {"status": "FAIL", "errors": [str(error)]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
