#!/usr/bin/env python3
"""驗證入場品質每日 shadow monitor 邊界。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify capital entry quality daily shadow monitor")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/capital_entry_quality_daily_shadow_monitor_verification_latest.json")
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
    return PROJECT_ROOT / "artifacts" / "model_experiments" / f"capital_entry_quality_daily_shadow_monitor_{date_text}.json"


def latest_monitor_date() -> str:
    files = sorted((PROJECT_ROOT / "artifacts" / "model_experiments").glob("capital_entry_quality_daily_shadow_monitor_*.json"))
    if not files:
        return "1970-01-01"
    return files[-1].stem.removeprefix("capital_entry_quality_daily_shadow_monitor_")


def main() -> int:
    args = parse_args()
    artifact = artifact_path(args)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    filters = payload.get("filters") or {}
    allowed_statuses = {
        "MONITOR_ACTIVE_CONSERVATIVE_ELIGIBLE",
        "MONITOR_ACTIVE_BALANCED_ONLY",
        "MONITOR_ACTIVE_NO_SHADOW_ELIGIBLE",
    }
    all_count = int((filters.get("all") or {}).get("eligible_count") or 0)
    balanced_count = int((filters.get("non_worsening") or {}).get("eligible_count") or 0)
    conservative_count = int((filters.get("improved_only") or {}).get("eligible_count") or 0)
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
        "uses_no_future_rankings": (payload.get("inputs") or {}).get("uses_future_rankings_for_filters") is False,
        "production_top10_present": int(summary.get("production_top10_count") or 0) == all_count and all_count > 0,
        "balanced_subset": 0 <= balanced_count <= all_count,
        "conservative_subset": 0 <= conservative_count <= balanced_count,
        "expected_filters_present": {"all", "non_worsening", "improved_only"}.issubset(set(filters)),
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "capital-entry-quality-daily-shadow-monitor-verification.v1",
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
