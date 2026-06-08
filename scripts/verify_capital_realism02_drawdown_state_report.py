#!/usr/bin/env python3
"""驗證 CAPITAL-REALISM-02 drawdown state 報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-02 drawdown state report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism02_drawdown_state_report_2026-06-05.json",
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
    comparisons = payload.get("comparisons") or {}
    summary = payload.get("summary") or {}

    if payload.get("schema_version") != "capital-realism02-drawdown-state-report.v1":
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if len(runs) != 18:
        errors.append(f"expected 18 drawdown state runs, got {len(runs)}")
    if len(comparisons) != len(runs):
        errors.append("comparisons must match runs")
    if contract.get("drawdown_state_run_count") != 18:
        errors.append("contract.drawdown_state_run_count must be 18")
    if contract.get("fixed40_reference_count") != 6:
        errors.append("contract.fixed40_reference_count must be 6")
    for key in ("research_only", "finite_capital", "odd_lot_default"):
        if not contract.get(key):
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key):
            errors.append(f"contract.{key} must be false")

    for run_id, row in runs.items():
        if row.get("buy_lot_size") != 1 or row.get("sell_lot_size") != 1:
            errors.append(f"{run_id}: lot sizes must be 1")
        if not row.get("research_only"):
            errors.append(f"{run_id}: research_only must be true")
        if row.get("changes_model") or row.get("changes_ranking_score"):
            errors.append(f"{run_id}: must not change model or ranking score")
        if not row.get("drawdown_state_enabled"):
            errors.append(f"{run_id}: drawdown_state_enabled must be true")
        if row.get("scenario") != "fixed40" or row.get("entry_filter") != "all":
            errors.append(f"{run_id}: expected fixed40/all")
        source = row.get("path")
        if not source or not resolve_path(source).exists():
            errors.append(f"{run_id}: source artifact missing")
        if run_id not in comparisons:
            errors.append(f"{run_id}: comparison missing")

    if summary.get("return_degraded_count", 0) < 12:
        errors.append("drawdown state must show broad return degradation before reject decision")
    if decision.get("status") != "DRAWDOWN_STATE_REJECT_AS_DEFAULT":
        errors.append("decision.status must reject drawdown state as default")
    if decision.get("drawdown_state") != "TOO_AGGRESSIVE_CURRENT_ENGINE":
        errors.append("decision.drawdown_state must flag current engine as too aggressive")
    if decision.get("recommendation_channel") != "NO_CHANGE":
        errors.append("recommendation channel must remain unchanged")
    if decision.get("warning_channel") != "NEXT_RESEARCH_TARGET":
        errors.append("warning channel must be the next research target")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
