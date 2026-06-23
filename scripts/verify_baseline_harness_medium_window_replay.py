#!/usr/bin/env python3
"""驗證 baseline harness medium-window replay。"""

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


VERIFY_SCHEMA_VERSION = "baseline-harness-medium-window-replay-verification.v1"
ARTIFACT_SCHEMA_VERSION = "baseline-harness-medium-window-replay.v1"
INPUT_BASELINE_PATH = "artifacts/backtest/production_baseline_harness_medium_window"
REQUIRED_START_DATE = "2025-12-24"
REQUIRED_END_DATE = "2026-05-15"
MIN_RANKING_COUNT = 60
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify baseline harness medium-window replay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifact", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/baseline_harness_medium_window_replay_verification_latest.json",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_path(run_date: str, override: str | None) -> Path:
    if override:
        path = resolve_path(override)
        assert path is not None
        return path
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_medium_window_replay_{run_date}.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def contains_forbidden_text(payload: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payload, ensure_ascii=False)


def build_payload(run_date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    runner_args = ((payload.get("runner") or {}).get("args") or {}) if isinstance(payload.get("runner"), dict) else {}
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    manifest_path = resolve_path(payload.get("manifest")) if payload.get("manifest") else None
    manifest = read_json(manifest_path) if manifest_path else {}
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == ARTIFACT_SCHEMA_VERSION, "value": payload.get("schema_version")},
        {"name": "medium_window_status_ok", "ok": payload.get("medium_window_status") == "OK", "value": payload.get("medium_window_status")},
        {"name": "runner_can_read_baseline", "ok": payload.get("runner_can_read_baseline") is True, "value": payload.get("runner_can_read_baseline")},
        {"name": "input_baseline_path_exact", "ok": payload.get("input_baseline_path") == INPUT_BASELINE_PATH, "value": payload.get("input_baseline_path")},
        {"name": "start_date_exact", "ok": window.get("start") == REQUIRED_START_DATE, "value": window.get("start")},
        {"name": "end_date_exact", "ok": window.get("end") == REQUIRED_END_DATE, "value": window.get("end")},
        {
            "name": "ranking_file_count_gte_60",
            "ok": isinstance(payload.get("ranking_file_count"), int) and payload.get("ranking_file_count") >= MIN_RANKING_COUNT,
            "value": payload.get("ranking_file_count"),
        },
        {
            "name": "actual_replay_count_gte_60",
            "ok": isinstance(payload.get("actual_replay_count"), int) and payload.get("actual_replay_count") >= MIN_RANKING_COUNT,
            "value": payload.get("actual_replay_count"),
        },
        {
            "name": "runner_bound_to_medium_window",
            "ok": runner_args.get("rankings_dir") == INPUT_BASELINE_PATH
            and isinstance(runner_args.get("max_ranking_files"), int)
            and runner_args.get("max_ranking_files") == payload.get("ranking_file_count")
            and runner_args.get("horizon") == 1,
            "value": runner_args,
        },
        {
            "name": "manifest_exists_and_matches",
            "ok": manifest_path is not None
            and manifest_path.exists()
            and manifest.get("schema_version") == "research-only-production-baseline-medium-window-manifest.v1"
            and manifest.get("target_output_path") == INPUT_BASELINE_PATH
            and (manifest.get("window") or {}).get("start") == REQUIRED_START_DATE
            and (manifest.get("window") or {}).get("end") == REQUIRED_END_DATE
            and manifest.get("ranking_file_count") == payload.get("ranking_file_count"),
            "value": {"manifest": repo_path(manifest_path), "summary": {k: manifest.get(k) for k in ["schema_version", "target_output_path", "ranking_file_count"]}},
        },
        {
            "name": "target_production_path_absent",
            "ok": FORBIDDEN_PRODUCTION_PATH.exists() is False and payload.get("target_production_path_created") is False,
            "value": {"path": repo_path(FORBIDDEN_PRODUCTION_PATH), "exists": FORBIDDEN_PRODUCTION_PATH.exists(), "payload": payload.get("target_production_path_created")},
        },
        {"name": "estimated_unlockable_combo_count_zero", "ok": payload.get("estimated_unlockable_combo_count") == 0, "value": payload.get("estimated_unlockable_combo_count")},
        {"name": "production_impact_no_change", "ok": payload.get("production_impact") == PRODUCTION_IMPACT, "value": payload.get("production_impact")},
        {
            "name": "research_only_contract",
            "ok": contract.get("research_only") is True
            and contract.get("medium_window_only") is True
            and contract.get("review_window_only") is True
            and contract.get("does_not_create_artifacts_backtest_production") is True
            and contract.get("does_not_run_202176_grid") is True
            and contract.get("does_not_change_production_ranking") is True
            and contract.get("does_not_write_models_latest_lgbm") is True
            and contract.get("does_not_publish_clawd") is True
            and contract.get("medium_window_ok_is_not_full_replay_unlock") is True,
            "value": contract,
        },
        {"name": "no_promotion_ready", "ok": not contains_forbidden_text(payload) and contract.get("no_promotion_ready") is True, "value": False},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "verification_summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "medium_window_status": payload.get("medium_window_status"),
            "runner_can_read_baseline": payload.get("runner_can_read_baseline"),
            "input_baseline_path": payload.get("input_baseline_path"),
            "start_date": window.get("start"),
            "end_date": window.get("end"),
            "ranking_file_count": payload.get("ranking_file_count"),
            "actual_replay_count": payload.get("actual_replay_count"),
            "estimated_unlockable_combo_count": payload.get("estimated_unlockable_combo_count"),
            "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
            "production_impact": payload.get("production_impact"),
        },
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    artifact = artifact_path(str(args.date), args.artifact)
    output = resolve_path(args.output)
    assert output is not None
    payload = build_payload(str(args.date), artifact)
    write_json(output, payload)
    print(f"BASELINE_HARNESS_MEDIUM_WINDOW_REPLAY_VERIFICATION_{payload['status']} output={repo_path(output)}")
    if payload["status"] != "OK":
        for error in payload["errors"]:
            print(f"ERROR: {error['name']} value={error.get('value')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
