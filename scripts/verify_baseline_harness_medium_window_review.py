#!/usr/bin/env python3
"""驗證 baseline harness medium-window review artifact。"""

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


VERIFY_SCHEMA_VERSION = "baseline-harness-medium-window-review-verification.v1"
ARTIFACT_SCHEMA_VERSION = "baseline-harness-medium-window-review.v1"
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"
MIN_MEDIUM_TRADING_DAYS = 60
MAX_MEDIUM_TRADING_DAYS = 120


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify baseline harness medium-window review")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifact", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/baseline_harness_medium_window_review_verification_latest.json",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_path(run_date: str, override: str | None) -> Path:
    if override:
        path = resolve_path(override)
        assert path is not None
        return path
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_medium_window_review_{run_date}.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def contains_forbidden_text(payload: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payload, ensure_ascii=False)


def build_payload(run_date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    review_scope = payload.get("review_scope") if isinstance(payload.get("review_scope"), dict) else {}
    trading_day_count = payload.get("recommended_trading_day_count")
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == ARTIFACT_SCHEMA_VERSION, "value": payload.get("schema_version")},
        {
            "name": "medium_window_review_status_ok",
            "ok": payload.get("medium_window_review_status") == "OK",
            "value": payload.get("medium_window_review_status"),
        },
        {"name": "small_window_verified", "ok": payload.get("small_window_verified") is True, "value": payload.get("small_window_verified")},
        {"name": "warning_profile_ok", "ok": payload.get("warning_profile_ok") is True, "value": payload.get("warning_profile_ok")},
        {"name": "runtime_profile_ok", "ok": payload.get("runtime_profile_ok") is True, "value": payload.get("runtime_profile_ok")},
        {"name": "can_run_medium_window", "ok": payload.get("can_run_medium_window") is True, "value": payload.get("can_run_medium_window")},
        {
            "name": "recommended_window_within_bound",
            "ok": isinstance(trading_day_count, int) and MIN_MEDIUM_TRADING_DAYS <= trading_day_count <= MAX_MEDIUM_TRADING_DAYS,
            "value": {
                "recommended_medium_window": payload.get("recommended_medium_window"),
                "recommended_trading_day_count": trading_day_count,
                "min": MIN_MEDIUM_TRADING_DAYS,
                "max": MAX_MEDIUM_TRADING_DAYS,
            },
        },
        {
            "name": "estimated_unlockable_combo_count_zero",
            "ok": payload.get("estimated_unlockable_combo_count") == 0,
            "value": payload.get("estimated_unlockable_combo_count"),
        },
        {
            "name": "target_production_path_absent",
            "ok": FORBIDDEN_PRODUCTION_PATH.exists() is False and payload.get("target_production_path_created") is False,
            "value": {
                "path": repo_path(FORBIDDEN_PRODUCTION_PATH),
                "exists": FORBIDDEN_PRODUCTION_PATH.exists(),
                "payload": payload.get("target_production_path_created"),
            },
        },
        {"name": "production_impact_no_change", "ok": payload.get("production_impact") == PRODUCTION_IMPACT, "value": payload.get("production_impact")},
        {
            "name": "review_only_contract",
            "ok": contract.get("research_only") is True
            and contract.get("review_only") is True
            and contract.get("does_not_create_artifacts_backtest_production") is True
            and contract.get("does_not_run_202176_grid") is True
            and contract.get("does_not_change_production_ranking") is True
            and contract.get("does_not_write_models_latest_lgbm") is True
            and contract.get("does_not_publish_clawd") is True
            and contract.get("medium_window_review_ok_is_not_full_replay_unlock") is True
            and review_scope.get("does_not_execute_medium_window_replay") is True
            and review_scope.get("does_not_materialize_medium_window_baseline") is True,
            "value": {"contract": contract, "review_scope": review_scope},
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
            "medium_window_review_status": payload.get("medium_window_review_status"),
            "small_window_verified": payload.get("small_window_verified"),
            "recommended_medium_window": payload.get("recommended_medium_window"),
            "recommended_trading_day_count": payload.get("recommended_trading_day_count"),
            "can_run_medium_window": payload.get("can_run_medium_window"),
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
    print(f"BASELINE_HARNESS_MEDIUM_WINDOW_REVIEW_VERIFICATION_{payload['status']} output={repo_path(output)}")
    if payload["status"] != "OK":
        for error in payload["errors"]:
            print(f"ERROR: {error['name']} value={error.get('value')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
