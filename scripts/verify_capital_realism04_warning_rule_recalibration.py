#!/usr/bin/env python3
"""驗證 CAPITAL-REALISM-04 warning rule recalibration 報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism04-warning-rule-recalibration.v1"
ALLOWED_STATUS = {"RISK_ALERT_RULE_CANDIDATE_FOUND", "NO_CLEAN_RISK_ALERT_RULE"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-04 warning rule recalibration report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism04_warning_rule_recalibration_2026-06-05.json",
    )
    parser.add_argument("--min-observations", type=int, default=1000)
    parser.add_argument("--min-candidates", type=int, default=8)
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
    candidates = payload.get("candidate_results") or {}
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
    if contract.get("target_horizon_days") != 10:
        errors.append("target_horizon_days must be 10")
    if int(inputs.get("observation_count") or 0) < args.min_observations:
        errors.append("observation_count below minimum")
    if len(candidates) < args.min_candidates:
        errors.append("candidate count below minimum")

    for name, row in candidates.items():
        outcome = row.get("outcome") or {}
        delta = row.get("delta_vs_watch") or {}
        if "count" not in outcome or "avg_return" not in outcome:
            errors.append(f"{name}: outcome shape invalid")
        for key in ("avg_return", "negative_rate", "loss_gt_5pct_rate"):
            if key not in delta:
                errors.append(f"{name}: delta_vs_watch.{key} missing")

    if decision.get("status") not in ALLOWED_STATUS:
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
