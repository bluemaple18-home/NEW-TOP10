#!/usr/bin/env python3
"""建立 production baseline ranking source audit。

這支腳本只讀既有 artifacts，判定 `artifacts/backtest/production`
是否有合法來源可接線或 materialize；不建立 ranking 目錄、不跑 replay。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from weekend_training_common import PRODUCTION_IMPACT, inventory_paths, repo_path, write_json, write_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKEND_DIR = PROJECT_ROOT / "artifacts" / "weekend_training"
SCHEMA_VERSION = "weekend-production-baseline-source-audit.v1"
TARGET_BASELINE_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
REQUIRED_COLUMNS = {
    "stock_id",
    "risk_adjusted_score",
    "suggested_weight",
    "max_position_weight",
    "gross_exposure",
}
PREFERRED_COLUMNS = {
    "stock_name",
    "final_score",
    "model_prob",
    "allocated_exposure",
    "cash_weight",
    "market_regime",
    "reasons",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production baseline source audit")
    parser.add_argument("--date", required=True)
    parser.add_argument("--max-candidates", type=int, default=40)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def audit_paths(date: str) -> tuple[Path, Path]:
    stem = f"weekend_production_baseline_source_audit_{date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def ranking_date(path: Path) -> str | None:
    match = re.fullmatch(r"ranking_(\d{4}-\d{2}-\d{2})\.csv", path.name)
    return match.group(1) if match else None


def ranking_files(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(item for item in path.glob("ranking_*.csv") if ranking_date(item))


def read_columns(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return [str(item).strip() for item in next(reader)]
        except StopIteration:
            return []


def source_kind(path: Path) -> str:
    text = repo_path(path) or str(path)
    if path == TARGET_BASELINE_PATH:
        return "target_path"
    if "production_subset" in text:
        return "production_subset"
    if "current_model_sealed" in text:
        return "current_model_sealed"
    if "historical_rankings_current_model" in text:
        return "historical_current_model"
    if "/production" in f"/{text}" and "candidate" not in text:
        return "production_named"
    if "publish_rankings" in text:
        return "publish_output"
    if "candidate" in text:
        return "candidate_or_candidate_scoped"
    if path.name == "production":
        return "local_production_subdir"
    return "unknown"


def has_manifest(path: Path) -> bool:
    return (path / "manifest.json").exists() or (path / "analysis_report.yaml").exists() or (path / "analysis_report.md").exists()


def candidate_dirs_from_inventory(date: str) -> tuple[dict[str, int], dict[str, int], dict[str, Any]]:
    inventory_path, _ = inventory_paths(date)
    inventory = read_json(inventory_path)
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    rows = [
        row
        for row in records
        if isinstance(row, dict)
        and row.get("burn_down_status") == "UNSUPPORTED_INPUT"
        and row.get("unsupported_reason") == "MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production"
    ]
    by_candidate = Counter(str(row.get("candidate_dir") or "") for row in rows)
    by_entry_filter = Counter(str((row.get("dimensions") or {}).get("entry_filter") or "") for row in rows)
    return dict(by_candidate), dict(by_entry_filter), {
        "inventory": repo_path(inventory_path),
        "missing_baseline_rows": len(rows),
        "unique_candidate_dirs": len(by_candidate),
        "entry_filter_counts": dict(sorted(by_entry_filter.items())),
    }


def discover_source_dirs() -> list[Path]:
    roots = [
        TARGET_BASELINE_PATH,
        PROJECT_ROOT / "artifacts" / "backtest" / "historical_rankings_current_model",
        PROJECT_ROOT / "artifacts" / "research_rankings" / "current_model_sealed_2026-02-06_2026-05-15",
        PROJECT_ROOT / "artifacts" / "research_rankings" / "current_model_sealed_no_setup",
        PROJECT_ROOT / "artifacts" / "research_rankings" / "current_model_sealed_conservative_setup",
        PROJECT_ROOT / "artifacts" / "research_rankings" / "current_model_sealed_model_only",
        PROJECT_ROOT / "artifacts" / "backtest" / "production_subset_rankings_recent_100_2025-12-10_2026-05-15",
        PROJECT_ROOT / "artifacts" / "backtest" / "production_subset_rankings_recent_6m_2025-11-12_2026-05-15",
        PROJECT_ROOT / "artifacts" / "publish_rankings" / "consensus",
        PROJECT_ROOT / "artifacts" / "model_experiments" / "strategy_composition_isolation_work_2026-06-10" / "production_all_rankings",
    ]
    backtest_root = PROJECT_ROOT / "artifacts" / "backtest"
    if backtest_root.exists():
        roots.extend(item for item in backtest_root.glob("*/production") if item.is_dir())
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in roots:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def evaluate_source(path: Path) -> dict[str, Any]:
    files = ranking_files(path)
    dates = [ranking_date(item) for item in files]
    dates = [item for item in dates if item]
    columns = read_columns(files[-1] if files else None)
    column_set = set(columns)
    missing_required = sorted(REQUIRED_COLUMNS - column_set)
    missing_preferred = sorted(PREFERRED_COLUMNS - column_set)
    kind = source_kind(path)
    is_candidate_like = kind == "candidate_or_candidate_scoped" or ("candidate" in (repo_path(path) or "") and path.name != "production")
    has_provenance = has_manifest(path)
    coverage = {
        "ranking_file_count": len(files),
        "start_date": dates[0] if dates else None,
        "end_date": dates[-1] if dates else None,
        "sample_file": repo_path(files[-1]) if files else None,
    }
    column_contract_ok = bool(files) and not missing_required
    comparable = column_contract_ok and bool(dates) and not is_candidate_like
    materialize_ready = path == TARGET_BASELINE_PATH and column_contract_ok
    smoke_candidate = (
        not materialize_ready
        and comparable
        and kind in {"current_model_sealed", "production_subset", "historical_current_model", "production_named"}
    )
    score = 0
    score += min(len(files), 120)
    score += 100 if column_contract_ok else 0
    score += 40 if has_provenance else 0
    score += 25 if kind in {"current_model_sealed", "production_subset", "historical_current_model"} else 0
    score -= 80 if is_candidate_like else 0
    return {
        "path": repo_path(path),
        "exists": path.exists(),
        "source_kind": kind,
        "ranking_file_count": len(files),
        "date_coverage": coverage,
        "required_columns": sorted(REQUIRED_COLUMNS),
        "missing_required_columns": missing_required,
        "missing_preferred_columns": missing_preferred,
        "column_contract_ok": column_contract_ok,
        "has_provenance_artifact": has_provenance,
        "candidate_like_path": is_candidate_like,
        "comparable_with_candidate_rankings": comparable,
        "materialize_ready": materialize_ready,
        "minimum_smoke_candidate": smoke_candidate,
        "score": score,
    }


def build_payload(date: str, max_candidates: int) -> dict[str, Any]:
    candidate_dir_counts, entry_filter_counts, inventory_summary = candidate_dirs_from_inventory(date)
    sources = [evaluate_source(path) for path in discover_source_dirs()]
    sources.sort(key=lambda item: (-int(item["score"]), str(item["path"] or "")))
    best = sources[0] if sources else {}
    target = next((item for item in sources if item.get("path") == "artifacts/backtest/production"), None)
    smoke_candidates = [item for item in sources if item.get("minimum_smoke_candidate")]
    blocker_reasons: list[str] = []
    if not target or not target.get("exists"):
        blocker_reasons.append("TARGET_BASELINE_DIR_MISSING:artifacts/backtest/production")
    if not smoke_candidates:
        blocker_reasons.append("NO_COMPARABLE_NON_CANDIDATE_SOURCE_WITH_COLUMN_CONTRACT")
    else:
        blocker_reasons.append("SOURCE_PROVENANCE_NOT_CANONICAL_FOR_ARTIFACTS_BACKTEST_PRODUCTION")
    can_materialize = bool(target and target.get("materialize_ready"))
    status = "OK" if can_materialize else "BLOCKED"
    baseline_source_path = target.get("path") if can_materialize and target else (smoke_candidates[0].get("path") if smoke_candidates else best.get("path"))
    baseline_source_status = "EXISTING_TARGET_READY" if can_materialize else "BLOCKED_PROVENANCE_GAP"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date,
        "status": status,
        "baseline_source_status": baseline_source_status,
        "baseline_source_path": baseline_source_path,
        "date_coverage": (smoke_candidates[0] if smoke_candidates else best).get("date_coverage") if (smoke_candidates or best) else {},
        "required_columns": sorted(REQUIRED_COLUMNS),
        "column_contract_ok": bool((smoke_candidates[0] if smoke_candidates else best).get("column_contract_ok")) if (smoke_candidates or best) else False,
        "comparable_with_candidate_rankings": False if not can_materialize else True,
        "can_materialize_artifacts_backtest_production": can_materialize,
        "unlockable_combo_count_estimate": int(inventory_summary["missing_baseline_rows"]) if can_materialize else 0,
        "next_action": (
            "open WEEKEND-TRAINING-12 materialize smoke; do not expand 202176 combos"
            if can_materialize
            else "mark UNSUPPORTED_RANKING_DIR_MISSING as artifact blocker until canonical baseline source is proven"
        ),
        "production_impact": PRODUCTION_IMPACT,
        "blocker_reasons": blocker_reasons,
        "source": {
            "inventory": inventory_summary["inventory"],
            "target_baseline_path": "artifacts/backtest/production",
        },
        "summary": {
            "missing_baseline_rows": inventory_summary["missing_baseline_rows"],
            "unique_candidate_dirs": inventory_summary["unique_candidate_dirs"],
            "entry_filter_counts": entry_filter_counts,
            "source_candidate_count": len(sources),
            "minimum_smoke_candidate_count": len(smoke_candidates),
            "top_candidate_dirs": dict(Counter(candidate_dir_counts).most_common(10)),
        },
        "candidate_sources": sources[: max(max_candidates, 0)],
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_create_ranking_dirs": True,
            "does_not_symlink_or_copy_baseline": True,
            "does_not_change_production_ranking": True,
            "does_not_train_model": True,
            "does_not_publish_clawd": True,
        },
        "errors": [],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Weekend Production Baseline Source Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- baseline_source_status: `{payload['baseline_source_status']}`",
        f"- baseline_source_path: `{payload['baseline_source_path']}`",
        f"- can_materialize_artifacts_backtest_production: `{payload['can_materialize_artifacts_backtest_production']}`",
        f"- unlockable_combo_count_estimate: `{payload['unlockable_combo_count_estimate']}`",
        f"- production_impact: `{payload['production_impact']}`",
        f"- next_action: {payload['next_action']}",
        "",
        "## Blockers",
        "",
    ]
    for reason in payload.get("blocker_reasons") or []:
        lines.append(f"- `{reason}`")
    lines.extend(["", "## Candidate Sources", ""])
    for source in payload.get("candidate_sources", [])[:10]:
        coverage = source.get("date_coverage") or {}
        lines.extend(
            [
                f"### {source.get('path')}",
                "",
                f"- kind: `{source.get('source_kind')}`",
                f"- ranking_file_count: `{source.get('ranking_file_count')}`",
                f"- date_coverage: `{coverage.get('start_date')}` to `{coverage.get('end_date')}`",
                f"- column_contract_ok: `{source.get('column_contract_ok')}`",
                f"- has_provenance_artifact: `{source.get('has_provenance_artifact')}`",
                f"- comparable_with_candidate_rankings: `{source.get('comparable_with_candidate_rankings')}`",
                f"- minimum_smoke_candidate: `{source.get('minimum_smoke_candidate')}`",
                "",
            ]
        )
    lines.append("No production ranking, model, Clawd, symlink, copy, or replay changes.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args.date, args.max_candidates)
    json_path, md_path = audit_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(json_path),
                "baseline_source_status": payload["baseline_source_status"],
                "can_materialize_artifacts_backtest_production": payload["can_materialize_artifacts_backtest_production"],
                "unlockable_combo_count_estimate": payload["unlockable_combo_count_estimate"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
