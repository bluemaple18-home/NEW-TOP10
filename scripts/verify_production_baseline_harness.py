#!/usr/bin/env python3
"""驗證 production baseline staging harness。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_production_baseline_harness import (  # noqa: E402
    REQUIRED_COLUMNS,
    SCHEMA_VERSION,
    SMOKE_SCHEMA_VERSION,
    STAGING_ROOT,
    TARGET_BASELINE_PATH,
    smoke_paths,
)
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json  # noqa: E402


VERIFY_SCHEMA_VERSION = "production-baseline-harness-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production baseline harness")
    parser.add_argument("--date", required=True)
    parser.add_argument("--smoke-artifact", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/production_baseline_harness_verification_latest.json",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def is_under(path_text: str | None, root: Path) -> bool:
    if not path_text:
        return False
    path = resolve_path(path_text)
    if path is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def contains_forbidden_text(*payloads: dict[str, Any]) -> bool:
    return any("PROMOTION_READY" in json.dumps(payload, ensure_ascii=False) for payload in payloads)


def ranking_path(output_dir: Path, date_text: str) -> Path:
    return output_dir / f"ranking_{date_text}.csv"


def verify_ranking_files(manifest: dict[str, Any]) -> dict[str, Any]:
    output_dir_text = manifest.get("output_dir")
    output_dir = resolve_path(output_dir_text)
    dates = manifest.get("ranking_dates") if isinstance(manifest.get("ranking_dates"), list) else []
    expected_dates = manifest.get("expected_ranking_dates") if isinstance(manifest.get("expected_ranking_dates"), list) else []
    errors: list[dict[str, Any]] = []
    row_counts: dict[str, int] = {}
    if output_dir is None or not output_dir.exists():
        return {
            "ok": False,
            "date_coverage_ok": False,
            "schema_columns_ok": False,
            "stock_id_non_empty": False,
            "ranking_order_deterministic": False,
            "row_counts": {},
            "errors": [{"date": None, "reason": "OUTPUT_DIR_MISSING", "path": output_dir_text}],
        }

    for date_text in dates:
        path = ranking_path(output_dir, str(date_text))
        if not path.exists():
            errors.append({"date": date_text, "reason": "RANKING_FILE_MISSING", "path": repo_path(path)})
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_id": str})
        row_counts[str(date_text)] = int(len(frame))
        missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
        if missing:
            errors.append({"date": date_text, "reason": "MISSING_REQUIRED_COLUMNS", "missing": missing})
        if frame.empty:
            errors.append({"date": date_text, "reason": "RANKING_EMPTY"})
        if "stock_id" not in frame.columns or frame["stock_id"].fillna("").astype(str).str.strip().eq("").any():
            errors.append({"date": date_text, "reason": "STOCK_ID_EMPTY"})
        if "stock_id" in frame.columns and frame["stock_id"].astype(str).duplicated().any():
            errors.append({"date": date_text, "reason": "STOCK_ID_DUPLICATE"})
        if "risk_adjusted_score" not in frame.columns:
            errors.append({"date": date_text, "reason": "RISK_ADJUSTED_SCORE_MISSING"})
        else:
            scores = pd.to_numeric(frame["risk_adjusted_score"], errors="coerce")
            if scores.isna().any() or not scores.is_monotonic_decreasing:
                errors.append({"date": date_text, "reason": "RANKING_ORDER_NOT_DESCENDING"})

    generated_set = {str(item) for item in dates}
    expected_set = {str(item) for item in expected_dates}
    if generated_set != expected_set:
        errors.append(
            {
                "date": None,
                "reason": "DATE_COVERAGE_MISMATCH",
                "missing": sorted(expected_set - generated_set),
                "extra": sorted(generated_set - expected_set),
            }
        )
    reasons = {str(item.get("reason")) for item in errors}
    return {
        "ok": not errors and bool(dates),
        "date_coverage_ok": "DATE_COVERAGE_MISMATCH" not in reasons and bool(dates),
        "schema_columns_ok": "MISSING_REQUIRED_COLUMNS" not in reasons and bool(dates),
        "stock_id_non_empty": not ({"RANKING_EMPTY", "STOCK_ID_EMPTY", "STOCK_ID_DUPLICATE"} & reasons) and bool(dates),
        "ranking_order_deterministic": not ({"RISK_ADJUSTED_SCORE_MISSING", "RANKING_ORDER_NOT_DESCENDING"} & reasons)
        and bool(dates),
        "row_counts": row_counts,
        "errors": errors,
    }


def has_complete_provenance(manifest: dict[str, Any]) -> bool:
    data_source = manifest.get("data_source") if isinstance(manifest.get("data_source"), dict) else {}
    no_future = manifest.get("no_future_data_contract") if isinstance(manifest.get("no_future_data_contract"), dict) else {}
    required = [
        manifest.get("generator_command"),
        manifest.get("source_pipeline"),
        manifest.get("model_artifact"),
        manifest.get("model_hash"),
        manifest.get("config"),
        manifest.get("config_hash"),
        data_source.get("features"),
        data_source.get("features_hash"),
        manifest.get("start_date"),
        manifest.get("end_date"),
        no_future.get("ranking_row_contract"),
        no_future.get("market_regime_contract"),
    ]
    return all(bool(item) for item in required)


def build_payload(date: str, smoke_artifact: Path, manifest_path: Path) -> dict[str, Any]:
    smoke = read_json(smoke_artifact)
    manifest = read_json(manifest_path)
    ranking = verify_ranking_files(manifest)
    checks_payload = manifest.get("checks") if isinstance(manifest.get("checks"), dict) else {}
    lineage = manifest.get("lineage") if isinstance(manifest.get("lineage"), dict) else {}
    contract = manifest.get("contract") if isinstance(manifest.get("contract"), dict) else {}
    harness_status = smoke.get("harness_status") or (manifest.get("summary") or {}).get("harness_status")
    output_dir = manifest.get("output_dir")
    blockers = smoke.get("blocker_reasons") if isinstance(smoke.get("blocker_reasons"), list) else []
    production_path_exists = TARGET_BASELINE_PATH.exists()
    checks = [
        {"name": "smoke_artifact_exists", "ok": smoke_artifact.exists(), "value": repo_path(smoke_artifact)},
        {"name": "smoke_schema", "ok": smoke.get("schema_version") == SMOKE_SCHEMA_VERSION, "value": smoke.get("schema_version")},
        {"name": "manifest_exists", "ok": manifest_path.exists(), "value": repo_path(manifest_path)},
        {"name": "manifest_schema", "ok": manifest.get("schema_version") == SCHEMA_VERSION, "value": manifest.get("schema_version")},
        {"name": "harness_status_explicit", "ok": harness_status in {"OK", "BLOCKED"}, "value": harness_status},
        {"name": "schema_columns_ok", "ok": ranking["schema_columns_ok"], "value": ranking["errors"]},
        {"name": "date_coverage_ok", "ok": ranking["date_coverage_ok"], "value": manifest.get("ranking_dates")},
        {"name": "stock_id_non_empty", "ok": ranking["stock_id_non_empty"], "value": ranking["row_counts"]},
        {"name": "ranking_order_deterministic", "ok": ranking["ranking_order_deterministic"], "value": ranking["errors"]},
        {
            "name": "manifest_has_generator_command_model_config_data_range",
            "ok": has_complete_provenance(manifest),
            "value": {
                "generator_command": manifest.get("generator_command"),
                "model_artifact": manifest.get("model_artifact"),
                "config": manifest.get("config"),
                "start_date": manifest.get("start_date"),
                "end_date": manifest.get("end_date"),
            },
        },
        {
            "name": "output_path_is_staging_only",
            "ok": is_under(output_dir, STAGING_ROOT) and not is_under(output_dir, TARGET_BASELINE_PATH),
            "value": output_dir,
        },
        {
            "name": "target_production_path_not_created",
            "ok": production_path_exists is False and checks_payload.get("target_production_path_created") is False,
            "value": {"path": repo_path(TARGET_BASELINE_PATH), "exists": production_path_exists},
        },
        {
            "name": "not_copied_from_candidate_or_subset_source",
            "ok": lineage.get("copied_from_candidate_source") is False
            and lineage.get("copied_from_subset_source") is False
            and lineage.get("symlinked_from_existing_ranking_dir") is False
            and "candidate" not in json.dumps(manifest.get("source_pipeline"), ensure_ascii=False).lower()
            and "subset" not in json.dumps(manifest.get("source_pipeline"), ensure_ascii=False).lower(),
            "value": lineage,
        },
        {
            "name": "production_impact_no_change",
            "ok": manifest.get("production_impact") == PRODUCTION_IMPACT and smoke.get("production_impact") == PRODUCTION_IMPACT,
            "value": {"manifest": manifest.get("production_impact"), "smoke": smoke.get("production_impact")},
        },
        {
            "name": "no_promotion_ready",
            "ok": not contains_forbidden_text(smoke, manifest)
            and contract.get("no_promotion_ready") is True
            and checks_payload.get("no_promotion_ready") is True,
            "value": False,
        },
        {
            "name": "blocked_has_reason",
            "ok": harness_status == "OK" or bool(blockers),
            "value": blockers,
        },
        {
            "name": "no_full_replay_unlock",
            "ok": (smoke.get("summary") or {}).get("full_replay_unlocked") is False
            and contract.get("does_not_execute_replay") is True,
            "value": smoke.get("summary"),
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK" if not failed else "FAILED",
        "harness_status": harness_status,
        "smoke_artifact": repo_path(smoke_artifact),
        "manifest": repo_path(manifest_path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "ranking_file_count": len(manifest.get("ranking_dates") or []),
            "production_impact": manifest.get("production_impact"),
        },
        "checks": checks,
        "ranking_verification": ranking,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    default_smoke, _ = smoke_paths(args.date)
    smoke_artifact = resolve_path(args.smoke_artifact) or default_smoke
    smoke = read_json(smoke_artifact)
    default_manifest = resolve_path(smoke.get("manifest")) if smoke else None
    manifest_path = resolve_path(args.manifest) or default_manifest
    if manifest_path is None:
        manifest_path = STAGING_ROOT / f"production_baseline_harness_{args.date}" / "manifest.json"
    output = resolve_path(args.output)
    assert output is not None
    payload = build_payload(args.date, smoke_artifact, manifest_path)
    write_json(output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "harness_status": payload["harness_status"],
                "failed_count": payload["summary"]["failed_count"],
                "output": repo_path(output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
