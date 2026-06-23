#!/usr/bin/env python3
"""驗證 baseline harness minimal replay smoke。"""

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


VERIFY_SCHEMA_VERSION = "baseline-harness-minimal-replay-smoke-verification.v1"
SMOKE_SCHEMA_VERSION = "baseline-harness-minimal-replay-smoke.v1"
EXPECTED_DATES = ["2026-05-13", "2026-05-14", "2026-05-15"]
INPUT_BASELINE_PATH = "artifacts/backtest/production_baseline_harness_smoke"
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify baseline harness minimal replay smoke")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifact", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/baseline_harness_minimal_replay_smoke_verification_latest.json",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_path(run_date: str, override: str | None) -> Path:
    if override:
        path = resolve_path(override)
        assert path is not None
        return path
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_minimal_replay_smoke_{run_date}.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def contains_forbidden_text(payload: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payload, ensure_ascii=False)


def build_payload(run_date: str, artifact: Path) -> dict[str, Any]:
    smoke = read_json(artifact)
    contract = smoke.get("contract") if isinstance(smoke.get("contract"), dict) else {}
    date_range = smoke.get("date_range") if isinstance(smoke.get("date_range"), dict) else {}
    runner = smoke.get("runner") if isinstance(smoke.get("runner"), dict) else {}
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": smoke.get("schema_version") == SMOKE_SCHEMA_VERSION, "value": smoke.get("schema_version")},
        {
            "name": "replay_smoke_status_allowed",
            "ok": smoke.get("replay_smoke_status") in {"OK", "BLOCKED_DATA_GAP"},
            "value": smoke.get("replay_smoke_status"),
        },
        {"name": "runner_can_read_baseline", "ok": smoke.get("runner_can_read_baseline") is True, "value": smoke.get("runner_can_read_baseline")},
        {
            "name": "input_baseline_path_exact",
            "ok": smoke.get("input_baseline_path") == INPUT_BASELINE_PATH,
            "value": smoke.get("input_baseline_path"),
        },
        {"name": "ranking_file_count_three", "ok": smoke.get("ranking_file_count") == 3, "value": smoke.get("ranking_file_count")},
        {
            "name": "date_range_exact",
            "ok": date_range.get("start") == EXPECTED_DATES[0]
            and date_range.get("end") == EXPECTED_DATES[-1]
            and date_range.get("dates") == EXPECTED_DATES,
            "value": date_range,
        },
        {
            "name": "actual_replay_count_lte_three",
            "ok": isinstance(smoke.get("actual_replay_count"), int) and smoke.get("actual_replay_count") <= 3,
            "value": smoke.get("actual_replay_count"),
        },
        {
            "name": "target_production_path_absent",
            "ok": FORBIDDEN_PRODUCTION_PATH.exists() is False and smoke.get("target_production_path_created") is False,
            "value": {"path": repo_path(FORBIDDEN_PRODUCTION_PATH), "exists": FORBIDDEN_PRODUCTION_PATH.exists(), "payload": smoke.get("target_production_path_created")},
        },
        {
            "name": "estimated_unlockable_combo_count_zero",
            "ok": smoke.get("estimated_unlockable_combo_count") == 0,
            "value": smoke.get("estimated_unlockable_combo_count"),
        },
        {
            "name": "production_impact_no_change",
            "ok": smoke.get("production_impact") == PRODUCTION_IMPACT,
            "value": smoke.get("production_impact"),
        },
        {
            "name": "runner_bound_to_three_files",
            "ok": runner.get("args", {}).get("rankings_dir") == INPUT_BASELINE_PATH
            and runner.get("args", {}).get("max_ranking_files") == 3
            and runner.get("args", {}).get("horizon") == 1,
            "value": runner.get("args"),
        },
        {
            "name": "research_only_contract",
            "ok": contract.get("research_only") is True
            and contract.get("three_day_smoke_only") is True
            and contract.get("does_not_create_artifacts_backtest_production") is True
            and contract.get("does_not_run_202176_grid") is True
            and contract.get("does_not_change_production_ranking") is True
            and contract.get("does_not_write_models_latest_lgbm") is True
            and contract.get("does_not_publish_clawd") is True,
            "value": contract,
        },
        {
            "name": "no_promotion_ready",
            "ok": not contains_forbidden_text(smoke) and contract.get("no_promotion_ready") is True,
            "value": False,
        },
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
            "replay_smoke_status": smoke.get("replay_smoke_status"),
            "runner_can_read_baseline": smoke.get("runner_can_read_baseline"),
            "ranking_file_count": smoke.get("ranking_file_count"),
            "actual_replay_count": smoke.get("actual_replay_count"),
            "estimated_unlockable_combo_count": smoke.get("estimated_unlockable_combo_count"),
            "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
            "production_impact": smoke.get("production_impact"),
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
    print(f"BASELINE_HARNESS_MINIMAL_REPLAY_SMOKE_VERIFICATION_{payload['status']} output={repo_path(output)}")
    if payload["status"] != "OK":
        for error in payload["errors"]:
            print(f"ERROR: {error['name']} value={error.get('value')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
