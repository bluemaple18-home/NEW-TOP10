#!/usr/bin/env python3
"""產生三日 research-only production baseline harness smoke。

此腳本只複製已驗證 staging harness 的三個 ranking CSV 到 research-only path；
不建立 artifacts/backtest/production，不跑 replay，不改模型、不改正式 ranking。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json  # noqa: E402


SCHEMA_VERSION = "research-only-production-baseline-smoke-manifest.v1"
SUMMARY_SCHEMA_VERSION = "research-only-baseline-materialization-smoke.v1"
TASK_ID = "WEEKEND-TRAINING-16"
EXPECTED_DATES = ["2026-05-13", "2026-05-14", "2026-05-15"]
DEFAULT_REVIEW = "artifacts/weekend_training/production_baseline_materialization_review_2026-06-18.json"
DEFAULT_STAGING_MANIFEST = "artifacts/weekend_training/staging/production_baseline_harness_2026-06-18/manifest.json"
TARGET_OUTPUT_PATH = "artifacts/backtest/production_baseline_harness_smoke"
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="materialize research-only production baseline smoke")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--review", default=DEFAULT_REVIEW)
    parser.add_argument("--staging-manifest", default=DEFAULT_STAGING_MANIFEST)
    parser.add_argument("--target-dir", default=TARGET_OUTPUT_PATH)
    parser.add_argument(
        "--summary-output",
        default=None,
        help="預設 artifacts/weekend_training/research_only_baseline_materialization_smoke_YYYY-MM-DD.json",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_exact_path(path: Path, expected_repo_path: str) -> bool:
    expected = PROJECT_ROOT / expected_repo_path
    return path.resolve() == expected.resolve()


def contains_forbidden_text(*payloads: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payloads, ensure_ascii=False)


def output_summary_path(run_date: str, override: str | None) -> Path:
    if override:
        path = resolve_path(override)
        assert path is not None
        return path
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"research_only_baseline_materialization_smoke_{run_date}.json"


def validate_inputs(review: dict[str, Any], staging_manifest: dict[str, Any], target_dir: Path) -> list[str]:
    errors: list[str] = []
    review_dates = ((review.get("allowed_date_range") or {}).get("dates") or [])
    staging_dates = staging_manifest.get("ranking_dates") or []
    expected_dates = staging_manifest.get("expected_ranking_dates") or []
    review_target = review.get("target_output_path")
    staging_contract = staging_manifest.get("contract") if isinstance(staging_manifest.get("contract"), dict) else {}

    if review.get("materialization_review_status") != "OK":
        errors.append(f"review status is not OK: {review.get('materialization_review_status')}")
    if review.get("can_materialize_research_baseline") is not True:
        errors.append("review does not allow research baseline materialization")
    if review.get("estimated_unlockable_combo_count") != 0:
        errors.append(f"estimated_unlockable_combo_count must be 0: {review.get('estimated_unlockable_combo_count')}")
    if review.get("production_impact") != PRODUCTION_IMPACT:
        errors.append(f"review production_impact must be {PRODUCTION_IMPACT}: {review.get('production_impact')}")
    if list(review_dates) != EXPECTED_DATES:
        errors.append(f"review allowed dates mismatch: {review_dates}")
    if review_target != TARGET_OUTPUT_PATH:
        errors.append(f"review target_output_path mismatch: {review_target}")
    if not is_exact_path(target_dir, TARGET_OUTPUT_PATH):
        errors.append(f"target-dir must be exactly {TARGET_OUTPUT_PATH}: {repo_path(target_dir)}")
    if FORBIDDEN_PRODUCTION_PATH.exists():
        errors.append(f"forbidden production path exists: {repo_path(FORBIDDEN_PRODUCTION_PATH)}")
    if staging_manifest.get("schema_version") != "production-baseline-harness-manifest.v1":
        errors.append(f"staging manifest schema mismatch: {staging_manifest.get('schema_version')}")
    if staging_manifest.get("production_impact") != PRODUCTION_IMPACT:
        errors.append(f"staging production_impact must be {PRODUCTION_IMPACT}: {staging_manifest.get('production_impact')}")
    if list(staging_dates) != EXPECTED_DATES or list(expected_dates) != EXPECTED_DATES:
        errors.append(f"staging dates mismatch: ranking={staging_dates} expected={expected_dates}")
    if staging_contract.get("research_only") is not True or staging_contract.get("does_not_execute_replay") is not True:
        errors.append("staging manifest contract must be research_only and does_not_execute_replay")
    if staging_contract.get("does_not_create_artifacts_backtest_production") is not True:
        errors.append("staging manifest must explicitly avoid artifacts/backtest/production")
    if contains_forbidden_text(review, staging_manifest):
        errors.append(f"forbidden text present: {FORBIDDEN_TEXT}")
    return errors


def source_ranking_paths(staging_manifest: dict[str, Any], staging_manifest_path: Path) -> dict[str, Path]:
    per_file = ((staging_manifest.get("ranking_quality") or {}).get("per_file") or [])
    result: dict[str, Path] = {}
    for row in per_file:
        if not isinstance(row, dict):
            continue
        date_text = str(row.get("date") or "")
        path = resolve_path(row.get("path"))
        if date_text and path:
            result[date_text] = path
    output_dir = resolve_path(staging_manifest.get("output_dir")) or staging_manifest_path.parent
    for date_text in EXPECTED_DATES:
        result.setdefault(date_text, output_dir / f"ranking_{date_text}.csv")
    return result


def build_manifest(
    run_date: str,
    review_path: Path,
    staging_manifest_path: Path,
    staging_manifest: dict[str, Any],
    target_dir: Path,
    copied_files: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "task_id": TASK_ID,
        "research_only": True,
        "materialization_status": "OK",
        "target_output_path": repo_path(target_dir),
        "forbidden_production_path": repo_path(FORBIDDEN_PRODUCTION_PATH),
        "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
        "source_review": repo_path(review_path),
        "source_staging_manifest": repo_path(staging_manifest_path),
        "source_staging_output_dir": staging_manifest.get("output_dir"),
        "source_schema_version": staging_manifest.get("schema_version"),
        "allowed_dates": EXPECTED_DATES,
        "ranking_dates": [row["date"] for row in copied_files],
        "ranking_file_count": len(copied_files),
        "estimated_unlockable_combo_count": 0,
        "production_impact": PRODUCTION_IMPACT,
        "copied_files": copied_files,
        "lineage": {
            "traces_source_staging_harness": True,
            "copied_from_staging_harness": True,
            "source_pipeline": staging_manifest.get("source_pipeline"),
            "source_generator_manifest": (staging_manifest.get("lineage") or {}).get("generator_manifest"),
            "source_model_artifact": staging_manifest.get("model_artifact"),
            "source_model_hash": staging_manifest.get("model_hash"),
            "source_config": staging_manifest.get("config"),
            "source_config_hash": staging_manifest.get("config_hash"),
        },
        "contract": {
            "research_only": True,
            "three_day_smoke_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_execute_replay": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
            "no_promotion_ready": True,
            "smoke_materialization_is_not_production_baseline_complete": True,
        },
        "next_action": "WEEKEND-TRAINING-17_baseline_harness_minimal_replay_smoke",
    }


def build_summary(run_date: str, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "task_id": TASK_ID,
        "materialization_status": manifest.get("materialization_status"),
        "research_only": manifest.get("research_only"),
        "target_output_path": manifest.get("target_output_path"),
        "manifest": f"{manifest.get('target_output_path')}/manifest.json",
        "ranking_file_count": manifest.get("ranking_file_count"),
        "dates": manifest.get("ranking_dates"),
        "target_production_path_created": manifest.get("target_production_path_created"),
        "estimated_unlockable_combo_count": manifest.get("estimated_unlockable_combo_count"),
        "production_impact": manifest.get("production_impact"),
        "contract": manifest.get("contract"),
        "next_action": manifest.get("next_action"),
    }


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    run_date = str(args.date)
    review_path = resolve_path(args.review)
    staging_manifest_path = resolve_path(args.staging_manifest)
    target_dir = resolve_path(args.target_dir)
    assert review_path is not None and staging_manifest_path is not None and target_dir is not None

    review = read_json(review_path)
    staging_manifest = read_json(staging_manifest_path)
    errors = validate_inputs(review, staging_manifest, target_dir)
    sources = source_ranking_paths(staging_manifest, staging_manifest_path)
    for date_text in EXPECTED_DATES:
        source = sources.get(date_text)
        if source is None or not source.exists():
            errors.append(f"missing source ranking for {date_text}: {repo_path(source) if source else None}")
    if errors:
        raise RuntimeError("; ".join(errors))

    target_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[dict[str, Any]] = []
    for date_text in EXPECTED_DATES:
        source = sources[date_text]
        target = target_dir / f"ranking_{date_text}.csv"
        shutil.copy2(source, target)
        copied_files.append(
            {
                "date": date_text,
                "source_path": repo_path(source),
                "target_path": repo_path(target),
                "source_sha256": sha256(source),
                "target_sha256": sha256(target),
                "bytes": target.stat().st_size,
            }
        )

    manifest = build_manifest(run_date, review_path, staging_manifest_path, staging_manifest, target_dir, copied_files)
    manifest_path = target_dir / "manifest.json"
    write_json(manifest_path, manifest)
    summary = build_summary(run_date, manifest)
    write_json(output_summary_path(run_date, args.summary_output), summary)
    return summary


def main() -> int:
    args = parse_args()
    try:
        summary = materialize(args)
    except Exception as exc:
        print(f"RESEARCH_ONLY_BASELINE_MATERIALIZATION_FAILED {exc}", file=sys.stderr)
        return 1
    print(
        "RESEARCH_ONLY_BASELINE_MATERIALIZATION_OK "
        f"target={summary['target_output_path']} ranking_file_count={summary['ranking_file_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
