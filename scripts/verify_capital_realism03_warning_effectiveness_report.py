#!/usr/bin/env python3
"""驗證 CAPITAL-REALISM-03 warning effectiveness 報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism03-warning-effectiveness.v1"
ALLOWED_DECISIONS = {
    "DIRECTIONALLY_USEFUL_MONITOR_ONLY",
    "PARTIAL_WEAKENING_SIGNAL_MONITOR_ONLY",
    "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL",
}
LEVELS = {"WATCH", "WEAKENING", "RISK_ALERT"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-03 warning effectiveness report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism03_warning_effectiveness_report_2026-06-05.json",
    )
    parser.add_argument("--min-target-dates", type=int, default=80)
    parser.add_argument("--min-observations", type=int, default=1000)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    errors: list[str] = []
    if not artifact.exists():
        errors.append(f"artifact missing: {artifact}")
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False))
        return 1

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    summary = payload.get("summary", {})
    decision = payload.get("decision", {})

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    for key in ("research_only", "does_not_send_push", "non_personal_warning_only"):
        if not contract.get(key):
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key):
            errors.append(f"contract.{key} must be false")
    if contract.get("uses_future_rankings_for_warning") is not False:
        errors.append("warning must not use future rankings")
    if contract.get("uses_future_prices_for_evaluation_only") is not True:
        errors.append("future prices must be evaluation-only")
    if contract.get("watchlist_ranking_days") != 7:
        errors.append("watchlist_ranking_days must be 7")
    if contract.get("top_n") != 10:
        errors.append("top_n must be 10")

    if int(inputs.get("evaluated_target_dates") or 0) < args.min_target_dates:
        errors.append("evaluated_target_dates below minimum")
    if int(summary.get("observation_count") or 0) < args.min_observations:
        errors.append("observation_count below minimum")

    level_counts = summary.get("level_counts") or {}
    if set(level_counts) - LEVELS:
        errors.append(f"unexpected warning levels: {sorted(set(level_counts) - LEVELS)}")
    outcomes = summary.get("level_outcomes") or {}
    for level in LEVELS:
        if level not in outcomes:
            errors.append(f"missing level outcome: {level}")
            continue
        for horizon in ("1", "3", "5", "10"):
            row = outcomes[level].get(horizon)
            if not row or "count" not in row or "avg_return" not in row:
                errors.append(f"missing outcome shape: {level} {horizon}d")

    if decision.get("status") not in ALLOWED_DECISIONS:
        errors.append("decision.status not allowed")
    if decision.get("recommendation_channel") != "NO_CHANGE":
        errors.append("recommendation channel must remain unchanged")
    if decision.get("warning_channel") != "RESEARCH_ONLY_NOT_PUSH":
        errors.append("warning channel must stay research-only")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
