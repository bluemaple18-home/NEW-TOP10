#!/usr/bin/env python3
"""驗證 CAPITAL-REALISM-02 follow-up 報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-02 follow-up report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism02_followup_report_2026-06-05.json",
    )
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
    decision = payload.get("decision", {})
    entry_guard_runs = payload.get("entry_guard_runs") or {}
    stop_policy_runs = payload.get("stop_policy_runs") or {}

    if payload.get("schema_version") != "capital-realism02-followup-report.v1":
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if len(entry_guard_runs) != 18:
        errors.append(f"expected 18 entry guard runs, got {len(entry_guard_runs)}")
    if len(stop_policy_runs) != 18:
        errors.append(f"expected 18 stop policy runs, got {len(stop_policy_runs)}")
    for key in ("research_only", "finite_capital", "odd_lot_default"):
        if not contract.get(key):
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key):
            errors.append(f"contract.{key} must be false")
    for group_name, group in (("entry_guard", entry_guard_runs), ("stop_policy", stop_policy_runs)):
        for run_id, row in group.items():
            if row.get("buy_lot_size") != 1 or row.get("sell_lot_size") != 1:
                errors.append(f"{group_name}.{run_id}: lot sizes must be 1")
            if not row.get("research_only"):
                errors.append(f"{group_name}.{run_id}: research_only must be true")
            if row.get("changes_model") or row.get("changes_ranking_score"):
                errors.append(f"{group_name}.{run_id}: must not change model or ranking score")
            source = row.get("path")
            if not source or not resolve_path(source).exists():
                errors.append(f"{group_name}.{run_id}: source artifact missing")

    if decision.get("status") != "FOLLOWUP_COMPLETE_NO_PRODUCTION_CHANGE":
        errors.append("decision.status must be follow-up complete without production change")
    if decision.get("entry_price_guard") != "NO_EFFECT_IN_CURRENT_HALF_YEAR_SAMPLE":
        errors.append("entry guard must be no-effect")
    if decision.get("stop_policy") != "REJECT_MECHANICAL_STOP_AS_DEFAULT":
        errors.append("mechanical stop must be rejected as default")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
