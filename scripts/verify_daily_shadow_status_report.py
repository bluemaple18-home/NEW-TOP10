#!/usr/bin/env python3
"""驗證 daily shadow status report 沒有越過 production 邊界。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily shadow status report")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/daily_shadow_status_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_artifact() -> Path | None:
    files = sorted(OUTPUT_DIR.glob("daily_shadow_status_*.json"))
    return files[-1] if files else None


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def model_sha256() -> str:
    digest = hashlib.sha256()
    with (PROJECT_ROOT / "models" / "latest_lgbm.pkl").open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_path(args: argparse.Namespace) -> Path | None:
    if args.artifact:
        return resolve_path(args.artifact)
    if args.date:
        return OUTPUT_DIR / f"daily_shadow_status_{args.date}.json"
    return latest_artifact()


def main() -> int:
    args = parse_args()
    artifact = artifact_path(args)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    branches = payload.get("branches") or []
    branch_ids = {str(row.get("branch_id")) for row in branches}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "schema": payload.get("schema_version") == "daily-shadow-status-report.v1",
        "report_only": contract.get("report_only") is True,
        "default_not_allowed": contract.get("default_allowed") is False,
        "no_top10_change": contract.get("changes_production_top10_membership") is False,
        "no_score_change": contract.get("changes_risk_adjusted_score") is False,
        "no_ranking_change": contract.get("changes_production_ranking") is False,
        "no_message_change": contract.get("changes_clawd_message") is False,
        "no_model_change": contract.get("changes_model") is False and model_sha256() == args.expected_model_sha256,
        "no_auto_retrain": contract.get("enables_auto_retrain") is False,
        "active_monitor_count": int(summary.get("active_daily_monitor_count") or 0) >= 2,
        "production_ready_zero": summary.get("production_ready_branch_count") == 0,
        "gross55_present": "gross55_exposure_shadow" in branch_ids,
        "capital_entry_present": "capital_entry_quality_shadow" in branch_ids,
        "training_schedule_manual": "manual" in str(summary.get("training_schedule_status") or ""),
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "daily-shadow-status-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact) if artifact else None,
                "checks": checks,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK" if not failed else "FAILED", "output": repo_path(output), "failed": failed}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
