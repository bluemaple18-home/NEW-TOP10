#!/usr/bin/env python3
"""驗證 CAPITAL-REALISM-02 報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RUN_COUNT = 36


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-02 report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism02_report_2026-06-05.json",
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
    runs = payload.get("runs") or {}

    if payload.get("schema_version") != "capital-realism02-report.v1":
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if len(runs) != EXPECTED_RUN_COUNT:
        errors.append(f"expected {EXPECTED_RUN_COUNT} runs, got {len(runs)}")
    if contract.get("run_count") != EXPECTED_RUN_COUNT:
        errors.append("contract.run_count mismatch")
    for key in ("research_only", "finite_capital", "odd_lot_default"):
        if not contract.get(key):
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key):
            errors.append(f"contract.{key} must be false")
    if contract.get("buy_lot_size") != 1 or contract.get("sell_lot_size") != 1:
        errors.append("contract lot sizes must be 1")

    for run_id, row in runs.items():
        if row.get("buy_lot_size") != 1 or row.get("sell_lot_size") != 1:
            errors.append(f"{run_id}: lot sizes must be 1")
        if not row.get("research_only"):
            errors.append(f"{run_id}: research_only must be true")
        if row.get("changes_model") or row.get("changes_ranking_score"):
            errors.append(f"{run_id}: must not change model or ranking score")
        source = row.get("path")
        if not source or not resolve_path(source).exists():
            errors.append(f"{run_id}: source artifact missing")

    if decision.get("status") != "ENTRY_EXIT_POLICY_NOT_READY":
        errors.append("decision.status must remain not ready")
    if decision.get("tp20_runner_stop8") != "REJECT_AS_DEFAULT_FOR_NOW":
        errors.append("TP20 runner stop8 must not be default")
    if decision.get("entry_filter_policy") != "DO_NOT_USE_SINGLE_GLOBAL_FILTER":
        errors.append("entry filter must not be global")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
