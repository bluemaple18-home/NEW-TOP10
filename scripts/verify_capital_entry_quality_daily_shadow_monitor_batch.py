#!/usr/bin/env python3
"""驗證入場品質每日 shadow monitor batch。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify capital entry quality daily shadow monitor batch")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/capital_entry_quality_daily_shadow_monitor_batch_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def model_sha256() -> str:
    digest = hashlib.sha256()
    with (PROJECT_ROOT / "models" / "latest_lgbm.pkl").open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_path(args: argparse.Namespace) -> Path:
    if args.artifact:
        return resolve_path(args.artifact)
    date_text = args.date or latest_monitor_date()
    return PROJECT_ROOT / "artifacts" / "model_experiments" / f"capital_entry_quality_daily_shadow_monitor_batch_{date_text}.json"


def latest_monitor_date() -> str:
    files = sorted((PROJECT_ROOT / "artifacts" / "model_experiments").glob("capital_entry_quality_daily_shadow_monitor_batch_*.json"))
    if not files:
        return "1970-01-01"
    return files[-1].stem.removeprefix("capital_entry_quality_daily_shadow_monitor_batch_")


def n(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    args = parse_args()
    artifact = artifact_path(args)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    rows = payload.get("rows") or []
    sample_policy = summary.get("sample_policy") or {}
    allowed_statuses = {"MONITOR_ACTIVE_ENTRY_FILTER_DISTRIBUTION", "MONITOR_ACTIVE_NO_BALANCED_ELIGIBLE"}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "monitor_status_allowed": payload.get("monitor_status") in allowed_statuses,
        "shadow_only": contract.get("operational_shadow_only") is True,
        "default_not_allowed": contract.get("default_allowed") is False,
        "no_production_top10_change": contract.get("changes_production_top10_membership") is False,
        "no_score_change": contract.get("changes_risk_adjusted_score") is False,
        "no_ranking_change": contract.get("changes_production_ranking") is False,
        "no_message_change": contract.get("changes_clawd_message") is False,
        "no_model_change": contract.get("changes_model") is False and model_sha256() == args.expected_model_sha256,
        "uses_no_future_rankings": contract.get("uses_future_rankings_for_filters") is False,
        "ranking_days_present": int(summary.get("ranking_days") or 0) == len(rows) and len(rows) >= 3,
        "balanced_distribution_present": n(summary.get("avg_balanced_eligible_count")) >= 0,
        "conservative_distribution_present": n(summary.get("avg_conservative_eligible_count")) >= 0,
        "sample_policy_blocks_default": sample_policy.get("sample_ready_for_default_review") is False,
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "capital-entry-quality-daily-shadow-monitor-batch-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
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
