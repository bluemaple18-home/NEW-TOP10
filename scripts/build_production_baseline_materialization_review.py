#!/usr/bin/env python3
"""審核 production baseline harness 是否可進 research-only materialization。

這支腳本只讀 staging harness 與驗證證據，產出 review artifact；
不建立 artifacts/backtest/production，不跑 replay，不改模型。
"""

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

from build_production_baseline_harness import (  # noqa: E402
    SCHEMA_VERSION as HARNESS_SCHEMA_VERSION,
    SMOKE_SCHEMA_VERSION as HARNESS_SMOKE_SCHEMA_VERSION,
    STAGING_ROOT,
    TARGET_BASELINE_PATH,
    smoke_paths as harness_smoke_paths,
)
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json, write_text  # noqa: E402


SCHEMA_VERSION = "production-baseline-materialization-review.v1"
WEEKEND_DIR = PROJECT_ROOT / "artifacts" / "weekend_training"
TASK_ID = "WEEKEND-TRAINING-15"
NEXT_ACTION_OK = "WEEKEND-TRAINING-16_research_only_baseline_materialization_smoke"
NEXT_ACTION_BLOCKED = "修 harness / manifest blocker"
DEFAULT_TARGET_OUTPUT_PATH = "artifacts/backtest/production_baseline_harness_smoke"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production baseline materialization review")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--smoke-artifact", default=None)
    parser.add_argument(
        "--harness-verification",
        default="artifacts/weekend_training/production_baseline_harness_verification_latest.json",
    )
    parser.add_argument("--target-output-path", default=DEFAULT_TARGET_OUTPUT_PATH)
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def output_paths(run_date: str) -> tuple[Path, Path]:
    stem = f"production_baseline_materialization_review_{run_date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
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


def is_exact_or_under(path_text: str | None, root: Path) -> bool:
    if not path_text:
        return False
    path = resolve_path(path_text)
    if path is None:
        return False
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        return resolved == root_resolved or bool(resolved.relative_to(root_resolved))
    except ValueError:
        return False


def has_complete_provenance(manifest: dict[str, Any]) -> bool:
    data_source = manifest.get("data_source") if isinstance(manifest.get("data_source"), dict) else {}
    no_future = manifest.get("no_future_data_contract") if isinstance(manifest.get("no_future_data_contract"), dict) else {}
    required = [
        manifest.get("generator_command"),
        manifest.get("internal_generator_command"),
        manifest.get("source_pipeline"),
        manifest.get("model_artifact"),
        manifest.get("model_hash"),
        manifest.get("config"),
        manifest.get("config_hash"),
        data_source.get("features"),
        data_source.get("features_hash"),
        data_source.get("universe"),
        data_source.get("universe_hash"),
        manifest.get("start_date"),
        manifest.get("end_date"),
        no_future.get("ranking_row_contract"),
        no_future.get("market_regime_contract"),
    ]
    return all(bool(item) for item in required)


def date_coverage(manifest: dict[str, Any]) -> dict[str, Any]:
    ranking_dates = [str(item) for item in manifest.get("ranking_dates") or []]
    expected_dates = [str(item) for item in manifest.get("expected_ranking_dates") or []]
    start_date = str(manifest.get("start_date") or "")
    end_date = str(manifest.get("end_date") or "")
    dates_match = bool(ranking_dates) and ranking_dates == expected_dates
    range_match = bool(ranking_dates) and ranking_dates[0] == start_date and ranking_dates[-1] == end_date
    return {
        "ok": dates_match and range_match and len(ranking_dates) == 3,
        "start": start_date,
        "end": end_date,
        "dates": ranking_dates,
        "expected_dates": expected_dates,
        "date_count": len(ranking_dates),
    }


def check_payload_text(*payloads: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT not in json.dumps(payloads, ensure_ascii=False)


def blocked_reasons(checks: dict[str, bool]) -> list[str]:
    labels = {
        "smoke_artifact_exists": "SMOKE_ARTIFACT_MISSING",
        "manifest_exists": "MANIFEST_MISSING",
        "harness_verification_ok": "HARNESS_VERIFICATION_NOT_OK",
        "staging_harness_verified": "STAGING_HARNESS_NOT_VERIFIED",
        "manifest_provenance_complete": "MANIFEST_PROVENANCE_INCOMPLETE",
        "date_coverage_sufficient_for_smoke": "DATE_COVERAGE_NOT_THREE_DAY_SMOKE",
        "target_output_path_research_only": "TARGET_OUTPUT_PATH_NOT_RESEARCH_ONLY",
        "target_production_path_not_created": "TARGET_PRODUCTION_PATH_EXISTS",
        "estimated_unlockable_combo_count_zero": "UNLOCKABLE_COMBO_COUNT_NOT_ZERO",
        "production_impact_no_change": "PRODUCTION_IMPACT_NOT_NO_CHANGE",
        "no_promotion_ready_text": "PROMOTION_READY_TEXT_PRESENT",
        "no_full_replay_unlock": "FULL_REPLAY_UNLOCKED",
    }
    return [labels[name] for name, ok in checks.items() if not ok and name in labels]


def build_payload(
    run_date: str,
    smoke_artifact: Path,
    manifest_path: Path,
    verification_path: Path,
    target_output_path: str,
) -> dict[str, Any]:
    smoke = read_json(smoke_artifact)
    manifest = read_json(manifest_path)
    verification = read_json(verification_path)
    smoke_checks = smoke.get("checks") if isinstance(smoke.get("checks"), dict) else {}
    manifest_checks = manifest.get("checks") if isinstance(manifest.get("checks"), dict) else {}
    manifest_summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    verification_summary = verification.get("summary") if isinstance(verification.get("summary"), dict) else {}
    smoke_summary = smoke.get("summary") if isinstance(smoke.get("summary"), dict) else {}
    coverage = date_coverage(manifest)
    harness_status = smoke.get("harness_status") or manifest_summary.get("harness_status")
    unlockable_combo_count = 0
    target_output_path_ok = not is_exact_or_under(target_output_path, TARGET_BASELINE_PATH)
    staging_harness_verified = (
        harness_status == "OK"
        and smoke_checks.get("staging_output_only") is True
        and smoke_checks.get("target_production_path_created") is False
        and manifest_checks.get("staging_output_only") is True
        and manifest_checks.get("target_production_path_created") is False
        and is_under(manifest.get("output_dir"), STAGING_ROOT)
    )
    manifest_provenance_complete = has_complete_provenance(manifest) and manifest_checks.get("provenance_complete") is True
    harness_verification_ok = (
        verification_path.exists()
        and verification.get("status") == "OK"
        and verification.get("harness_status") == "OK"
        and int(verification_summary.get("failed_count") or 0) == 0
    )
    checks = {
        "smoke_artifact_exists": smoke_artifact.exists() and smoke.get("schema_version") == HARNESS_SMOKE_SCHEMA_VERSION,
        "manifest_exists": manifest_path.exists() and manifest.get("schema_version") == HARNESS_SCHEMA_VERSION,
        "harness_verification_ok": harness_verification_ok,
        "staging_harness_verified": staging_harness_verified,
        "manifest_provenance_complete": manifest_provenance_complete,
        "date_coverage_sufficient_for_smoke": coverage["ok"],
        "target_output_path_research_only": target_output_path_ok,
        "target_production_path_not_created": TARGET_BASELINE_PATH.exists() is False,
        "estimated_unlockable_combo_count_zero": unlockable_combo_count == 0,
        "production_impact_no_change": manifest.get("production_impact") == PRODUCTION_IMPACT
        and smoke.get("production_impact") == PRODUCTION_IMPACT,
        "no_promotion_ready_text": check_payload_text(smoke, manifest, verification),
        "no_full_replay_unlock": smoke_summary.get("full_replay_unlocked") is False,
    }
    blockers = blocked_reasons(checks)
    can_materialize = not blockers
    status = "OK" if can_materialize else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "task_id": TASK_ID,
        "materialization_review_status": status,
        "staging_harness_verified": staging_harness_verified,
        "manifest_provenance_complete": manifest_provenance_complete,
        "date_coverage_sufficient_for_smoke": coverage["ok"],
        "can_materialize_research_baseline": can_materialize,
        "target_output_path": target_output_path,
        "allowed_date_range": {
            "start": coverage["start"],
            "end": coverage["end"],
            "dates": coverage["dates"],
            "scope": "3-day smoke only",
        },
        "estimated_unlockable_combo_count": unlockable_combo_count,
        "next_action": NEXT_ACTION_OK if can_materialize else NEXT_ACTION_BLOCKED,
        "production_impact": PRODUCTION_IMPACT,
        "review_sources": {
            "manifest": repo_path(manifest_path),
            "smoke_artifact": repo_path(smoke_artifact),
            "harness_verification": repo_path(verification_path),
        },
        "checks": checks,
        "coverage": coverage,
        "summary": {
            "harness_status": harness_status,
            "ranking_file_count": manifest_summary.get("ranking_file_count"),
            "verification_status": verification.get("status"),
            "verification_failed_count": verification_summary.get("failed_count"),
            "target_production_path": repo_path(TARGET_BASELINE_PATH),
            "target_production_path_exists": TARGET_BASELINE_PATH.exists(),
        },
        "contract": {
            "research_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_execute_replay": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
            "no_promotion_ready": True,
            "review_ok_is_not_promotion_ready": True,
            "three_day_smoke_is_not_half_year_baseline": True,
        },
        "blocker_reasons": blockers,
        "errors": [],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    allowed = payload["allowed_date_range"]
    lines = [
        "# Production Baseline Materialization Review",
        "",
        f"- materialization_review_status: `{payload['materialization_review_status']}`",
        f"- staging_harness_verified: `{payload['staging_harness_verified']}`",
        f"- manifest_provenance_complete: `{payload['manifest_provenance_complete']}`",
        f"- date_coverage_sufficient_for_smoke: `{payload['date_coverage_sufficient_for_smoke']}`",
        f"- can_materialize_research_baseline: `{payload['can_materialize_research_baseline']}`",
        f"- target_output_path: `{payload['target_output_path']}`",
        f"- allowed_date_range: `{allowed['start']} ~ {allowed['end']}`",
        f"- estimated_unlockable_combo_count: `{payload['estimated_unlockable_combo_count']}`",
        f"- next_action: `{payload['next_action']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {name}: `{ok}`" for name, ok in checks.items())
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blocker_reasons") or []
    if blockers:
        lines.extend(f"- `{reason}`" for reason in blockers)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Review OK only opens the research-only 3-day materialization smoke. It does not unlock full replay or promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    default_smoke, _ = harness_smoke_paths(args.date)
    smoke_artifact = resolve_path(args.smoke_artifact) or default_smoke
    smoke = read_json(smoke_artifact)
    default_manifest = resolve_path(smoke.get("manifest")) if smoke else None
    manifest_path = resolve_path(args.manifest) or default_manifest
    if manifest_path is None:
        manifest_path = STAGING_ROOT / f"production_baseline_harness_{args.date}" / "manifest.json"
    verification_path = resolve_path(args.harness_verification)
    assert verification_path is not None
    payload = build_payload(args.date, smoke_artifact, manifest_path, verification_path, args.target_output_path)
    json_path, md_path = output_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["materialization_review_status"],
                "can_materialize_research_baseline": payload["can_materialize_research_baseline"],
                "output": repo_path(json_path),
                "production_impact": payload["production_impact"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["materialization_review_status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
