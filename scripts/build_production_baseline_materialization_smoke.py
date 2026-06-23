#!/usr/bin/env python3
"""建立 canonical production baseline materialization smoke。

這支腳本只在 staging path 做最小 smoke；若 canonical provenance 尚未成立，
會明確輸出 BLOCKED，不會建立 artifacts/backtest/production。
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from weekend_training_common import PRODUCTION_IMPACT, repo_path, write_json, write_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKEND_DIR = PROJECT_ROOT / "artifacts" / "weekend_training"
TARGET_BASELINE_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
STAGING_ROOT = WEEKEND_DIR / "staging" / "production_baseline_smoke"
SCHEMA_VERSION = "production-baseline-materialization-smoke.v1"
REQUIRED_COLUMNS = {
    "stock_id",
    "risk_adjusted_score",
    "suggested_weight",
    "max_position_weight",
    "gross_exposure",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production baseline materialization smoke")
    parser.add_argument("--date", required=True)
    parser.add_argument("--training-date", default="2026-06-13")
    parser.add_argument("--design-date", default="2026-06-17")
    parser.add_argument("--smoke-ranking-date", default=None)
    return parser.parse_args()


def artifact_path(stem: str, date: str, suffix: str = "json") -> Path:
    return WEEKEND_DIR / f"{stem}_{date}.{suffix}"


def output_paths(date: str) -> tuple[Path, Path]:
    stem = f"production_baseline_materialization_smoke_{date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ranking_date(path: Path) -> str | None:
    name = path.name
    if name.startswith("ranking_") and name.endswith(".csv"):
        return name[len("ranking_") : -len(".csv")]
    return None


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


def read_first_stock_ids(path: Path, limit: int = 20) -> list[str]:
    ids: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            value = str(row.get("stock_id") or "").strip()
            if value:
                ids.append(value)
            if len(ids) >= limit:
                break
    return ids


def choose_smoke_file(source_path: Path, smoke_date: str | None) -> Path | None:
    files = ranking_files(source_path)
    if not files:
        return None
    if smoke_date:
        wanted = source_path / f"ranking_{smoke_date}.csv"
        if wanted.exists():
            return wanted
    return files[-1]


def source_has_canonical_provenance(source_audit: dict[str, Any], design: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if source_audit.get("status") != "OK":
        blockers.append(f"SOURCE_AUDIT_NOT_OK:{source_audit.get('status')}")
    if source_audit.get("baseline_source_status") != "EXISTING_TARGET_READY":
        blockers.append(f"BASELINE_SOURCE_NOT_CANONICAL:{source_audit.get('baseline_source_status')}")
    if source_audit.get("can_materialize_artifacts_backtest_production") is not True:
        blockers.append("SOURCE_AUDIT_DISALLOWS_MATERIALIZATION")
    if design.get("status") != "DESIGN_READY_FOR_MATERIALIZATION":
        blockers.append(f"DESIGN_NOT_READY_FOR_MATERIALIZATION:{design.get('status')}")
    return not blockers, blockers


def build_contract(design: dict[str, Any]) -> dict[str, Any]:
    answers = design.get("answers") if isinstance(design.get("answers"), dict) else {}
    return {
        "canonical_contract_defined": True,
        "baseline_source_of_truth": answers.get("baseline_source_of_truth")
        or "Canonical backtest-safe production baseline with explicit provenance manifest.",
        "required_columns": sorted(REQUIRED_COLUMNS),
        "preferred_columns": answers.get("preferred_columns") or [],
        "sort_order_contract": "ranking files must be deterministic and sorted by production baseline ranking score descending.",
        "ranking_score_contract": "risk_adjusted_score is the primary comparable ranking score for research replay.",
        "stock_id_contract": "stock_id must be non-empty TW stock identifier, preserved as string-compatible value.",
        "no_future_data_contract": "source manifest must prove ranking date uses only information available by that ranking date.",
        "provenance_fields": [
            "source_artifact_path",
            "generator_command",
            "model_artifact",
            "config_hash",
            "source_data_range",
            "created_by",
        ],
    }


def maybe_stage_smoke(
    source_path: Path,
    source_file: Path,
    output_dir: Path,
    source_audit: dict[str, Any],
    design: dict[str, Any],
) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    staged_file = output_dir / source_file.name
    shutil.copy2(source_file, staged_file)
    manifest = {
        "schema_version": "production-baseline-smoke-staging-manifest.v1",
        "generated_at": now_utc(),
        "source_path": repo_path(source_path),
        "source_file": repo_path(source_file),
        "staged_file": repo_path(staged_file),
        "source_audit": repo_path(artifact_path("weekend_production_baseline_source_audit", "2026-06-13")),
        "provenance_design": repo_path(artifact_path("weekend_production_baseline_provenance_design", "2026-06-17")),
        "production_impact": PRODUCTION_IMPACT,
    }
    write_json(output_dir / "manifest.json", manifest)
    return {"staging_output_dir": repo_path(output_dir), "staged_file": repo_path(staged_file)}


def build_payload(date: str, training_date: str, design_date: str, smoke_date: str | None) -> dict[str, Any]:
    source_audit_path = artifact_path("weekend_production_baseline_source_audit", training_date)
    design_path = artifact_path("weekend_production_baseline_provenance_design", design_date)
    source_audit = read_json(source_audit_path)
    design = read_json(design_path)
    canonical_ok, blockers = source_has_canonical_provenance(source_audit, design)
    source_path = PROJECT_ROOT / str(source_audit.get("baseline_source_path") or "")
    source_file = choose_smoke_file(source_path, smoke_date)
    columns = read_columns(source_file)
    missing_columns = sorted(REQUIRED_COLUMNS - set(columns))
    stock_ids = read_first_stock_ids(source_file) if source_file else []
    stock_id_ok = bool(stock_ids) and all(value.strip() for value in stock_ids)
    production_path_created = TARGET_BASELINE_PATH.exists()
    staging: dict[str, Any] = {}
    smoke_status = "OK" if canonical_ok and source_file and not missing_columns and stock_id_ok else "BLOCKED"
    if smoke_status == "OK":
        staging = maybe_stage_smoke(source_path, source_file, STAGING_ROOT / date, source_audit, design)
    else:
        if not source_file:
            blockers.append("NO_SMOKE_SOURCE_FILE")
        if missing_columns:
            blockers.append(f"MISSING_REQUIRED_COLUMNS:{','.join(missing_columns)}")
        if not stock_id_ok:
            blockers.append("STOCK_ID_CONTRACT_FAILED")
        if production_path_created:
            blockers.append("TARGET_PRODUCTION_BASELINE_PATH_EXISTS")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "training_date": training_date,
        "design_date": design_date,
        "smoke_status": smoke_status,
        "production_impact": PRODUCTION_IMPACT,
        "canonical_contract": build_contract(design),
        "source": {
            "source_audit": repo_path(source_audit_path),
            "provenance_design": repo_path(design_path),
            "source_path": repo_path(source_path) if source_path.exists() else str(source_audit.get("baseline_source_path") or ""),
            "source_file": repo_path(source_file) if source_file else None,
        },
        "checks": {
            "canonical_contract_defined": True,
            "source_provenance_ok": canonical_ok,
            "column_contract_ok": bool(source_file) and not missing_columns,
            "stock_id_contract_ok": stock_id_ok,
            "staging_output_only": smoke_status == "OK",
            "production_baseline_path_created": production_path_created,
            "candidate_source_not_mislabeled_as_production": "candidate" not in str(source_audit.get("baseline_source_path") or ""),
        },
        "staging": staging,
        "summary": {
            "materialization_smoke_status": smoke_status,
            "estimated_unlockable_combo_count": int(source_audit.get("unlockable_combo_count_estimate") or 0) if smoke_status == "OK" else 0,
            "source_file_columns": columns,
            "missing_required_columns": missing_columns,
            "sample_stock_ids": stock_ids[:10],
            "next_action": (
                "open WEEKEND-TRAINING-14_controlled_production_baseline_materialization"
                if smoke_status == "OK"
                else "維持 ARTIFACT_BLOCKER_PROVENANCE_GAP；先補 canonical source provenance，不跑 replay。"
            ),
        },
        "blocker_reasons": sorted(set(blockers)),
        "contract": {
            "research_only": True,
            "staging_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_execute_replay": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
        },
        "errors": [],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    checks = payload["checks"]
    lines = [
        "# Production Baseline Materialization Smoke",
        "",
        f"- smoke_status: `{payload['smoke_status']}`",
        f"- source_provenance_ok: `{checks['source_provenance_ok']}`",
        f"- column_contract_ok: `{checks['column_contract_ok']}`",
        f"- stock_id_contract_ok: `{checks['stock_id_contract_ok']}`",
        f"- staging_output_only: `{checks['staging_output_only']}`",
        f"- production_baseline_path_created: `{checks['production_baseline_path_created']}`",
        f"- estimated_unlockable_combo_count: `{summary['estimated_unlockable_combo_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        f"- next_action: {summary['next_action']}",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blocker_reasons") or []
    if blockers:
        for reason in blockers:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- none")
    lines.extend(["", "No production ranking, model, replay, or Clawd changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args.date, args.training_date, args.design_date, args.smoke_ranking_date)
    json_path, md_path = output_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["smoke_status"],
                "output": repo_path(json_path),
                "source_provenance_ok": payload["checks"]["source_provenance_ok"],
                "estimated_unlockable_combo_count": payload["summary"]["estimated_unlockable_combo_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
