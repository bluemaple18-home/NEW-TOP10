#!/usr/bin/env python3
"""驗證 research-only production baseline smoke materialization。"""

from __future__ import annotations

import argparse
import json
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


VERIFY_SCHEMA_VERSION = "research-only-baseline-materialization-smoke-verification.v1"
MANIFEST_SCHEMA_VERSION = "research-only-production-baseline-smoke-manifest.v1"
SUMMARY_SCHEMA_VERSION = "research-only-baseline-materialization-smoke.v1"
EXPECTED_DATES = ["2026-05-13", "2026-05-14", "2026-05-15"]
TARGET_OUTPUT_PATH = "artifacts/backtest/production_baseline_harness_smoke"
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify research-only production baseline smoke")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--target-dir", default=TARGET_OUTPUT_PATH)
    parser.add_argument(
        "--summary",
        default=None,
        help="預設 artifacts/weekend_training/research_only_baseline_materialization_smoke_YYYY-MM-DD.json",
    )
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/research_only_baseline_materialization_smoke_verification_latest.json",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def is_exact_path(path: Path, expected_repo_path: str) -> bool:
    expected = PROJECT_ROOT / expected_repo_path
    return path.resolve() == expected.resolve()


def contains_forbidden_text(*payloads: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payloads, ensure_ascii=False)


def summary_path(run_date: str, override: str | None) -> Path:
    if override:
        path = resolve_path(override)
        assert path is not None
        return path
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"research_only_baseline_materialization_smoke_{run_date}.json"


def ranking_files(target_dir: Path) -> list[Path]:
    return sorted(path for path in target_dir.glob("ranking_*.csv") if path.is_file())


def ranking_date(path: Path) -> str:
    return path.stem.removeprefix("ranking_")


def build_payload(run_date: str, target_dir: Path, summary_file: Path) -> dict[str, Any]:
    manifest_path = target_dir / "manifest.json"
    manifest = read_json(manifest_path)
    summary = read_json(summary_file)
    files = ranking_files(target_dir) if target_dir.exists() else []
    dates = [ranking_date(path) for path in files]
    copied_files = manifest.get("copied_files") if isinstance(manifest.get("copied_files"), list) else []
    contract = manifest.get("contract") if isinstance(manifest.get("contract"), dict) else {}
    lineage = manifest.get("lineage") if isinstance(manifest.get("lineage"), dict) else {}
    checks = [
        {
            "name": "target_path_exact",
            "ok": is_exact_path(target_dir, TARGET_OUTPUT_PATH),
            "value": repo_path(target_dir),
        },
        {"name": "target_dir_exists", "ok": target_dir.exists() and target_dir.is_dir(), "value": repo_path(target_dir)},
        {"name": "manifest_exists", "ok": manifest_path.exists(), "value": repo_path(manifest_path)},
        {
            "name": "manifest_schema",
            "ok": manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
            "value": manifest.get("schema_version"),
        },
        {"name": "summary_exists", "ok": summary_file.exists(), "value": repo_path(summary_file)},
        {
            "name": "summary_schema",
            "ok": summary.get("schema_version") == SUMMARY_SCHEMA_VERSION,
            "value": summary.get("schema_version"),
        },
        {
            "name": "ranking_file_count_three",
            "ok": len(files) == 3 and manifest.get("ranking_file_count") == 3 and summary.get("ranking_file_count") == 3,
            "value": {"actual_files": len(files), "manifest": manifest.get("ranking_file_count"), "summary": summary.get("ranking_file_count")},
        },
        {
            "name": "dates_exact",
            "ok": dates == EXPECTED_DATES and manifest.get("ranking_dates") == EXPECTED_DATES and summary.get("dates") == EXPECTED_DATES,
            "value": {"files": dates, "manifest": manifest.get("ranking_dates"), "summary": summary.get("dates")},
        },
        {
            "name": "manifest_traces_source_staging_harness",
            "ok": bool(manifest.get("source_staging_manifest"))
            and lineage.get("traces_source_staging_harness") is True
            and lineage.get("copied_from_staging_harness") is True,
            "value": {"source_staging_manifest": manifest.get("source_staging_manifest"), "lineage": lineage},
        },
        {
            "name": "copied_files_trace_all_dates",
            "ok": len(copied_files) == 3
            and [str(row.get("date")) for row in copied_files if isinstance(row, dict)] == EXPECTED_DATES
            and all(row.get("source_path") and row.get("target_path") and row.get("source_sha256") == row.get("target_sha256") for row in copied_files if isinstance(row, dict)),
            "value": copied_files,
        },
        {
            "name": "estimated_unlockable_combo_count_zero",
            "ok": manifest.get("estimated_unlockable_combo_count") == 0 and summary.get("estimated_unlockable_combo_count") == 0,
            "value": {"manifest": manifest.get("estimated_unlockable_combo_count"), "summary": summary.get("estimated_unlockable_combo_count")},
        },
        {
            "name": "target_production_path_absent",
            "ok": FORBIDDEN_PRODUCTION_PATH.exists() is False
            and manifest.get("target_production_path_created") is False
            and summary.get("target_production_path_created") is False,
            "value": {
                "path": repo_path(FORBIDDEN_PRODUCTION_PATH),
                "exists": FORBIDDEN_PRODUCTION_PATH.exists(),
                "manifest": manifest.get("target_production_path_created"),
                "summary": summary.get("target_production_path_created"),
            },
        },
        {
            "name": "production_impact_no_change",
            "ok": manifest.get("production_impact") == PRODUCTION_IMPACT and summary.get("production_impact") == PRODUCTION_IMPACT,
            "value": {"manifest": manifest.get("production_impact"), "summary": summary.get("production_impact")},
        },
        {
            "name": "research_only_contract",
            "ok": manifest.get("research_only") is True
            and summary.get("research_only") is True
            and contract.get("research_only") is True
            and contract.get("three_day_smoke_only") is True
            and contract.get("does_not_execute_replay") is True
            and contract.get("does_not_create_artifacts_backtest_production") is True
            and contract.get("does_not_change_production_ranking") is True
            and contract.get("does_not_write_models_latest_lgbm") is True
            and contract.get("does_not_publish_clawd") is True,
            "value": contract,
        },
        {
            "name": "no_promotion_ready",
            "ok": not contains_forbidden_text(manifest, summary) and contract.get("no_promotion_ready") is True,
            "value": False,
        },
        {
            "name": "materialization_status_ok",
            "ok": manifest.get("materialization_status") == "OK" and summary.get("materialization_status") == "OK",
            "value": {"manifest": manifest.get("materialization_status"), "summary": summary.get("materialization_status")},
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "status": "OK" if not failed else "FAILED",
        "target_output_path": repo_path(target_dir),
        "manifest": repo_path(manifest_path),
        "summary_artifact": repo_path(summary_file),
        "verification_summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "ranking_file_count": len(files),
            "dates": dates,
            "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
            "estimated_unlockable_combo_count": manifest.get("estimated_unlockable_combo_count"),
            "production_impact": manifest.get("production_impact"),
        },
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    target_dir = resolve_path(args.target_dir)
    output = resolve_path(args.output)
    assert target_dir is not None and output is not None
    payload = build_payload(str(args.date), target_dir, summary_path(str(args.date), args.summary))
    write_json(output, payload)
    print(f"RESEARCH_ONLY_BASELINE_SMOKE_VERIFICATION_{payload['status']} output={repo_path(output)}")
    if payload["status"] != "OK":
        for error in payload["errors"]:
            print(f"ERROR: {error['name']} value={error.get('value')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
